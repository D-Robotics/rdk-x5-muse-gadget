"""Two overlay views on the existing left camera; never starts a camera."""
import os
from pathlib import Path
import tempfile

from ament_index_python.packages import get_package_prefix
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess, OpaqueFunction, RegisterEventHandler, Shutdown
from launch.event_handlers import OnProcessExit
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

from muse_pet_vision.preview import prepare_viewer


def _build(context):
    def value(name):
        return LaunchConfiguration(name).perform(context)

    transport = value("image_transport")
    if transport not in ("ros", "shared_mem"):
        raise ValueError("image_transport must be ros or shared_mem")
    webservice = Path(get_package_prefix("websocket")) / "lib/websocket/webservice"
    runtime = Path(os.environ.get("MUSE_PET_PREVIEW_RUNTIME") or
                   Path(tempfile.gettempdir()) / f"muse-pet-preview-{os.getuid()}")
    config = prepare_viewer(webservice, runtime)
    processes = [ExecuteProcess(
        cmd=[str(webservice / "sbin/nginx"), "-p", str(runtime), "-c", str(config)],
        output="screen")]
    processes.append(Node(
        package="hobot_codec", executable="hobot_codec_republish", name="muse_preview_jpeg",
        output="screen", parameters=[{
            "channel": 1, "in_mode": transport, "in_format": "nv12",
            "out_mode": "ros", "out_format": "jpeg",
            "sub_topic": value("left_topic"), "pub_topic": "/muse/preview/encoded",
            # The relay controls delivery; never add a second 10 FPS cap here.
            "jpg_quality": 65.0, "input_framerate": 30, "output_framerate": 30,
        }], arguments=["--ros-args", "--log-level", "error"]))
    processes.append(Node(
        package="muse_pet_vision", executable="muse_pet_preview_frames", output="screen",
        parameters=[{"object_topic": value("object_topic"),
                     "gesture_topic": value("gesture_topic")}]))
    for channel, topic in enumerate(("/muse/preview/objects", "/muse/preview/gestures")):
        processes.append(Node(
            package="websocket", executable="websocket", name=f"muse_preview_{channel}",
            output="screen", parameters=[{
                "image_topic": "/muse/preview/jpeg", "image_type": "mjpeg",
                "only_show_image": False, "output_fps": 0,
                "channel": channel, "smart_topic": topic,
            }], arguments=["--ros-args", "--log-level", "error"]))
    # A bound port or codec failure must fail the service instead of leaving a
    # deceptively active launch process and blank page behind.
    handlers = [RegisterEventHandler(OnProcessExit(
        target_action=process, on_exit=[Shutdown(reason="Preview process exited")]))
        for process in processes]
    return handlers + processes


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument("left_topic", default_value="/image_left_raw"),
        DeclareLaunchArgument("image_transport", default_value="ros"),
        DeclareLaunchArgument("object_topic", default_value="/muse/objects"),
        DeclareLaunchArgument("gesture_topic", default_value="/muse/gestures"),
        OpaqueFunction(function=_build),
    ])
