"""ROS 2 bridge from D-Robotics perception messages to Muse pet events."""

from __future__ import annotations

import time
from typing import Any

from .adapter import PetVisionAdapter, TopicPair, UnixEventSink, select_stereo_topics
from .gesture_input import hand_only


try:
    import rclpy
    from ai_msgs.msg import PerceptionTargets
    from rclpy.node import Node
    from rclpy.qos import QoSProfile, ReliabilityPolicy
    from sensor_msgs.msg import CameraInfo, Image
except ImportError as exc:  # Keep the pure adapter importable on non-ROS hosts.
    rclpy = None
    _ROS_IMPORT_ERROR = exc
else:
    _ROS_IMPORT_ERROR = None


def _stamp_ns(message: Any, fallback: int) -> int:
    stamp = getattr(getattr(message, "header", None), "stamp", None)
    if stamp is None:
        return fallback
    value = int(getattr(stamp, "sec", 0)) * 1_000_000_000 + int(
        getattr(stamp, "nanosec", 0)
    )
    return value or fallback


def _best_gesture(message: Any) -> tuple[float | None, int | None, float | None]:
    candidates = []
    for target in getattr(message, "targets", ()):
        for attribute in getattr(target, "attributes", ()):
            if str(getattr(attribute, "type", "")).lower() != "gesture":
                continue
            confidence = float(getattr(attribute, "confidence", 0.0))
            candidates.append(
                (
                    confidence,
                    float(getattr(attribute, "value", 0.0)),
                    int(getattr(target, "track_id", 0)),
                )
            )
    if not candidates:
        return None, None, None
    confidence, value, track_id = max(candidates, key=lambda item: item[0])
    return value, track_id, confidence if confidence > 0 else None


def _detections(message: Any) -> list[dict[str, Any]]:
    detections = []
    for target in getattr(message, "targets", ()):
        rois = list(getattr(target, "rois", ()))
        roi = max(rois, key=lambda item: float(getattr(item, "confidence", 0.0))) if rois else None
        label = str(getattr(target, "type", ""))
        if roi is not None and not label:
            label = str(getattr(roi, "type", ""))
        detection: dict[str, Any] = {
            "label": label,
            "track_id": int(getattr(target, "track_id", 0)),
            "confidence": float(getattr(roi, "confidence", 0.0)) if roi is not None else 0.0,
        }
        if roi is not None:
            rect = getattr(roi, "rect", None)
            if rect is not None:
                detection["bbox"] = [
                    int(getattr(rect, "x_offset", 0)),
                    int(getattr(rect, "y_offset", 0)),
                    int(getattr(rect, "width", 0)),
                    int(getattr(rect, "height", 0)),
                ]
        detections.append(detection)
    return detections


def _extra_detectors(specification: str) -> list[tuple[str, str]]:
    """Parse ``name:/topic,name2:/topic2`` detector subscriptions."""

    result = []
    for item in specification.split(","):
        item = item.strip()
        if not item:
            continue
        if ":" in item:
            name, topic = item.split(":", 1)
        else:
            name, topic = "detector", item
        name = name.strip() or "detector"
        topic = topic.strip()
        if topic:
            result.append((name, topic if topic.startswith("/") else "/" + topic))
    return result


def message_is_fresh(message: Any, now_ns: int, max_age_sec: float = 1.0) -> bool:
    stamp = _stamp_ns(message, now_ns)
    return -500_000_000 <= now_ns - stamp <= max_age_sec * 1_000_000_000


def health_topics(left: str, right: str, compact_left: str,
                  compact_right: str) -> tuple[TopicPair, bool]:
    if bool(compact_left) != bool(compact_right):
        raise ValueError("Both compact camera health topics must be supplied")
    if compact_left:
        return TopicPair(compact_left, compact_right), True
    return TopicPair(left, right), False


if rclpy is not None:

    class MusePetVisionNode(Node):
        """Watch stereo health and bridge stable perception events to Muse UI."""

        def __init__(self) -> None:
            super().__init__("muse_pet_vision")
            self.declare_parameter("left_topic", "/image_left_raw")
            self.declare_parameter("right_topic", "/image_right_raw")
            self.declare_parameter("left_health_topic", "")
            self.declare_parameter("right_health_topic", "")
            self.declare_parameter("gesture_topic", "/muse/gestures")
            self.declare_parameter("hand_landmark_topic", "")
            self.declare_parameter("gesture_input_topic", "")
            self.declare_parameter("object_topic", "/muse/objects")
            self.declare_parameter("extra_detector_topics", "")
            self.declare_parameter("socket_path", "/run/muse-ui/input.sock")
            self.declare_parameter("auto_discover", False)
            self.declare_parameter("discovery_period_sec", 2.0)
            self.declare_parameter("camera_stale_sec", 1.0)
            self.declare_parameter("gesture_stable_sec", 0.25)
            self.declare_parameter("gesture_lost_sec", 0.4)
            self.declare_parameter("gesture_repeat_sec", 0.5)
            self.declare_parameter("object_confidence", 0.6)
            self.declare_parameter("object_history_size", 5)
            self.declare_parameter("object_required_hits", 3)
            self.declare_parameter("food_ttl_sec", 1.0)

            self._preferred_pair, self._compact_health = health_topics(
                self._text("left_topic"), self._text("right_topic"),
                self._text("left_health_topic"), self._text("right_health_topic"))
            self._image_qos = QoSProfile(depth=1, reliability=ReliabilityPolicy.BEST_EFFORT)
            self._adapter = PetVisionAdapter(
                camera_stale_after=self._number("camera_stale_sec"),
                gesture_stable_for=self._number("gesture_stable_sec"),
                gesture_lost_after=self._number("gesture_lost_sec"),
                gesture_repeat_every=self._number("gesture_repeat_sec"),
                object_confidence=self._number("object_confidence"),
                object_history_size=self._integer("object_history_size"),
                object_required_hits=self._integer("object_required_hits"),
                food_ttl=self._number("food_ttl_sec"),
            )
            self._sink = UnixEventSink(self._text("socket_path"))
            self._last_sink_warning = 0.0
            self._left_size = (0, 0)
            self._last_hand_report = 0.0
            self._hand_stats = dict(frames=0, targets=0, hands=0, valid=0, rejected=0)
            self._hand_sub = None
            self._hand_pub = None
            hand_topic = self._text("hand_landmark_topic")
            input_topic = self._text("gesture_input_topic")
            if bool(hand_topic) != bool(input_topic) or (hand_topic and hand_topic == input_topic):
                raise ValueError("Hand landmark and gesture input topics must be distinct and supplied together")
            if hand_topic:
                self._hand_pub = self.create_publisher(PerceptionTargets, input_topic, 10)
                self._hand_sub = self.create_subscription(
                    PerceptionTargets, hand_topic, self._on_hand_landmarks, 10)
            self._left_sub = None
            self._right_sub = None
            self._image_pair: TopicPair | None = None
            self._set_image_topics(self._preferred_pair)

            self._gesture_sub = self.create_subscription(
                PerceptionTargets,
                self._text("gesture_topic"),
                self._on_gesture,
                10,
            )
            self._detector_subscriptions = []
            detector_specs = [("yolo", self._text("object_topic"))]
            detector_specs.extend(_extra_detectors(self._text("extra_detector_topics")))
            seen_topics = set()
            for detector, topic in detector_specs:
                if topic in seen_topics:
                    continue
                seen_topics.add(topic)
                subscription = self.create_subscription(
                    PerceptionTargets,
                    topic,
                    lambda message, name=detector: self._on_objects(message, name),
                    10,
                )
                self._detector_subscriptions.append(subscription)

            self._tick_timer = self.create_timer(0.1, self._on_tick)
            self._discovery_timer = None
            if bool(self.get_parameter("auto_discover").value):
                period = max(0.5, self._number("discovery_period_sec"))
                self._discovery_timer = self.create_timer(period, self._discover_topics)

            self.get_logger().info(
                "Muse vision bridge: left=%s right=%s gesture=%s detectors=%s socket=%s"
                % (
                    self._image_pair.left,
                    self._image_pair.right,
                    self._text("gesture_topic"),
                    ",".join(topic for _, topic in detector_specs),
                    self._text("socket_path"),
                )
            )

        def _text(self, name: str) -> str:
            return str(self.get_parameter(name).value)

        def _number(self, name: str) -> float:
            return float(self.get_parameter(name).value)

        def _integer(self, name: str) -> int:
            return int(self.get_parameter(name).value)

        def _set_image_topics(self, pair: TopicPair) -> None:
            if pair == self._image_pair:
                return
            if self._left_sub is not None:
                self.destroy_subscription(self._left_sub)
            if self._right_sub is not None:
                self.destroy_subscription(self._right_sub)
            self._left_sub = self.create_subscription(
                CameraInfo if self._compact_health else Image,
                pair.left,
                lambda message: self._on_image("left", message),
                self._image_qos,
            )
            self._right_sub = self.create_subscription(
                CameraInfo if self._compact_health else Image,
                pair.right,
                lambda message: self._on_image("right", message),
                self._image_qos,
            )
            self._image_pair = pair
            self.get_logger().info(f"Stereo image topics: {pair.left}, {pair.right}")

        def _discover_topics(self) -> None:
            if self._compact_health:
                return  # Never replace a metadata stream with raw pixel messages.
            if (
                self._image_pair is not None
                and self.count_publishers(self._image_pair.left) > 0
                and self.count_publishers(self._image_pair.right) > 0
            ):
                return
            graph = dict(self.get_topic_names_and_types())
            selected = select_stereo_topics(
                graph,
                self._preferred_pair.left,
                self._preferred_pair.right,
            )
            if selected is not None:
                self._set_image_topics(selected)

        def _clock_ns(self) -> int:
            return int(self.get_clock().now().nanoseconds)

        def _on_image(self, eye: str, message: Any) -> None:
            now = time.monotonic()
            fallback = self._clock_ns()
            if not message_is_fresh(message, fallback):
                return
            if eye == "left":
                self._left_size = (int(message.width), int(message.height))
            self._emit(
                self._adapter.image(
                    eye,
                    now,
                    _stamp_ns(message, fallback),
                    int(message.width),
                    int(message.height),
                    str(getattr(message, "encoding", "camera_info")),
                )
            )

        def _on_hand_landmarks(self, message: Any) -> None:
            if not message_is_fresh(message, self._clock_ns()):
                return
            normalized, stats = hand_only(message)
            self._hand_pub.publish(normalized)
            self._hand_stats["frames"] += 1
            for key, value in stats.items():
                self._hand_stats[key] += value
            now = time.monotonic()
            if now - self._last_hand_report >= 5.0:
                self.get_logger().info(f"Gesture input (interval totals): {self._hand_stats}")
                self._hand_stats = dict.fromkeys(self._hand_stats, 0)
                self._last_hand_report = now

        def _on_gesture(self, message: Any) -> None:
            now = time.monotonic()
            if not message_is_fresh(message, self._clock_ns()):
                return
            stamp_ns = _stamp_ns(message, self._clock_ns())
            motion_events = self._adapter.hand_motion(message, *self._left_size, now, stamp_ns)
            for event in motion_events:
                if event["event"]["type"] == "gesture":
                    self.get_logger().info(f"Palm approach: {event['event']}")
            self._emit(motion_events)
            value, track_id, confidence = _best_gesture(message)
            self._emit(
                self._adapter.gesture(
                    value,
                    now,
                    stamp_ns,
                    track_id=track_id,
                    confidence=confidence,
                )
            )

        def _on_objects(self, message: Any, detector: str) -> None:
            now = time.monotonic()
            if not message_is_fresh(message, self._clock_ns()):
                return
            stamp_ns = _stamp_ns(message, self._clock_ns())
            self._emit(
                self._adapter.objects(
                    _detections(message), now, stamp_ns, detector=detector
                )
            )

        def _on_tick(self) -> None:
            self._emit(self._adapter.tick(time.monotonic(), self._clock_ns()))

        def _emit(self, events: list[dict[str, Any]]) -> None:
            for event in events:
                try:
                    self._sink.send(event)
                except OSError as exc:
                    now = time.monotonic()
                    if now - self._last_sink_warning >= 5.0:
                        self.get_logger().warning(
                            f"Cannot send to {self._sink.path}: {exc}"
                        )
                        self._last_sink_warning = now

        def destroy_node(self) -> bool:
            self._sink.close()
            return super().destroy_node()


def main(args: list[str] | None = None) -> None:
    if rclpy is None:
        raise RuntimeError(
            "ROS 2 Python packages are unavailable. Source the TROS setup before "
            "running muse_pet_vision_node."
        ) from _ROS_IMPORT_ERROR
    rclpy.init(args=args)
    node = MusePetVisionNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
