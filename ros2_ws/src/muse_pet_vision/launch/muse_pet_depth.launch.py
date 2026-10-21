"""MagicBox StereoNet on the existing camera; never stops gesture perception."""
import os
from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import RegisterEventHandler, Shutdown
from launch.event_handlers import OnProcessExit
from launch_ros.actions import Node
from muse_pet_vision.depth_config import stereo_parameters


def generate_launch_description():
    # Use the installed D-Robotics implementation and model, not a reimplementation.
    stereo = Path(get_package_share_directory('hobot_stereonet'))
    processes = [Node(package='muse_pet_camera_throttle', executable='depth_input',
                      output='screen', parameters=[{'fps': 30.0}]),
        Node(package='hobot_stereonet', executable='stereonet_model_node',
             name='MuseStereo', output='screen', parameters=[stereo_parameters(stereo)],
             arguments=['--ros-args', '--log-level', 'warn']),
    ]
    handlers = [RegisterEventHandler(OnProcessExit(
        target_action=process, on_exit=[Shutdown(reason='Depth process exited')]))
        for process in processes]
    return LaunchDescription(handlers + processes)
