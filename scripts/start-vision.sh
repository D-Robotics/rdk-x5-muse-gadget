#!/bin/bash
set -eo pipefail

tros_setup="${TROS_SETUP:-/opt/tros/setup.bash}"
if [[ ! -r "$tros_setup" && -z "${TROS_SETUP:-}" ]]; then
    tros_setup=/opt/tros/humble/setup.bash
fi
overlay_setup="${MUSE_PET_VISION_SETUP:-/opt/muse-ui/ros2_ws/install/setup.bash}"

[[ -r "$tros_setup" ]] || { echo "TROS setup not found: $tros_setup" >&2; exit 1; }
[[ -r "$overlay_setup" ]] || { echo "Muse vision overlay not found: $overlay_setup" >&2; exit 1; }

# ROS setup scripts may inspect variables that are not present in a clean
# systemd environment, so enable nounset only after sourcing them.
# shellcheck source=/dev/null
source "$tros_setup"
# shellcheck source=/dev/null
source "$overlay_setup"
source "$(dirname "${BASH_SOURCE[0]}")/ros-transport.sh"
set -u

args=(
    "left_topic:=${MUSE_PET_LEFT_TOPIC:-/image_left_raw}"
    "right_topic:=${MUSE_PET_RIGHT_TOPIC:-/image_right_raw}"
    "gesture_topic:=${MUSE_PET_GESTURE_TOPIC:-/muse/gestures}"
    "object_topic:=${MUSE_PET_OBJECT_TOPIC:-/muse/objects}"
    "socket_path:=${MUSE_PET_SOCKET_PATH:-/run/muse-ui/input.sock}"
    "start_gesture:=${MUSE_PET_START_GESTURE:-false}"
    "start_yolo:=${MUSE_PET_START_YOLO:-false}"
    "auto_discover:=${MUSE_PET_AUTO_DISCOVER:-false}"
)

[[ -z "${MUSE_PET_EXTRA_DETECTOR_TOPICS:-}" ]] || args+=("extra_detector_topics:=$MUSE_PET_EXTRA_DETECTOR_TOPICS")
[[ -z "${MUSE_PET_MONO2D_MODEL_FILE:-}" ]] || args+=("mono2d_model_file:=$MUSE_PET_MONO2D_MODEL_FILE")
[[ -z "${MUSE_PET_HAND_LMK_MODEL_FILE:-}" ]] || args+=("hand_lmk_model_file:=$MUSE_PET_HAND_LMK_MODEL_FILE")
[[ -z "${MUSE_PET_GESTURE_MODEL_FILE:-}" ]] || args+=("gesture_model_file:=$MUSE_PET_GESTURE_MODEL_FILE")
[[ -z "${MUSE_PET_GESTURE_MODEL_NAME:-}" ]] || args+=("gesture_model_name:=$MUSE_PET_GESTURE_MODEL_NAME")
[[ -z "${MUSE_PET_YOLO_CONFIG_FILE:-}" ]] || args+=("yolo_config_file:=$MUSE_PET_YOLO_CONFIG_FILE")

exec ros2 launch muse_pet_vision muse_pet_vision.launch.py "${args[@]}"
