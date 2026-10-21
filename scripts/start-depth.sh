#!/bin/bash
set -eo pipefail
tros_setup="${TROS_SETUP:-/opt/tros/humble/setup.bash}"
source "$tros_setup"
source "${MUSE_PET_VISION_SETUP:-/opt/muse-ui/ros2_ws/install/setup.bash}"
source "$(dirname "${BASH_SOURCE[0]}")/ros-transport.sh"
# StereoNet consumes the adapter output; camera/gesture services stay untouched.
exec ros2 launch muse_pet_vision muse_pet_depth.launch.py
