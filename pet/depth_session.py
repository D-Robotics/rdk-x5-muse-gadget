"""Lease-controlled StereoNet; normal camera and gesture services stay running."""
import json
import os
from pathlib import Path
import signal
import subprocess
import time

SERVICES = ('muse-pet-camera.service', 'muse-pet-vision.service', 'muse-pet-preview.service')
PIPELINE = 'muse-pet-depth-pipeline.service'
RUNTIME = Path(os.environ.get('MUSE_PET_DEPTH_RUNTIME', '/run/muse-pet-depth'))
LEASE = Path(os.environ.get('MUSE_PET_DEPTH_LEASE', '/run/user/1000/muse-depth.active'))


def systemctl(*args):
    return subprocess.run(['systemctl', *args], text=True, capture_output=True,
                          timeout=90, check=False)


def status(text):
    RUNTIME.mkdir(parents=True, exist_ok=True)
    temporary = RUNTIME / 'status.tmp'
    temporary.write_text(text + '\n')
    temporary.replace(RUNTIME / 'status')


def active_lease(path=LEASE, now=None):
    try:
        age = (time.time() if now is None else now) - path.stat().st_mtime
        return 0 <= age < 3
    except OSError:
        return False


def prepare():
    """The camera and gestures are independent; depth only subscribes to them."""
    RUNTIME.mkdir(parents=True, exist_ok=True)
    if any(systemctl('is-active', name).stdout.strip() != 'active'
           for name in (SERVICES[0], SERVICES[2])):
        raise RuntimeError('Start the shared Muse camera and preview before opening Depth')
    status('Starting depth')
    (RUNTIME / 'depth.bmp').unlink(missing_ok=True)


def resume():
    journal = RUNTIME / 'services.json'
    if not journal.exists():
        return
    # Validate the recovery file; never execute arbitrary unit names from disk.
    running = json.loads(journal.read_text())
    if not isinstance(running, list) or any(name not in SERVICES for name in running):
        raise ValueError('Invalid depth recovery journal')
    status('Restoring vision')
    for name in SERVICES:  # camera first, then consumers
        if name in running:
            result = systemctl('start', name)
            if result.returncode:
                raise RuntimeError(result.stderr or f'Could not restore {name}')
    journal.unlink()
    (RUNTIME / 'depth.bmp').unlink(missing_ok=True)
    status('Depth idle')


def stop_pipeline():
    result = systemctl('stop', PIPELINE)
    if result.returncode:
        # Never restart the normal camera while the depth owner may still live.
        raise RuntimeError(result.stderr or 'Could not stop the depth pipeline')
    resume()  # one-time recovery of the previous exclusive-mode journal
    (RUNTIME / 'depth.bmp').unlink(missing_ok=True)


def watch():
    # Keep model weights cached, but depth_input supplies zero frames off-page.
    # No camera/service churn, and no BPU inference without a current UI lease.
    stop_pipeline()
    status('Preparing depth')
    retry_at = 0.0
    was_open = False
    try:
        while True:
            now = time.monotonic()
            if now >= retry_at:
                retry_at = now + 15
                result = systemctl('start', PIPELINE)
                if result.returncode:
                    status('Depth unavailable')
                    print(result.stderr, flush=True)
            opened = active_lease()
            if not opened and was_open:
                (RUNTIME / 'depth.bmp').unlink(missing_ok=True)
                status('Depth idle')
            was_open = opened
            time.sleep(.1)
    finally:
        stop_pipeline()


def main():
    import sys
    def stop(signum, frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, stop)
    action = sys.argv[1] if len(sys.argv) > 1 else 'watch'
    if action not in ('watch', 'prepare', 'resume'):
        raise SystemExit('Expected watch, prepare or resume')
    try:
        globals()[action]()
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
