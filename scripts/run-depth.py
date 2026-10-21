#!/usr/bin/env python3
"""Start only depth workers using the controller's already prepared ROS environment."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'ros2_ws/src/muse_pet_vision'))
from muse_pet_vision.depth_config import stereo_parameters


def main():
    runtime = Path(os.environ.get('MUSE_PET_DEPTH_RUNTIME', '/run/muse-pet-depth'))
    environment = json.loads((runtime / 'ros-env.json').read_text())
    environment['ROS_LOG_DIR'] = str(runtime / 'log')
    parameters = runtime / 'stereo-params.json'
    parameters.write_text(json.dumps({'MuseStereo': {'ros__parameters': stereo_parameters()}}))
    commands = [
        [str(ROOT / 'ros2_ws/install/lib/muse_pet_camera_throttle/depth_input')],
        ['/opt/tros/humble/lib/hobot_stereonet/stereonet_model_node',
         '--ros-args', '-r', '__node:=MuseStereo', '--params-file', str(parameters), '--log-level', 'warn'],
    ]
    children = []
    stopping = False
    def stop(signum, frame):
        nonlocal stopping
        stopping = True
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        for command in commands:
            children.append(subprocess.Popen(command, env=environment))
        while not stopping:
            for process in children:
                result = process.poll()
                if result is not None:
                    raise RuntimeError(f'Depth worker exited: {result}')
            time.sleep(.05)
    finally:
        for process in children:
            if process.poll() is None: process.send_signal(signal.SIGINT)
        deadline = time.monotonic() + 3
        for process in children:
            try: process.wait(timeout=max(.01, deadline-time.monotonic()))
            except subprocess.TimeoutExpired:
                process.kill(); process.wait()


if __name__ == '__main__':
    main()
