#!/bin/bash
set -eo pipefail
source "${TROS_SETUP:-/opt/tros/humble/setup.bash}"
source "${MUSE_PET_VISION_SETUP:-/opt/muse-ui/ros2_ws/install/setup.bash}"
source "$(dirname "${BASH_SOURCE[0]}")/ros-transport.sh"
# Resolve the ROS environment once; page transitions never re-source setup.bash.
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
python3 - <<'PY'
import json,os
from pathlib import Path
runtime=Path(os.environ.get('MUSE_PET_DEPTH_RUNTIME','/run/muse-pet-depth'))
runtime.mkdir(parents=True,exist_ok=True)
path=runtime/'ros-env.tmp'
path.write_text(json.dumps(dict(os.environ)))
path.chmod(0o600)
path.replace(runtime/'ros-env.json')
PY
exec python3 /opt/muse-ui/scripts/depth-session.py watch
