"""Synthetic cross-process DDS test; no camera, BPU or board connection."""
import argparse
import os
from pathlib import Path
import random
import subprocess
import tempfile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--relay", required=True)
    parser.add_argument("--probe", required=True)
    parser.add_argument("--fast-preview", action="store_true")
    args = parser.parse_args()
    default_profile = Path(__file__).resolve().parents[4] / "scripts/fastdds-shm.xml"
    profile = Path(os.environ.get("MUSE_TEST_DDS_PROFILE", default_profile))
    if not profile.is_file():
        raise RuntimeError(f"Shared DDS profile not found: {profile}")
    env = {**os.environ, "RMW_IMPLEMENTATION": "rmw_fastrtps_cpp",
           "FASTRTPS_DEFAULT_PROFILES_FILE": str(profile), "RMW_FASTRTPS_USE_QOS_FROM_XML": "1",
           "ROS_DISABLE_LOANED_MESSAGES": "0", "ROS_LOCALHOST_ONLY": "1",
           "ROS_DOMAIN_ID": str(random.SystemRandom().randrange(80, 180))}
    command = [args.relay, "--ros-args", "-p", "image_transport:=shared_mem"]
    if args.fast_preview:
        command += ["-p", "preview_fps:=30.0"]
    rejected = subprocess.run(command, env={**env, "ROS_DISABLE_LOANED_MESSAGES": "1"},
                              capture_output=True, text=True, timeout=10)
    if rejected.returncode == 0 or "Shared image loans unavailable" not in rejected.stderr:
        raise RuntimeError(f"Disabled loans did not fail explicitly: {rejected.stderr}")

    with tempfile.TemporaryDirectory(prefix="muse-dds-test-") as directory:
        logs, processes = [], []
        try:
            for name, cmd in (("relay", command), ("source", [args.probe, "producer"]),
                              ("observer", [args.probe, "observer", "--ros-args", "-p",
                                            f"fast_preview:={str(args.fast_preview).lower()}"])):
                log = open(Path(directory) / f"{name}.log", "w+")
                logs.append((name, log))
                processes.append(subprocess.Popen(cmd, env=env, stdout=log, stderr=subprocess.STDOUT))
            code = processes[-1].wait(timeout=20)
            if code or any(process.poll() is not None for process in processes[:-1]):
                raise RuntimeError("Shared transport subprocess failed")
        finally:
            for process in processes:
                if process.poll() is None:
                    process.terminate()
            for process in processes:
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
            for name, log in logs:
                log.seek(0)
                print(f"{name}:\n{log.read()}")
                log.close()


if __name__ == "__main__":
    main()
