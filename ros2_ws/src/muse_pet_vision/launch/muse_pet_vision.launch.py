"""Perception on an existing stereo stream. This file never launches a camera."""
import os
from pathlib import Path
import tempfile

from ament_index_python.packages import get_package_prefix
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

from muse_pet_vision.assets import prepare_yolo_config, require_file


ARGUMENTS = {
    "left_topic": "/image_left_raw", "right_topic": "/image_right_raw",
    "gesture_topic": "/muse/gestures", "object_topic": "/muse/objects",
    "extra_detector_topics": "", "socket_path": "/run/muse-ui/input.sock",
    "auto_discover": "false", "camera_stale_sec": "1.0",
    "gesture_stable_sec": "0.25", "gesture_lost_sec": "0.4",
    "gesture_repeat_sec": "0.5", "object_confidence": "0.6",
    "start_gesture": "false", "start_yolo": "false",
    "start_throttle": "false", "camera_fps": "10.0",
    "mono2d_model_file": "", "mono2d_image_gap": "2",
    "hand_lmk_model_file": "", "gesture_model_file": "",
    "gesture_model_name": "", "yolo_config_file": "", "log_level": "warn",
}


def _build(context):
    values = {key: LaunchConfiguration(key).perform(context) for key in ARGUMENTS}

    def enabled(key):
        value = values[key].lower()
        if value not in ("true", "false", "1", "0"):
            raise ValueError(f"{key} must be true or false")
        return value in ("true", "1")

    def package_root(package):
        return Path(get_package_prefix(package)) / "lib" / package

    def model(root, key, filename):
        return require_file(values[key] or root / "config" / filename, key)

    nodes = []
    if enabled("start_throttle"):
        nodes.append(Node(package="muse_pet_camera_throttle", executable="camera_throttle",
            output="screen", parameters=[{"left_topic": values["left_topic"],
                "right_topic": values["right_topic"], "fps": float(values["camera_fps"])}]))
        values["left_topic"], values["right_topic"] = "/muse/camera/left", "/muse/camera/right"
    bridge_params = {key: values[key] for key in (
        "left_topic", "right_topic", "gesture_topic", "object_topic",
        "extra_detector_topics", "socket_path")}
    bridge_params["auto_discover"] = enabled("auto_discover")
    for key in ("camera_stale_sec", "gesture_stable_sec", "gesture_lost_sec",
                "gesture_repeat_sec", "object_confidence"):
        bridge_params[key] = float(values[key])
    nodes.append(Node(package="muse_pet_vision", executable="muse_pet_vision_node",
                  output="screen", parameters=[bridge_params]))

    def perception(package, executable, name, root, parameters):
        return Node(package=package, executable=executable, name=name,
                    output="screen", cwd=str(root), parameters=[parameters],
                    remappings=[("/image_raw", values["left_topic"])],
                    arguments=["--ros-args", "--log-level", values["log_level"]])

    if enabled("start_gesture"):
        body = package_root("mono2d_body_detection")
        hand = package_root("hand_lmk_detection")
        gesture = package_root("hand_gesture_detection")
        gesture_model = model(gesture, "gesture_model_file", "gestureDet_8x21.hbm")
        if values["gesture_model_file"] and not values["gesture_model_name"]:
            raise ValueError("A custom gesture_model_file also needs gesture_model_name")
        nodes.extend([
            perception("mono2d_body_detection", "mono2d_body_detection", "muse_body", body, {
                "model_file_name": model(body, "mono2d_model_file",
                    "multitask_body_head_face_hand_kps_960x544.hbm"),
                "model_type": 0, "track_mode": 1,
                "image_gap": int(values["mono2d_image_gap"]), "is_shared_mem_sub": 0,
                "ros_img_topic_name": values["left_topic"],
                "ai_msg_pub_topic_name": "/muse/body",
            }),
            perception("hand_lmk_detection", "hand_lmk_detection", "muse_hands", hand, {
                "feed_type": 0, "model_file_name": model(hand, "hand_lmk_model_file", "handLMKs.hbm"),
                "is_shared_mem_sub": 0, "ros_img_topic_name": values["left_topic"],
                "ai_msg_sub_topic_name": "/muse/body",
                "ai_msg_pub_topic_name": "/muse/hand_landmarks",
            }),
            perception("hand_gesture_detection", "hand_gesture_detection", "muse_gestures", gesture, {
                "model_file_name": gesture_model,
                "model_name": values["gesture_model_name"] or "gestureDet_8x21",
                "is_dynamic_gesture": False, "threshold": 0.5,
                "time_interval_sec": 0.25,
                "ai_msg_sub_topic_name": "/muse/hand_landmarks",
                "ai_msg_pub_topic_name": values["gesture_topic"],
            }),
        ])
    if enabled("start_yolo"):
        root = package_root("dnn_node_example")
        config = Path(values["yolo_config_file"] or root / "config/yolov8workconfig.json")
        cache = Path(os.environ.get("MUSE_PET_ASSET_CACHE") or
                     Path(tempfile.gettempdir()) / f"muse-pet-{os.getuid()}")
        config = prepare_yolo_config(config, root, cache)
        nodes.append(perception("dnn_node_example", "example", "muse_yolo", root, {
            "feed_type": 1, "is_shared_mem_sub": 0,
            "ros_img_topic_name": values["left_topic"], "config_file": config,
            "msg_pub_topic_name": values["object_topic"], "dump_render_img": 0,
        }))
    return nodes


def generate_launch_description():
    return LaunchDescription([
        *(DeclareLaunchArgument(key, default_value=value) for key, value in ARGUMENTS.items()),
        OpaqueFunction(function=_build),
    ])
