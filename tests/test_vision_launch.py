"""Check actual launch construction without pretending to run ROS or BPU."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from types import ModuleType
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ros2_ws/src/muse_pet_vision"))


class LaunchTests(unittest.TestCase):
    def load_launch(self, prefixes):
        class Configuration:
            def __init__(self, name): self.name = name
            def perform(self, context): return context[self.name]

        def module(name, **fields):
            result = ModuleType(name)
            result.__dict__.update(fields)
            return result

        modules = {
            "ament_index_python": module("ament_index_python"),
            "ament_index_python.packages": module("ament_index_python.packages",
                get_package_prefix=lambda name: prefixes[name]),
            "launch": module("launch", LaunchDescription=list),
            "launch.actions": module("launch.actions", DeclareLaunchArgument=lambda *a, **k: k,
                                     OpaqueFunction=lambda **k: k),
            "launch.substitutions": module("launch.substitutions", LaunchConfiguration=Configuration),
            "launch_ros": module("launch_ros"),
            "launch_ros.actions": module("launch_ros.actions", Node=lambda **k: k),
        }
        with patch.dict(sys.modules, modules):
            spec = importlib.util.spec_from_file_location("pet_launch", ROOT /
                "ros2_ws/src/muse_pet_vision/launch/muse_pet_vision.launch.py")
            launch = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(launch)
        return launch

    def test_bridge_only_launch_does_not_require_algorithm_packages(self):
        launch = self.load_launch({})
        nodes = launch._build(dict(launch.ARGUMENTS))
        self.assertEqual([node["package"] for node in nodes], ["muse_pet_vision"])

    def test_throttle_changes_both_bridge_inputs_and_keeps_original_camera_inputs(self):
        launch = self.load_launch({})
        nodes = launch._build({**launch.ARGUMENTS, "start_throttle": "true"})
        self.assertEqual(nodes[0]["package"], "muse_pet_camera_throttle")
        self.assertEqual(nodes[0]["parameters"][0]["left_topic"], "/image_left_raw")
        self.assertEqual(nodes[1]["parameters"][0]["left_topic"], "/muse/camera/left")
        self.assertEqual(nodes[1]["parameters"][0]["right_topic"], "/muse/camera/right")

    def test_full_pipeline_remaps_left_eye_and_resolves_assets(self):
        with tempfile.TemporaryDirectory() as tmp:
            prefix = Path(tmp)
            packages = ("mono2d_body_detection", "hand_lmk_detection",
                        "hand_gesture_detection", "dnn_node_example")
            files = ("multitask_body_head_face_hand_kps_960x544.hbm", "handLMKs.hbm",
                     "gestureDet_8x21.hbm", "model.bin")
            for package, filename in zip(packages, files):
                config = prefix / "lib" / package / "config"
                config.mkdir(parents=True)
                (config / filename).touch()
            config = prefix / "lib/dnn_node_example/config"
            (config / "coco.list").write_text("banana\ncup\n")
            (config / "yolov8workconfig.json").write_text(json.dumps({
                "model_file": "model.bin", "cls_names_list": "config/coco.list"}))
            launch = self.load_launch({name: str(prefix) for name in packages})
            values = {**launch.ARGUMENTS, "start_gesture": "true", "start_yolo": "true"}
            with patch.dict("os.environ", {"MUSE_PET_ASSET_CACHE": str(prefix / "cache")}):
                nodes = launch._build(values)
            self.assertEqual(len(nodes), 5)
            self.assertNotIn("mipi_cam", [node["package"] for node in nodes])
            for node in nodes[1:]:
                self.assertIn(("/image_raw", "/image_left_raw"), node["remappings"])
            config_path = nodes[-1]["parameters"][0]["config_file"]
            self.assertTrue(Path(json.loads(Path(config_path).read_text())["model_file"]).is_absolute())
            with patch.dict("os.environ", {"MUSE_PET_ASSET_CACHE": str(prefix / "cache")}):
                bounded = launch._build({**values, "start_throttle": "true"})
            for node in bounded[2:]:
                self.assertIn(("/image_raw", "/muse/camera/left"), node["remappings"])
                if "ros_img_topic_name" in node["parameters"][0]:
                    self.assertEqual(node["parameters"][0]["ros_img_topic_name"], "/muse/camera/left")


if __name__ == "__main__":
    unittest.main()
