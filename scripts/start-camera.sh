#!/bin/bash
set -eo pipefail
tros_setup="${TROS_SETUP:-/opt/tros/setup.bash}"
if [[ ! -r "$tros_setup" && -z "${TROS_SETUP:-}" ]]; then
    tros_setup=/opt/tros/humble/setup.bash
fi
[[ -r "$tros_setup" ]] || { echo "TROS setup not found: $tros_setup" >&2; exit 1; }
export HOME="${HOME:-/root}"
# shellcheck source=/dev/null
source "$tros_setup"
source "$(dirname "${BASH_SOURCE[0]}")/ros-transport.sh"
set -u
exec ros2 launch mipi_cam mipi_cam_dual_channel.launch.py \
    "mipi_image_width:=${MUSE_PET_CAMERA_WIDTH:-1088}" \
    "mipi_image_height:=${MUSE_PET_CAMERA_HEIGHT:-1280}" \
    "mipi_image_framerate:=${MUSE_PET_CAMERA_FPS:-30.0}" \
    "mipi_io_method:=$MUSE_PET_IMAGE_TRANSPORT" \
    "mipi_sub_stream_enable:=$MUSE_PET_SUBSTREAM_ENABLED" \
    "mipi_sub_image_width:=${MUSE_PET_SUB_IMAGE_WIDTH:-272}" \
    "mipi_sub_image_height:=${MUSE_PET_SUB_IMAGE_HEIGHT:-320}" \
    "dual_combine:=${MUSE_PET_CAMERA_COMBINE:-0}" \
    "mipi_stream_mode:=${MUSE_PET_CAMERA_STREAM_MODE:-0}" \
    "mipi_camera_calibration_file_path:=${MUSE_PET_CAMERA_CALIBRATION:-default}" \
    "mipi_lpwm_enable:=${MUSE_PET_CAMERA_SYNC:-false}" \
    "mipi_channel:=${MUSE_PET_CAMERA_CHANNEL:-2}" \
    "mipi_channel2:=${MUSE_PET_CAMERA_CHANNEL2:-0}" \
    mipi_frame_ts_type:=realtime
