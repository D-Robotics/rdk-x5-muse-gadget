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

if [[ "${MUSE_PET_UNIFIED_RUNTIME:-0}" == 1 ]]; then
    exec ros2 run muse_pet_vision muse_pet_vision_node --ros-args \
        -p left_health_topic:=/muse/camera/left/health \
        -p right_health_topic:=/muse/camera/right/health \
        -p hand_landmark_topic:=/muse/hand_landmarks \
        -p gesture_input_topic:=/muse/gesture_input \
        -p gesture_topic:=/muse/gestures -p object_topic:=/muse/objects \
        -p socket_path:="${MUSE_PET_SOCKET_PATH:-/run/muse-ui/input.sock}"
fi

left_topic="${MUSE_PET_LEFT_TOPIC:-/image_left_raw}"
right_topic="${MUSE_PET_RIGHT_TOPIC:-/image_right_raw}"
if [[ "$MUSE_PET_TRANSPORT" == shm ]]; then
    prefix=
    case "$MUSE_PET_SUBSTREAM_ENABLED" in
        true|1) prefix=sub_ ;;
        false|0) ;;
        *) echo 'MUSE_PET_SHM_SUBSTREAM must be true or false.' >&2; exit 2 ;;
    esac
    left_topic="${MUSE_PET_SHM_LEFT_TOPIC:-/${prefix}hbmem_left_img}"
    right_topic="${MUSE_PET_SHM_RIGHT_TOPIC:-/${prefix}hbmem_right_img}"
fi

args=(
    "left_topic:=$left_topic"
    "right_topic:=$right_topic"
    "image_transport:=$MUSE_PET_IMAGE_TRANSPORT"
    "gesture_topic:=${MUSE_PET_GESTURE_TOPIC:-/muse/gestures}"
    "object_topic:=${MUSE_PET_OBJECT_TOPIC:-/muse/objects}"
    "socket_path:=${MUSE_PET_SOCKET_PATH:-/run/muse-ui/input.sock}"
    "start_gesture:=${MUSE_PET_START_GESTURE:-false}"
    "start_yolo:=${MUSE_PET_START_YOLO:-false}"
    "auto_discover:=${MUSE_PET_AUTO_DISCOVER:-false}"
    "start_throttle:=${MUSE_PET_THROTTLE:-true}"
    "camera_fps:=${MUSE_PET_INFERENCE_FPS:-10.0}"
    "preview_fps:=${MUSE_PET_PREVIEW_FPS:-8.0}"
    "log_level:=${MUSE_PET_LOG_LEVEL:-error}"
    "mono2d_image_gap:=${MUSE_PET_BODY_IMAGE_GAP:-0}"
)

[[ -z "${MUSE_PET_EXTRA_DETECTOR_TOPICS:-}" ]] || args+=("extra_detector_topics:=$MUSE_PET_EXTRA_DETECTOR_TOPICS")
[[ -z "${MUSE_PET_MONO2D_MODEL_FILE:-}" ]] || args+=("mono2d_model_file:=$MUSE_PET_MONO2D_MODEL_FILE")
[[ -z "${MUSE_PET_HAND_LMK_MODEL_FILE:-}" ]] || args+=("hand_lmk_model_file:=$MUSE_PET_HAND_LMK_MODEL_FILE")
[[ -z "${MUSE_PET_GESTURE_MODEL_FILE:-}" ]] || args+=("gesture_model_file:=$MUSE_PET_GESTURE_MODEL_FILE")
[[ -z "${MUSE_PET_GESTURE_MODEL_NAME:-}" ]] || args+=("gesture_model_name:=$MUSE_PET_GESTURE_MODEL_NAME")
[[ -z "${MUSE_PET_YOLO_CONFIG_FILE:-}" ]] || args+=("yolo_config_file:=$MUSE_PET_YOLO_CONFIG_FILE")

exec ros2 launch muse_pet_vision muse_pet_vision.launch.py "${args[@]}"
