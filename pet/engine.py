"""Pure state machine for the RDK X5 desktop pet.

The engine has no filesystem, socket, ROS or asyncio dependencies.  Its clock is
injected so timers and event expiry can be tested without sleeping.
"""
from __future__ import annotations

import math
import shlex
import time
from collections.abc import Callable, Mapping
from typing import Any


class PetCommandError(ValueError):
    """A local pet command is malformed or cannot be applied."""


class PetEngine:
    """Own the pet state and turn commands or perception events into actions."""

    GESTURES = {
        "palm": "Palm",
        "thumbleft": "ThumbLeft",
        "thumbright": "ThumbRight",
        "okay": "Okay",
        "ok": "Okay",
        "thumbup": "ThumbUp",
        "victory": "Victory",
    }
    GESTURE_ACTIONS = {
        "Palm": "wake",
        "ThumbLeft": "move_left",
        "ThumbRight": "move_right",
        "Okay": "feed",
        "ThumbUp": "pet",
        "Victory": "find",
    }
    DEFAULT_COOLDOWNS = {
        "Palm": 1.0,
        "ThumbLeft": 0.35,
        "ThumbRight": 0.35,
        "Okay": 3.0,
        "ThumbUp": 1.0,
        "Victory": 2.0,
    }

    def __init__(
        self,
        *,
        clock: Callable[[], float] = time.monotonic,
        event_ttl: float = 1.5,
        min_stable_ms: int = 250,
        min_confidence: float = 0.5,
        movement_hold: float = 0.9,
        cooldowns: Mapping[str, float] | None = None,
    ) -> None:
        self._clock = clock
        self.event_ttl = float(event_ttl)
        self.min_stable_ms = int(min_stable_ms)
        self.min_confidence = float(min_confidence)
        self.movement_hold = float(movement_hold)
        self.cooldowns = dict(self.DEFAULT_COOLDOWNS)
        if cooldowns:
            self.cooldowns.update(cooldowns)

        now = float(clock())
        if not math.isfinite(now):
            raise ValueError("clock must return a finite monotonic value")
        self._last_now = now
        self._seen_events: dict[str, float] = {}
        self._last_event: dict[str, float] = {}
        self._motion_until: float | None = None
        self._activity_until: float | None = None

        self.awake = False
        self.activity = "sleeping"
        self.position = 50
        self.direction = "stop"
        self.happiness = 50
        self.hunger = 20
        self.energy = 80
        self.last_action = "boot"
        self.last_gesture = ""
        self.last_food = ""
        self.pending_food = ""
        self._pending_food_until: float | None = None

        self.timer_state = "idle"
        self.timer_duration = 0
        self._timer_deadline: float | None = None

        self.find_state = "idle"
        self.find_target = ""
        self.last_seen_object = ""
        self.vision = "waiting"
        self._vision_seen: float | None = None
        self._camera_status: dict[str, str] = {}

    def _now(self, supplied: float | None = None) -> float:
        value = float(self._clock() if supplied is None else supplied)
        if not math.isfinite(value):
            raise PetCommandError("time must be finite")
        # A monotonic clock should never move backwards.  Clamping also keeps an
        # injected or external event timestamp from increasing timer remaining.
        value = max(value, self._last_now)
        self._last_now = value
        return value

    def _resting_activity(self) -> str:
        if not self.awake:
            return "sleeping"
        if self.direction != "stop":
            return "moving"
        if self.timer_state == "running":
            return "focus"
        if self.find_state == "searching":
            return "finding"
        return "idle"

    def _tick_at(self, now: float) -> None:
        if self._vision_seen is not None and now - self._vision_seen > 3.0:
            self.vision = "offline"
        if self._motion_until is not None and now >= self._motion_until:
            self._motion_until = None
            self.direction = "stop"
            if self.activity == "moving":
                self.activity = self._resting_activity()

        if self._pending_food_until is not None and now >= self._pending_food_until:
            self._pending_food_until = None
            self.pending_food = ""

        if self._timer_deadline is not None and now >= self._timer_deadline:
            self._timer_deadline = None
            self.timer_state = "complete"
            self.awake = True
            self.happiness = min(100, self.happiness + 10)
            self.hunger = min(100, self.hunger + 5)
            self.energy = max(0, self.energy - 5)
            self.activity = "happy"
            self.last_action = "timer_done"
            self._activity_until = now + 3.0

        if self._activity_until is not None and now >= self._activity_until:
            self._activity_until = None
            self.activity = self._resting_activity()

        oldest = now - max(10.0, self.event_ttl * 4)
        self._seen_events = {key: seen for key, seen in self._seen_events.items()
                             if seen >= oldest}

    def tick(self, now: float | None = None) -> dict[str, Any]:
        current = self._now(now)
        self._tick_at(current)
        return self._snapshot(current)

    def _snapshot(self, now: float) -> dict[str, Any]:
        remaining = 0
        if self._timer_deadline is not None:
            remaining = max(0, math.ceil(self._timer_deadline - now))
        current_task = ""
        if self.timer_state == "running":
            current_task = "timer"
        elif self.find_state == "searching":
            current_task = "find"
        return {
            "awake": self.awake,
            "mode": self.activity,
            "position": self.position,
            "direction": self.direction,
            "happiness": self.happiness,
            "hunger": self.hunger,
            "energy": self.energy,
            "last_action": self.last_action,
            "last_gesture": self.last_gesture,
            "last_food": self.last_food,
            "pending_food": self.pending_food,
            "timer_state": self.timer_state,
            "timer_remaining": remaining,
            "timer_duration": self.timer_duration,
            "find_state": self.find_state,
            "find_target": self.find_target,
            "last_seen_object": self.last_seen_object,
            "current_task": current_task,
            "vision": self.vision,
        }

    def status(self) -> dict[str, Any]:
        return self.tick()

    def state_fields(self) -> dict[str, str]:
        """Return the line-protocol fields written by the backend."""
        state = self.status()
        timer = "off"
        if state["timer_state"] == "running":
            minutes, seconds = divmod(state["timer_remaining"], 60)
            timer = f"{minutes:02}:{seconds:02}"
        elif state["timer_state"] == "complete":
            timer = "done"
        elif state["timer_state"] == "cancelled":
            timer = "cancelled"
        pet_object = state["pending_food"] or state["last_seen_object"] or "none"
        pet_gesture = state["last_gesture"] or "none"
        return {
            "pet_awake": "true" if state["awake"] else "false",
            "pet_mode": str(state["mode"]),
            "pet_position": str(state["position"]),
            "pet_x": str((state["position"] - 50) * 2),
            "pet_direction": str(state["direction"]),
            "pet_happiness": str(state["happiness"]),
            "pet_hunger": str(state["hunger"]),
            "pet_energy": str(state["energy"]),
            "pet_object": str(pet_object),
            "pet_gesture": str(pet_gesture),
            "pet_timer": timer,
            "pet_app": str(state["current_task"] or "pet"),
            "vision": str(state["vision"]),
            "pet_last_action": str(state["last_action"]),
            "pet_last_gesture": str(state["last_gesture"]),
            "pet_last_food": str(state["last_food"]),
            "pet_pending_food": str(state["pending_food"]),
            "pet_timer_state": str(state["timer_state"]),
            "pet_timer_remaining": str(state["timer_remaining"]),
            "pet_timer_duration": str(state["timer_duration"]),
            "pet_find_state": str(state["find_state"]),
            "pet_find_target": str(state["find_target"]),
            "pet_last_seen_object": str(state["last_seen_object"]),
            "pet_current_task": str(state["current_task"]),
        }

    def wake(self, *, now: float | None = None) -> dict[str, Any]:
        current = self._now(now)
        self._tick_at(current)
        self.awake = True
        self.activity = self._resting_activity()
        self.last_action = "wake"
        self._activity_until = None
        return self._snapshot(current)

    def sleep(self, *, now: float | None = None) -> dict[str, Any]:
        current = self._now(now)
        self._tick_at(current)
        self.awake = False
        self.direction = "stop"
        self._motion_until = None
        self._activity_until = None
        self.activity = "sleeping"
        self.last_action = "sleep"
        return self._snapshot(current)

    def pet(self, *, now: float | None = None) -> dict[str, Any]:
        current = self._now(now)
        self._tick_at(current)
        self.awake = True
        self.happiness = min(100, self.happiness + 5)
        self.activity = "happy"
        self.last_action = "pet"
        self._activity_until = current + 2.0
        return self._snapshot(current)

    def move(self, direction: str, *, now: float | None = None) -> dict[str, Any]:
        current = self._now(now)
        self._tick_at(current)
        direction = str(direction).strip().lower()
        if direction not in ("left", "right", "stop"):
            raise PetCommandError("direction must be left, right or stop")
        if direction != "stop" and not self.awake:
            raise PetCommandError("pet is sleeping; wake it before moving")
        self.direction = direction
        if direction == "stop":
            self._motion_until = None
            self.activity = self._resting_activity()
        else:
            delta = -5 if direction == "left" else 5
            self.position = max(0, min(100, self.position + delta))
            self.hunger = min(100, self.hunger + 1)
            self.energy = max(0, self.energy - 1)
            self._motion_until = current + self.movement_hold
            self.activity = "moving"
        self.last_action = f"move_{direction}"
        return self._snapshot(current)

    def feed(self, food: str, *, now: float | None = None) -> dict[str, Any]:
        current = self._now(now)
        self._tick_at(current)
        food = str(food).strip().lower()
        if not food:
            raise PetCommandError("food is required")
        self.awake = True
        self.direction = "stop"
        self._motion_until = None
        self.last_food = food
        self.pending_food = ""
        self._pending_food_until = None
        self.happiness = min(100, self.happiness + 15)
        self.hunger = max(0, self.hunger - 25)
        self.energy = min(100, self.energy + 5)
        self.activity = "eating"
        self.last_action = f"feed_{food}"
        self._activity_until = current + 2.5
        return self._snapshot(current)

    def timer_start(self, seconds: float = 25 * 60, *,
                    now: float | None = None) -> dict[str, Any]:
        current = self._now(now)
        self._tick_at(current)
        try:
            duration = float(seconds)
        except (TypeError, ValueError) as exc:
            raise PetCommandError("timer duration must be a number") from exc
        if not math.isfinite(duration) or duration < 1 or duration > 24 * 60 * 60:
            raise PetCommandError("timer duration must be between 1 second and 24 hours")
        self.timer_duration = math.ceil(duration)
        self._timer_deadline = current + duration
        self.timer_state = "running"
        self.awake = True
        self.activity = "focus"
        self.last_action = "timer_start"
        self._activity_until = None
        return self._snapshot(current)

    def timer_cancel(self, *, now: float | None = None) -> dict[str, Any]:
        current = self._now(now)
        self._tick_at(current)
        self._timer_deadline = None
        self.timer_state = "cancelled"
        self.timer_duration = 0
        self.last_action = "timer_cancel"
        self.activity = self._resting_activity()
        return self._snapshot(current)

    def find(self, target: str = "banana", *, now: float | None = None) -> dict[str, Any]:
        current = self._now(now)
        self._tick_at(current)
        target = str(target).strip().lower()
        if not target:
            raise PetCommandError("find target is required")
        self.awake = True
        self.find_target = target
        self.find_state = "searching"
        self.activity = "finding"
        self.last_action = f"find_{target}"
        self._activity_until = None
        return self._snapshot(current)

    def _observe_object(self, label: str, confidence: float, now: float) -> tuple[bool, str]:
        label = label.strip().lower()
        if not label:
            return False, "missing_label"
        if not math.isfinite(confidence) or confidence < self.min_confidence:
            return False, "low_confidence"
        self.last_seen_object = label
        self.last_action = f"see_{label}"
        if label == "banana":
            self.pending_food = label
            self._pending_food_until = now + 1.0
        if self.find_state == "searching" and label == self.find_target:
            self.find_state = "found"
            self.awake = True
            self.happiness = min(100, self.happiness + 10)
            self.activity = "happy"
            self.last_action = f"found_{label}"
            self._activity_until = now + 3.0
        return True, "accepted"

    def _gesture(self, name: str, now: float) -> tuple[bool, str, str]:
        action = self.GESTURE_ACTIONS[name]
        if action == "wake":
            self.wake(now=now)
        elif action == "move_left":
            try:
                self.move("left", now=now)
            except PetCommandError as exc:
                return False, "sleeping", action
        elif action == "move_right":
            try:
                self.move("right", now=now)
            except PetCommandError as exc:
                return False, "sleeping", action
        elif action == "feed":
            if not self.pending_food:
                return False, "no_pending_food", action
            self.feed(self.pending_food, now=now)
        elif action == "pet":
            self.pet(now=now)
        elif action == "find":
            self.find("banana", now=now)
        self.last_gesture = name
        return True, "accepted", action

    def handle_event(self, event: Mapping[str, Any]) -> dict[str, Any]:
        """Consume a fresh, stable perception event.

        Supported events are ``gesture`` with ``name`` and ``object`` with
        ``label``.  Producers may include a host-monotonic ``observed_at``, an
        ``event_id``, ``stable_ms`` and ``confidence``.
        """
        if not isinstance(event, Mapping):
            raise PetCommandError("event must be an object")
        now = self._now()
        self._tick_at(now)
        observed = event.get("observed_at", event.get("timestamp", now))
        try:
            observed = float(observed)
        except (TypeError, ValueError):
            return self._event_result(False, "invalid_timestamp", "", now)
        if not math.isfinite(observed) or observed > now + 0.5:
            return self._event_result(False, "invalid_timestamp", "", now)
        if now - observed > self.event_ttl:
            return self._event_result(False, "stale", "", now)

        event_id = str(event.get("event_id", event.get("id", ""))).strip()
        if event_id:
            if event_id in self._seen_events:
                return self._event_result(False, "duplicate", "", now)
            self._seen_events[event_id] = now

        kind = str(event.get("type", event.get("kind", ""))).strip().lower()
        if kind == "gesture":
            raw_name = str(event.get("name", event.get("gesture", ""))).strip()
            name = self.GESTURES.get(raw_name.replace("_", "").replace("-", "").lower())
            if not name:
                return self._event_result(False, "unknown_gesture", "", now)
            try:
                stable_ms = float(event.get("stable_ms", self.min_stable_ms))
                confidence = float(event.get("confidence", 1.0))
            except (TypeError, ValueError):
                return self._event_result(False, "invalid_measurement", "", now)
            if not math.isfinite(stable_ms) or stable_ms < self.min_stable_ms:
                return self._event_result(False, "unstable", "", now)
            if not math.isfinite(confidence) or confidence < self.min_confidence:
                return self._event_result(False, "low_confidence", "", now)
            last = self._last_event.get(f"gesture:{name}")
            if last is not None and now - last < self.cooldowns[name]:
                return self._event_result(False, "cooldown", self.GESTURE_ACTIONS[name], now)
            accepted, reason, action = self._gesture(name, now)
            if accepted:
                self._last_event[f"gesture:{name}"] = now
            return self._event_result(accepted, reason, action, now)

        if kind == "object":
            label = str(event.get("label", "")).strip().lower()
            try:
                confidence = float(event.get("confidence", 1.0))
            except (TypeError, ValueError):
                return self._event_result(False, "invalid_measurement", "observe", now)
            key = f"object:{label}"
            last = self._last_event.get(key)
            if last is not None and now - last < 0.4:
                return self._event_result(False, "cooldown", "observe", now)
            accepted, reason = self._observe_object(label, confidence, now)
            if accepted:
                self._last_event[key] = now
            return self._event_result(accepted, reason, "observe", now)

        if kind in ("health", "vision"):
            status = str(event.get("status", event.get("state", ""))).strip().lower()
            if not status or len(status) > 32 or not all(
                    char.isalnum() or char in "_-" for char in status):
                return self._event_result(False, "invalid_status", "vision", now)
            self._vision_seen = now
            component = str(event.get("component", ""))
            if component in ("camera_left", "camera_right"):
                self._camera_status[component] = status
                self.vision = ("ready" if all(self._camera_status.get(eye) == "ready"
                    for eye in ("camera_left", "camera_right")) else "degraded")
            else:
                self.vision = status
            return self._event_result(True, "accepted", "vision", now)

        return self._event_result(False, "unknown_event", "", now)

    def _event_result(self, accepted: bool, reason: str, action: str,
                      now: float) -> dict[str, Any]:
        return {
            "accepted": accepted,
            "reason": reason,
            "action": action,
            "state": self._snapshot(now),
        }

    def command(self, name: str, **params: Any) -> dict[str, Any]:
        """Dispatch a trusted local command and return the new state."""
        try:
            words = shlex.split(str(name))
        except ValueError as exc:
            raise PetCommandError(f"invalid pet command: {exc}") from exc
        if not words:
            raise PetCommandError("unknown pet command: <empty>")
        name, positional = words[0].lower(), words[1:]
        if name == "wake":
            if positional:
                raise PetCommandError("wake takes no arguments")
            return self.wake()
        if name == "sleep":
            if positional:
                raise PetCommandError("sleep takes no arguments")
            return self.sleep()
        if name == "pet":
            if positional:
                raise PetCommandError("pet takes no arguments")
            return self.pet()
        if name == "move":
            direction = params.get("direction", positional[0] if positional else "")
            if len(positional) > 1:
                raise PetCommandError("move takes one direction")
            return self.move(direction)
        if name == "feed":
            food = params.get("food", positional[0] if positional else
                              (self.pending_food or "banana"))
            if len(positional) > 1:
                raise PetCommandError("feed takes one food")
            return self.feed(food)
        if name == "timer":
            operation = str(params.get(
                "operation", positional[0] if positional else "start")).strip().lower()
            if operation == "start":
                if "seconds" in params:
                    seconds = params["seconds"]
                else:
                    try:
                        minutes = params.get(
                            "minutes", positional[1] if len(positional) > 1 else 25)
                        seconds = float(minutes) * 60
                    except (TypeError, ValueError) as exc:
                        raise PetCommandError("timer minutes must be a number") from exc
                if len(positional) > 2:
                    raise PetCommandError("timer start takes one duration")
                return self.timer_start(seconds)
            if operation in ("cancel", "stop"):
                if len(positional) > 1:
                    raise PetCommandError("timer cancel takes no duration")
                return self.timer_cancel()
            if operation == "status":
                if len(positional) > 1:
                    raise PetCommandError("timer status takes no duration")
                return self.status()
            raise PetCommandError("timer operation must be start, cancel or status")
        if name == "find":
            target = params.get("target", positional[0] if positional else "banana")
            if len(positional) > 1:
                raise PetCommandError("find takes one target")
            return self.find(target)
        if name == "status":
            if positional:
                raise PetCommandError("status takes no arguments")
            return self.status()
        raise PetCommandError(f"unknown pet command: {name or '<empty>'}")
