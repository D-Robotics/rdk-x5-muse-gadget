"""ROS-independent topic selection and interaction gates.

This module deliberately has no ROS imports so its behavior can be tested on a
developer machine.  The ROS node converts messages into the small Python data
structures accepted here and forwards the resulting events to the Muse UI.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import json
import math
import socket
from typing import Any, Iterable, Mapping, Sequence


IMAGE_TYPE = "sensor_msgs/msg/Image"


def _topic_name(value: str) -> str:
    value = value.strip()
    if not value:
        return ""
    return value if value.startswith("/") else "/" + value


def _topic_types(value: Iterable[str] | str) -> set[str]:
    if isinstance(value, str):
        return {value}
    return set(value)


@dataclass(frozen=True)
class TopicPair:
    """A left/right ROS image topic pair."""

    left: str
    right: str


def select_stereo_topics(
    topics: Mapping[str, Iterable[str] | str],
    preferred_left: str = "",
    preferred_right: str = "",
) -> TopicPair | None:
    """Choose a sensor_msgs/Image stereo pair from a ROS graph snapshot.

    Explicit topics win when both are currently published.  Discovery then
    checks the MIPI driver's ``image_*_raw`` pair before the GS130 SDK's
    ``image_left``/``image_right`` pair.  Both topics must share a namespace;
    shared-memory image messages are intentionally rejected because this
    adapter subscribes to sensor_msgs/Image.
    """

    normalized = {_topic_name(name): _topic_types(types) for name, types in topics.items()}

    def is_image(name: str) -> bool:
        return IMAGE_TYPE in normalized.get(_topic_name(name), set())

    preferred_left = _topic_name(preferred_left)
    preferred_right = _topic_name(preferred_right)
    if preferred_left and preferred_right and is_image(preferred_left) and is_image(preferred_right):
        return TopicPair(preferred_left, preferred_right)

    suffix_pairs = (
        ("/image_left_raw", "/image_right_raw"),
        ("/image_left", "/image_right"),
    )
    candidates: list[tuple[int, int, TopicPair]] = []
    for priority, (left_suffix, right_suffix) in enumerate(suffix_pairs):
        for left in normalized:
            if not left.endswith(left_suffix) or not is_image(left):
                continue
            namespace = left[: -len(left_suffix)]
            right = namespace + right_suffix
            if is_image(right):
                # Prefer the root namespace, then a stable lexical order.
                candidates.append((priority, len(namespace), TopicPair(left, right)))
    if not candidates:
        return None
    candidates.sort(key=lambda item: (item[0], item[1], item[2].left))
    return candidates[0][2]


def _event(
    event_type: str,
    observed_at: float,
    stamp_ns: int,
    event_id: str,
    **fields: Any,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "type": event_type,
        "event_id": event_id,
        "observed_at": float(observed_at),
        "stamp_ns": int(stamp_ns),
    }
    body.update(fields)
    return {"action": "pet_event", "event": body}


@dataclass
class _EyeState:
    seen: bool = False
    online: bool = False
    last_seen: float = 0.0
    width: int = 0
    height: int = 0
    encoding: str = ""


class CameraHealthMonitor:
    """Emit camera state changes without forwarding image payloads."""

    def __init__(self, stale_after: float = 1.0) -> None:
        if stale_after <= 0:
            raise ValueError("stale_after must be positive")
        self.stale_after = float(stale_after)
        self._eyes = {"left": _EyeState(), "right": _EyeState()}

    def status(self) -> str:
        online = sum(state.online for state in self._eyes.values())
        if online == 2:
            return "ready"
        if online:
            return "degraded"
        return "offline" if any(state.seen for state in self._eyes.values()) else "waiting"

    def observe(
        self,
        eye: str,
        now: float,
        stamp_ns: int,
        width: int,
        height: int,
        encoding: str,
    ) -> list[dict[str, Any]]:
        if eye not in self._eyes:
            raise ValueError("eye must be 'left' or 'right'")
        state = self._eyes[eye]
        was_online = state.online
        state.seen = True
        state.online = True
        state.last_seen = float(now)
        state.width = int(width)
        state.height = int(height)
        state.encoding = str(encoding)
        if was_online:
            return []
        return [
            _event(
                "health",
                now,
                stamp_ns,
                f"camera:{eye}:online:{stamp_ns}",
                status="ready",
                component=f"camera_{eye}",
                eye=eye,
                width=state.width,
                height=state.height,
                encoding=state.encoding,
            )
        ]

    def tick(self, now: float, stamp_ns: int) -> list[dict[str, Any]]:
        events = []
        for eye, state in self._eyes.items():
            if state.seen and state.online and now - state.last_seen > self.stale_after:
                state.online = False
                events.append(
                    _event(
                        "health",
                        now,
                        stamp_ns,
                        f"camera:{eye}:offline:{stamp_ns}",
                        status="degraded",
                        component=f"camera_{eye}",
                        eye=eye,
                        reason="image_timeout",
                    )
                )
        return events


GESTURE_NAMES = {
    0: "background",
    2: "thumb_up",
    3: "victory",
    4: "mute",
    5: "palm",
    11: "okay",
    12: "thumb_left",
    13: "thumb_right",
    14: "awesome",
    15: "pinch_move",
    16: "pinch_rotate_ccw",
    17: "pinch_rotate_cw",
}


def normalize_gesture(value: int | float | str | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip().lower().replace("-", "_").replace(" ", "_")
        aliases = {
            "ok": "okay",
            "palm_open": "palm",
            "thumbleft": "thumb_left",
            "thumbright": "thumb_right",
        }
        text = aliases.get(text, text)
        return text if text in set(GESTURE_NAMES.values()) else None
    try:
        return GESTURE_NAMES.get(int(value))
    except (TypeError, ValueError, OverflowError):
        return None


@dataclass(frozen=True)
class GestureActivation:
    kind: str
    track_id: int | None
    confidence: float | None
    observed_at: float
    stamp_ns: int
    stable_ms: int


class StableGestureGate:
    """Debounce gesture classifications and stop motion when the hand vanishes."""

    _MOTION = {"thumb_left", "thumb_right"}

    def __init__(
        self,
        stable_for: float = 0.25,
        lost_after: float = 0.4,
        repeat_every: float = 0.5,
    ) -> None:
        if stable_for < 0 or lost_after <= 0 or repeat_every <= 0:
            raise ValueError("invalid gesture timing")
        self.stable_for = float(stable_for)
        self.lost_after = float(lost_after)
        self.repeat_every = float(repeat_every)
        self._candidate: str | None = None
        self._candidate_track: int | None = None
        self._candidate_since = 0.0
        self._last_valid: float | None = None
        self._active: str | None = None
        self._last_emit: float | None = None

    def observe(
        self,
        value: int | float | str | None,
        now: float,
        stamp_ns: int,
        track_id: int | None = None,
        confidence: float | None = None,
    ) -> list[GestureActivation]:
        self.tick(now, stamp_ns)
        gesture = normalize_gesture(value)
        if confidence is not None and 0 < confidence < 0.5:
            gesture = None
        if gesture in (None, "background"):
            self._candidate = None
            self._candidate_track = None
            return self.tick(now, stamp_ns)

        self._last_valid = float(now)
        if gesture != self._candidate or track_id != self._candidate_track:
            self._candidate = gesture
            self._candidate_track = track_id
            self._candidate_since = float(now)
            return []
        if now - self._candidate_since < self.stable_for:
            return []
        if gesture == self._active:
            if (
                gesture not in self._MOTION
                or self._last_emit is None
                or now - self._last_emit < self.repeat_every
            ):
                return []
        self._active = gesture
        self._last_emit = float(now)
        return [
            GestureActivation(
                gesture,
                track_id,
                confidence,
                float(now),
                stamp_ns,
                round(self.stable_for * 1000),
            )
        ]

    def tick(self, now: float, stamp_ns: int) -> list[GestureActivation]:
        if self._last_valid is None or now - self._last_valid <= self.lost_after:
            return []
        self._candidate = None
        self._candidate_track = None
        self._active = None
        self._last_valid = None
        self._last_emit = None
        return []


class FoodGate:
    """Confirm a food object across several detector frames."""

    def __init__(
        self,
        confidence: float = 0.6,
        history_size: int = 5,
        required_hits: int = 3,
        ttl: float = 1.0,
    ) -> None:
        if not 0 <= confidence <= 1:
            raise ValueError("confidence must be between zero and one")
        if history_size < 1 or required_hits < 1 or required_hits > history_size:
            raise ValueError("invalid hit window")
        if ttl <= 0:
            raise ValueError("ttl must be positive")
        self.confidence = float(confidence)
        self.required_hits = int(required_hits)
        self.ttl = float(ttl)
        self._history: deque[bool] = deque(maxlen=int(history_size))
        self._available = False
        self._last_hit: float | None = None

    @property
    def is_available(self) -> bool:
        return self._available

    def observe(self, detections: Sequence[Mapping[str, Any]], now: float) -> bool:
        if self._last_hit is not None and now - self._last_hit > self.ttl:
            self._available = False
            self._history.clear()
        hit = any(
            str(item.get("label", "")).strip().lower() == "banana"
            and _finite_float(item.get("confidence"), default=-1.0) >= self.confidence
            for item in detections
        )
        self._history.append(hit)
        if hit:
            self._last_hit = float(now)
        became_available = not self._available and sum(self._history) >= self.required_hits
        if became_available:
            self._available = True
        return became_available

    def expired(self, now: float) -> bool:
        if not self._available or self._last_hit is None or now - self._last_hit <= self.ttl:
            return False
        self._available = False
        self._history.clear()
        self._last_hit = None
        return True

    def consume(self) -> None:
        self._available = False
        self._history.clear()
        self._last_hit = None


def _finite_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        return default
    return result if math.isfinite(result) else default


def _clean_detection(item: Mapping[str, Any]) -> dict[str, Any]:
    clean: dict[str, Any] = {
        "label": str(item.get("label", "")),
        "confidence": round(_finite_float(item.get("confidence")), 4),
    }
    if item.get("track_id") is not None:
        clean["track_id"] = int(item["track_id"])
    bbox = item.get("bbox")
    if isinstance(bbox, Sequence) and not isinstance(bbox, (str, bytes)) and len(bbox) == 4:
        clean["bbox"] = [int(value) for value in bbox]
    return clean


class PetVisionAdapter:
    """Turn camera, gesture and detector samples into stable UI events."""

    def __init__(
        self,
        camera_stale_after: float = 1.0,
        gesture_stable_for: float = 0.25,
        gesture_lost_after: float = 0.4,
        gesture_repeat_every: float = 0.5,
        object_confidence: float = 0.6,
        object_history_size: int = 5,
        object_required_hits: int = 3,
        food_ttl: float = 1.0,
    ) -> None:
        self.camera = CameraHealthMonitor(camera_stale_after)
        self.gestures = StableGestureGate(
            gesture_stable_for, gesture_lost_after, gesture_repeat_every
        )
        self.food = FoodGate(
            object_confidence,
            object_history_size,
            object_required_hits,
            food_ttl,
        )
        self._last_health = float("-inf")

    def image(
        self,
        eye: str,
        now: float,
        stamp_ns: int,
        width: int,
        height: int,
        encoding: str,
    ) -> list[dict[str, Any]]:
        return self.camera.observe(eye, now, stamp_ns, width, height, encoding)

    def gesture(
        self,
        value: int | float | str | None,
        now: float,
        stamp_ns: int,
        track_id: int | None = None,
        confidence: float | None = None,
    ) -> list[dict[str, Any]]:
        events = []
        for activation in self.gestures.observe(
            value, now, stamp_ns, track_id=track_id, confidence=confidence
        ):
            events.extend(self._gesture_events(activation))
        return events

    def objects(
        self,
        detections: Sequence[Mapping[str, Any]],
        now: float,
        stamp_ns: int,
        detector: str = "yolo",
    ) -> list[dict[str, Any]]:
        clean = [_clean_detection(item) for item in detections[:20]]
        self.food.observe(clean, now)
        events = []
        for index, item in enumerate(clean):
            label = item["label"].strip().lower()
            confidence = item["confidence"]
            if confidence < self.food.confidence:
                continue
            # Banana is the feed affordance, so suppress single-frame false
            # positives until the temporal gate has confirmed it.
            if label == "banana" and not self.food.is_available:
                continue
            event_fields = dict(item)
            event_fields["label"] = label
            event_fields["detector"] = detector
            events.append(
                _event(
                    "object",
                    now,
                    stamp_ns,
                    f"object:{detector}:{label}:{item.get('track_id', index)}:{stamp_ns}",
                    **event_fields,
                )
            )
        return events

    def tick(self, now: float, stamp_ns: int) -> list[dict[str, Any]]:
        events = self.camera.tick(now, stamp_ns)
        for activation in self.gestures.tick(now, stamp_ns):
            events.extend(self._gesture_events(activation))
        self.food.expired(now)
        if now - self._last_health >= 1.0:
            self._last_health = now
            events.append(_event("health", now, stamp_ns, f"health:{stamp_ns}",
                                 status=self.camera.status(), component="stereo"))
        return events

    def _gesture_events(self, activation: GestureActivation) -> list[dict[str, Any]]:
        names = {
            "thumb_up": "ThumbUp",
            "victory": "Victory",
            "mute": "Mute",
            "palm": "Palm",
            "okay": "Okay",
            "thumb_left": "ThumbLeft",
            "thumb_right": "ThumbRight",
            "awesome": "Awesome",
            "pinch_move": "PinchMove",
            "pinch_rotate_ccw": "PinchRotateAntiClockwise",
            "pinch_rotate_cw": "PinchRotateClockwise",
        }
        name = names.get(activation.kind)
        if name is None:
            return []
        fields: dict[str, Any] = {
            "name": name,
            "stable_ms": activation.stable_ms,
        }
        if activation.track_id is not None:
            fields["track_id"] = int(activation.track_id)
        # The current D-Robotics gesture node leaves Attribute.confidence at
        # zero.  Omit that unset value so the backend does not treat a valid
        # gesture as a zero-confidence result.
        if activation.confidence is not None and activation.confidence > 0:
            fields["confidence"] = round(float(activation.confidence), 4)
        return [
            _event(
                "gesture",
                activation.observed_at,
                activation.stamp_ns,
                f"gesture:{name}:{activation.track_id}:{activation.stamp_ns}",
                **fields,
            )
        ]


class UnixEventSink:
    """Send compact JSON datagrams to the Muse UI bridge."""

    def __init__(self, path: str = "/run/muse-ui/input.sock") -> None:
        self.path = path
        self._socket = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)

    def send(self, event: Mapping[str, Any]) -> None:
        payload = json.dumps(event, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self._socket.sendto(payload, self.path)

    def close(self) -> None:
        self._socket.close()

    def __enter__(self) -> "UnixEventSink":
        return self

    def __exit__(self, *_args: Any) -> None:
        self.close()
