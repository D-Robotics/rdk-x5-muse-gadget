#!/bin/bash
set -eo pipefail
source "${TROS_SETUP:-/opt/tros/humble/setup.bash}"
source "${MUSE_PET_VISION_SETUP:-/opt/muse-ui/ros2_ws/install/setup.bash}"
source "$(dirname "${BASH_SOURCE[0]}")/ros-transport.sh"
[[ "$MUSE_PET_TRANSPORT" == shm ]] || { echo 'Unified runtime requires SHM transport.' >&2; exit 2; }
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 OPENCV_FOR_THREADS_NUM=1
export MUSE_RUNTIME_YOLO_CONFIG
MUSE_RUNTIME_YOLO_CONFIG=$(python3 - <<'PY'
from pathlib import Path
from ament_index_python.packages import get_package_prefix
from muse_pet_vision.assets import prepare_yolo_config
root=Path(get_package_prefix('dnn_node_example'))/'lib/dnn_node_example'
print(prepare_yolo_config(root/'config/yolov8workconfig.json',root,Path('/run/muse-vision-runtime/assets')))
PY
)
exec /opt/muse-ui/ros2_ws/install/lib/muse_pet_runtime/vision_runtime \
    --ros-args --log-level error --log-level muse_camera_throttle:=info --log-level MuseStereo:=warn
