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
    def load_launch(self, prefixes, kind="vision"):
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
                get_package_prefix=lambda name: prefixes[name],
                get_package_share_directory=lambda name: prefixes[name]),
            "launch": module("launch", LaunchDescription=list),
            "launch.actions": module("launch.actions", DeclareLaunchArgument=lambda *a, **k: k,
                                     OpaqueFunction=lambda **k: k, ExecuteProcess=lambda **k: k,
                                     RegisterEventHandler=lambda value: {"handler": value},
                                     Shutdown=lambda **k: k),
            "launch.event_handlers": module("launch.event_handlers", OnProcessExit=lambda **k: k),
            "launch.substitutions": module("launch.substitutions", LaunchConfiguration=Configuration),
            "launch_ros": module("launch_ros"),
            "launch_ros.actions": module("launch_ros.actions", Node=lambda **k: k),
        }
        with patch.dict(sys.modules, modules):
            spec = importlib.util.spec_from_file_location("pet_launch", ROOT /
                f"ros2_ws/src/muse_pet_vision/launch/muse_pet_{kind}.launch.py")
            launch = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(launch)
        return launch

    def test_depth_launch_cannot_start_a_second_camera_or_stop_gestures(self):
        with tempfile.TemporaryDirectory() as tmp:
            share = Path(tmp)
            (share / 'config').mkdir()
            (share / 'config/DStereoV2.4_int8.bin').touch()
            launch = self.load_launch({'hobot_stereonet': str(share)}, 'depth')
            nodes = [n for n in launch.generate_launch_description() if 'package' in n]
            self.assertEqual([n['executable'] for n in nodes], ['depth_input', 'stereonet_model_node'])
            params = nodes[1]['parameters'][0]
            self.assertEqual(params['stereo_image_topic'], '/muse/depth/input')
            self.assertEqual(params['camera_info_topic'], '/hbmem_combine_img/right/camera_info')
            self.assertFalse(params['publish_pcd_enabled'])

    def test_bridge_only_launch_does_not_require_algorithm_packages(self):
        launch = self.load_launch({})
        nodes = launch._build(dict(launch.ARGUMENTS))
        self.assertEqual([node["package"] for node in nodes], ["muse_pet_vision"])
        self.assertNotIn("hand_landmark_topic", nodes[0]["parameters"][0])

    def test_throttle_changes_both_bridge_inputs_and_keeps_original_camera_inputs(self):
        launch = self.load_launch({})
        nodes = launch._build({**launch.ARGUMENTS, "start_throttle": "true"})
        self.assertEqual(nodes[0]["package"], "muse_pet_camera_throttle")
        self.assertEqual(nodes[0]["parameters"][0]["left_topic"], "/image_left_raw")
        self.assertEqual(nodes[1]["parameters"][0]["left_topic"], "/muse/camera/left")
        self.assertEqual(nodes[1]["parameters"][0]["right_topic"], "/muse/camera/right")
        self.assertEqual(nodes[1]["parameters"][0]["left_health_topic"], "/muse/camera/left/health")
        self.assertEqual(nodes[1]["parameters"][0]["right_health_topic"], "/muse/camera/right/health")

    def test_shared_bridge_uses_metadata_and_validates_transport(self):
        launch = self.load_launch({})
        values = {**launch.ARGUMENTS, "image_transport": "shared_mem", "start_throttle": "true"}
        nodes = launch._build(values)
        self.assertEqual(nodes[0]["parameters"][0]["left_topic"], "/hbmem_left_img")
        self.assertEqual(nodes[0]["parameters"][0]["right_topic"], "/hbmem_right_img")
        self.assertEqual(nodes[0]["parameters"][0]["image_transport"], "shared_mem")
        self.assertEqual(nodes[1]["parameters"][0]["left_health_topic"], "/muse/camera/left/health")
        with self.assertRaises(ValueError):
            launch._build({**values, "start_throttle": "false"})
        with self.assertRaises(ValueError):
            launch._build({**values, "image_transport": "wrong"})

    def test_shared_preview_codec_reads_bounded_frames_and_keeps_jpeg_ros_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            prefix = Path(tmp)
            html = prefix / "lib/websocket/webservice/html/TogetheROS/index.html"
            html.parent.mkdir(parents=True)
            html.write_text('<head></head><script src="./main.js"></script>')
            launch = self.load_launch({"websocket": str(prefix)}, "preview")
            with patch.dict("os.environ", {"MUSE_PET_PREVIEW_RUNTIME": str(prefix / "runtime")}):
                nodes = launch._build({"left_topic": "/muse/camera/preview/hbmem",
                    "image_transport": "shared_mem", "object_topic": "/muse/objects",
                    "gesture_topic": "/muse/gestures"})
            codec = next(node for node in nodes if node.get("package") == "hobot_codec")
            parameters = codec["parameters"][0]
            self.assertEqual((parameters["in_mode"], parameters["out_mode"]), ("shared_mem", "ros"))
            self.assertEqual(parameters["sub_topic"], "/muse/camera/preview/hbmem")
            self.assertEqual(parameters["pub_topic"], "/muse/preview/encoded")
            self.assertEqual((parameters["input_framerate"], parameters["output_framerate"]), (30, 30))

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
            self.assertEqual(nodes[0]["parameters"][0]["hand_landmark_topic"], "/muse/hand_landmarks")
            self.assertEqual(nodes[0]["parameters"][0]["gesture_input_topic"], "/muse/gesture_input")
            classifier = next(node for node in nodes if node["package"] == "hand_gesture_detection")
            self.assertEqual(classifier["parameters"][0]["ai_msg_sub_topic_name"], "/muse/gesture_input")
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
            with patch.dict("os.environ", {"MUSE_PET_ASSET_CACHE": str(prefix / "cache")}):
                shared = launch._build({**values, "start_throttle": "true", "image_transport": "shared_mem"})
            for node in shared[2:]:
                self.assertIn(("/hbmem_img", "/muse/camera/left/hbmem"), node["remappings"])
                parameters = node["parameters"][0]
                if "is_shared_mem_sub" in parameters:
                    self.assertEqual(parameters["is_shared_mem_sub"], 1)
            self.assertEqual(shared[-1]["parameters"][0]["sharedmem_img_topic_name"], "/muse/camera/left/hbmem")


if __name__ == "__main__":
    unittest.main()
