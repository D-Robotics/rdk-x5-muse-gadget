"""Real adapter-to-engine contract tests; no ROS/BPU installation required."""
import json
from pathlib import Path
import socket
import sys
import tempfile
from types import SimpleNamespace as NS
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ros2_ws/src/muse_pet_vision"))
from muse_pet_vision.adapter import (CameraHealthMonitor, FoodGate, PetVisionAdapter,
                                    StableGestureGate, UnixEventSink, select_stereo_topics)
from muse_pet_vision.assets import prepare_yolo_config
from muse_pet_vision.node import _best_gesture, _detections, message_is_fresh
from pet import PetEngine


class VisionTests(unittest.TestCase):
    def test_discovery_requires_matched_types_and_namespace(self):
        image = ["sensor_msgs/msg/Image"]
        self.assertIsNone(select_stereo_topics({"/a/image_left_raw": image,
                                               "/b/image_right_raw": image}))
        graph = {"/cam/image_left_raw": image, "/cam/image_right_raw": image,
                 "/hbmem_left_img": ["hbm_img_msgs/msg/HbmMsg1080P"]}
        self.assertEqual(select_stereo_topics(graph).left, "/cam/image_left_raw")
        self.assertIsNone(select_stereo_topics({"/image_left_raw": ["std_msgs/msg/String"]}))

    def test_gesture_requires_continuity_and_releases_before_second_activation(self):
        gate = StableGestureGate()
        self.assertEqual(gate.observe(5, 1, 1), [])
        self.assertEqual(gate.observe(5, 1.1, 2), [])
        self.assertEqual(gate.observe(5, 1.3, 3)[0].kind, "palm")
        self.assertEqual(gate.observe(5, 1.4, 4), [])
        self.assertEqual(gate.observe(5, 3.0, 5), [])  # missing hand is not stable
        self.assertEqual(gate.observe(5, 3.3, 6)[0].kind, "palm")

    def test_food_confirmation_expires_between_sparse_frames(self):
        gate = FoodGate()
        banana = [{"label": "banana", "confidence": .9}]
        self.assertFalse(gate.observe(banana, 0))
        self.assertFalse(gate.observe(banana, .1))
        self.assertFalse(gate.observe(banana, 2))
        self.assertFalse(gate.observe(banana, 2.1))
        self.assertTrue(gate.observe(banana, 2.2))
        self.assertTrue(gate.expired(3.3))

    def test_stereo_health_and_periodic_reconnect_snapshot(self):
        health = CameraHealthMonitor()
        health.observe("left", 1, 1, 1088, 1280, "nv12")
        self.assertEqual(health.status(), "degraded")
        health.observe("right", 1, 1, 1088, 1280, "nv12")
        self.assertEqual(health.status(), "ready")
        health.tick(2.1, 2)
        self.assertEqual(health.status(), "offline")
        adapter = PetVisionAdapter()
        self.assertEqual(adapter.tick(1, 1)[-1]["event"]["status"], "waiting")

    def test_ai_message_parsing_and_timestamp_expiry(self):
        target = NS(type="banana", track_id=7,
                    attributes=[NS(type="gesture", value=11.0, confidence=0.0)],
                    rois=[NS(confidence=.9, rect=NS(x_offset=10, y_offset=20,
                                                  width=30, height=40))])
        message = NS(targets=[target], header=NS(stamp=NS(sec=10, nanosec=0)))
        self.assertEqual(_best_gesture(message), (11.0, 7, None))
        self.assertEqual(_detections(message)[0]["bbox"], [10, 20, 30, 40])
        self.assertTrue(message_is_fresh(message, 10_500_000_000))
        self.assertFalse(message_is_fresh(message, 12_000_000_000))

    def test_real_adapter_events_wake_move_feed_and_find(self):
        now = [100.0]
        pet = PetEngine(clock=lambda: now[0])
        adapter = PetVisionAdapter()

        def emit(events):
            return [pet.handle_event(event["event"]) for event in events]

        emit(adapter.gesture(5, now[0], 1))
        now[0] += .3
        self.assertTrue(emit(adapter.gesture(5, now[0], 2))[0]["accepted"])
        now[0] += .1
        emit(adapter.gesture(13, now[0], 3))
        now[0] += .3
        emit(adapter.gesture(13, now[0], 4))
        self.assertEqual(pet.status()["position"], 55)
        for seq in range(5, 8):
            now[0] += .1
            emit(adapter.objects([{"label": "banana", "confidence": .9}], now[0], seq))
        emit(adapter.gesture(11, now[0], 8))
        now[0] += .3
        emit(adapter.gesture(11, now[0], 9))
        self.assertEqual(pet.status()["mode"], "eating")
        pet.find("cup")
        now[0] += .1
        emit(adapter.objects([{"label": "cup", "confidence": .8}], now[0], 10))
        self.assertEqual(pet.status()["find_state"], "found")

    def test_sink_uses_backend_envelope(self):
        with tempfile.TemporaryDirectory(dir="/tmp", prefix="mvp-") as tmp:
            path = str(Path(tmp) / "input.sock")
            with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as receiver:
                receiver.bind(path)
                receiver.settimeout(1)
                event = PetVisionAdapter().tick(1, 1)[0]
                with UnixEventSink(path) as sink:
                    sink.send(event)
                self.assertEqual(json.loads(receiver.recv(4096)), event)

    def test_config_paths_resolve_without_changing_vendor_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_dir = root / "config"
            config_dir.mkdir()
            (config_dir / "model.bin").touch()
            (config_dir / "coco.list").write_text("banana\ncup\n")
            config = config_dir / "yolov8workconfig.json"
            original = json.dumps({"model_file": "model.bin", "cls_names_list": "config/coco.list"})
            config.write_text(original)
            output = prepare_yolo_config(config, root, root / "cache")
            data = json.loads(Path(output).read_text())
            self.assertEqual(data["cls_names_list"], str((config_dir / "coco.list").resolve()))
            self.assertEqual(config.read_text(), original)
            (config_dir / "model.bin").unlink()
            with self.assertRaises(FileNotFoundError):
                prepare_yolo_config(config, root, root / "cache")


if __name__ == "__main__":
    unittest.main()
