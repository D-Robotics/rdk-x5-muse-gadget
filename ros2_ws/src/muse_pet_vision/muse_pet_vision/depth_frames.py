"""Present the vendor StereoNet distance visualization on the native screen."""
import os
from pathlib import Path
import time


def fit_visual(message):
    import cv2
    import numpy as np
    if message.encoding not in ('bgr8', 'rgb8'):
        raise ValueError('Unsupported StereoNet visual encoding')
    w, h, stride = int(message.width), int(message.height), int(message.step)
    if not (0 < w <= 4096 and 0 < h <= 4096 and w * 3 <= stride <= w * 3 + 4096):
        raise ValueError('Invalid StereoNet visual dimensions')
    if len(message.data) != h * stride:
        raise ValueError('Truncated StereoNet visual')
    source = np.frombuffer(message.data, dtype=np.uint8).reshape(h, stride)
    source = source[:, :w * 3].reshape(h, w, 3)
    if message.encoding == 'rgb8':
        source = cv2.cvtColor(source, cv2.COLOR_RGB2BGR)
    # StereoNet 2.4 distance render stacks the left image above the color depth.
    if (w, h) != (640, 704):
        raise ValueError('Unexpected StereoNet distance layout; expected 640x704')
    source = source[h // 2:]
    h //= 2
    scale = min(480 / w, 320 / h)
    out_w, out_h = max(1, round(w * scale)), max(1, round(h * scale))
    resized = cv2.resize(source, (out_w, out_h), interpolation=cv2.INTER_AREA)
    output = np.zeros((320, 480, 3), dtype=np.uint8)
    x, y = (480 - out_w) // 2, (320 - out_h) // 2
    output[y:y + out_h, x:x + out_w] = resized
    return output


class DepthRenderer:
    def __init__(self, runtime, lease=None):
        self.runtime, self.lease = Path(runtime), lease
        self.next_frame = 0.0

    def render(self, message):
        from .preview_demand import screen_active
        if self.lease is not None and not screen_active(self.lease):
            return False
        now = time.monotonic()
        if now < self.next_frame:
            return False
        self.next_frame = now + 1 / 30
        import cv2
        output = fit_visual(message)
        self.runtime.mkdir(parents=True, exist_ok=True)
        ok, bmp = cv2.imencode('.bmp', output)
        if not ok: raise ValueError('Depth BMP encode failed')
        temporary = self.runtime / 'depth.tmp'
        temporary.write_bytes(bytes(bmp))
        temporary.replace(self.runtime / 'depth.bmp')
        return True


def main(args=None):
    import cv2
    import rclpy
    from rclpy.node import Node
    from rclpy.qos import QoSProfile, ReliabilityPolicy
    from sensor_msgs.msg import Image

    cv2.setNumThreads(1)
    runtime = Path(os.environ.get('MUSE_PET_DEPTH_RUNTIME', '/run/muse-pet-depth'))
    runtime.mkdir(parents=True, exist_ok=True)

    class Frames(Node):
        def __init__(self):
            super().__init__('muse_depth_frames')
            self.next_frame = 0.0
            self.subscription = self.create_subscription(
                Image, '/MuseStereo/stereonet_visual', self.render,
                QoSProfile(depth=1, reliability=ReliabilityPolicy.BEST_EFFORT))

        def render(self, message):
            now = time.monotonic()
            if now < self.next_frame:
                return
            self.next_frame = now + 1 / 30
            try:
                output = fit_visual(message)
                ok, bmp = cv2.imencode('.bmp', output)
                if not ok:
                    raise ValueError('Depth BMP encode failed')
                temporary = runtime / 'depth.tmp'
                temporary.write_bytes(bytes(bmp))
                temporary.replace(runtime / 'depth.bmp')
            except (ValueError, cv2.error) as exc:
                self.get_logger().error(str(exc), throttle_duration_sec=5)

    rclpy.init(args=args)
    node = Frames()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()
