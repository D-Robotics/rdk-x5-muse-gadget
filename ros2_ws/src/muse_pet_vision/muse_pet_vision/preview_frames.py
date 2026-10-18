"""Frame-matched overlays for the web viewer and the native SPI screen."""
from collections import deque
import copy
import os
from pathlib import Path
import time

from .adapter import normalize_gesture


def stamp_ns(message):
    return message.header.stamp.sec * 1_000_000_000 + message.header.stamp.nanosec


class OverlayCache:
    """Allow sub-millisecond timestamp rounding, never a neighbouring frame."""
    def __init__(self, tolerance_ns=1_000_000, ttl=2.0, limit=128):
        self.tolerance_ns, self.ttl, self.limit = tolerance_ns, ttl, limit
        self.items = {}

    def add(self, message, now):
        self.items[stamp_ns(message)] = (now, message)
        self.expire(now)
        while len(self.items) > self.limit:
            self.items.pop(next(iter(self.items)))

    def expire(self, now):
        self.items = {key: value for key, value in self.items.items()
                      if now - value[0] <= self.ttl}

    def match(self, stamp, now):
        self.expire(now)
        if not self.items:
            return None
        nearest = min(self.items, key=lambda key: abs(key - stamp))
        return self.items[nearest][1] if abs(nearest - stamp) <= self.tolerance_ns else None


def render_screen(jpeg, messages):
    import cv2
    import numpy as np

    # Hardware JPEG dimensions are multiples of 16. Decode at quarter size
    # for the 224px camera area instead of decoding a full 1088x1280 image.
    source = cv2.imdecode(np.frombuffer(jpeg, dtype=np.uint8), cv2.IMREAD_REDUCED_COLOR_4)
    if source is None:
        raise ValueError("Invalid preview JPEG")
    height, width = (dimension * 4 for dimension in source.shape[:2])
    scale = min(224 / width, 256 / height)
    w, h = max(1, round(width * scale)), max(1, round(height * scale))
    canvas = np.zeros((256, 480, 3), dtype=np.uint8)
    offset_y = (256 - h) // 2
    canvas[offset_y:offset_y + h, :w] = cv2.resize(source, (w, h))
    labels, gestures = set(), set()
    for index, message in enumerate(messages):
        if message is None:
            continue
        color = (140, 255, 120) if index == 0 else (255, 190, 110)
        for target in message.targets:
            for attribute in target.attributes:
                if attribute.type == "gesture":
                    name = normalize_gesture(attribute.value)
                    if name and name != "background":
                        gestures.add(name.replace('_', ' ').title())
            for roi in target.rois:
                rect = roi.rect
                x, y = round(rect.x_offset * scale), round(rect.y_offset * scale) + offset_y
                x2, y2 = x + round(rect.width * scale), y + round(rect.height * scale)
                x, x2 = max(0, min(w - 1, x)), max(0, min(w - 1, x2))
                y, y2 = max(offset_y, min(offset_y + h - 1, y)), max(offset_y, min(offset_y + h - 1, y2))
                cv2.rectangle(canvas, (x, y), (x2, y2), color, 1)
                label = target.type or roi.type
                cv2.putText(canvas, label[:18], (x, max(12, y - 3)),
                            cv2.FONT_HERSHEY_SIMPLEX, .35, color, 1, cv2.LINE_AA)
                if index == 0:
                    labels.add(label)
            for group in target.points:
                if group.type != "hand_kps":
                    continue
                points = [(round(p.x * scale), round(p.y * scale) + offset_y)
                          for p in group.point]
                for finger in ((0, 1, 2, 3, 4), (0, 5, 6, 7, 8),
                               (0, 9, 10, 11, 12), (0, 13, 14, 15, 16),
                               (0, 17, 18, 19, 20)):
                    for a, b in zip(finger, finger[1:]):
                        if b < len(points):
                            cv2.line(canvas, points[a], points[b], color, 1)
                for point in points:
                    cv2.circle(canvas, point, 2, (150, 120, 255), -1)
    def text(value, y, color=(225, 225, 235), size=.48):
        cv2.putText(canvas, value[:25], (238, y), cv2.FONT_HERSHEY_SIMPLEX,
                    size, color, 1, cv2.LINE_AA)
    text("OBJECTS", 24, (140, 255, 120))
    for i, label in enumerate(sorted(labels)[:4] or ["--"]):
        text(label, 50 + i * 21)
    text("GESTURE", 156, (255, 190, 110))
    for i, gesture in enumerate(sorted(gestures)[:2] or ["--"]):
        text(gesture, 182 + i * 22)
    return canvas


def main(args=None):
    import cv2
    import rclpy
    from ai_msgs.msg import PerceptionTargets
    from rclpy.node import Node
    from rclpy.qos import qos_profile_sensor_data
    from sensor_msgs.msg import CompressedImage
    cv2.setNumThreads(1)

    class PreviewFrames(Node):
        def __init__(self):
            super().__init__("muse_preview_frames")
            for name, default in (("object_topic", "/muse/objects"),
                                  ("gesture_topic", "/muse/gestures"),
                                  ("screen_path", "/run/muse-pet-preview/vision.bmp")):
                self.declare_parameter(name, default)
            self.pending = deque(maxlen=16)
            self.caches = [OverlayCache(), OverlayCache()]
            self.publishers_ = [self.create_publisher(PerceptionTargets,
                f"/muse/preview/{kind}", 10) for kind in ("objects", "gestures")]
            self.subs = [self.create_subscription(CompressedImage, "/muse/preview/jpeg",
                lambda msg: self.pending.append((time.monotonic(), msg)), qos_profile_sensor_data)]
            for i, parameter in enumerate(("object_topic", "gesture_topic")):
                self.subs.append(self.create_subscription(PerceptionTargets,
                    str(self.get_parameter(parameter).value),
                    lambda msg, i=i: self.caches[i].add(msg, time.monotonic()), 10))
            self.last_screen = 0.0
            self.path = Path(str(self.get_parameter("screen_path").value))
            self.create_timer(.05, self.tick)

        def tick(self):
            now = time.monotonic()
            while self.pending and now - self.pending[0][0] >= .25:
                received, frame = self.pending.popleft()
                if now - received > 2.0:
                    continue
                overlays = [cache.match(stamp_ns(frame), now) for cache in self.caches]
                for publisher, overlay in zip(self.publishers_, overlays):
                    output = copy.deepcopy(overlay) if overlay is not None else PerceptionTargets()
                    # TROS websocket requires exact equality, including nanoseconds.
                    output.header = copy.deepcopy(frame.header)
                    publisher.publish(output)
                if now - self.last_screen < .125:
                    continue
                self.last_screen = now
                try:
                    canvas = render_screen(bytes(frame.data), overlays)
                    temporary = self.path.with_suffix(".tmp.bmp")
                    if not cv2.imwrite(str(temporary), canvas):
                        raise OSError("Cannot write screen preview")
                    os.replace(temporary, self.path)
                except (OSError, ValueError, cv2.error) as exc:
                    self.get_logger().warning(str(exc), throttle_duration_sec=5.0)

    rclpy.init(args=args)
    node = PreviewFrames()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()
