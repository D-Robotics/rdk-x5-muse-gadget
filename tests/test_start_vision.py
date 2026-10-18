import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class StartupTests(unittest.TestCase):
    def test_camera_uses_realtime_stamps_and_cross_user_transport(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            setup = folder / "setup.bash"
            setup.write_text(":\n")
            ros2 = folder / "ros2"
            ros2.write_text("#!/bin/sh\nprintf '%s\\n' \"$FASTRTPS_DEFAULT_PROFILES_FILE\" \"$ROS_DISABLE_LOANED_MESSAGES\" \"$@\"\n")
            ros2.chmod(0o755)
            env = {**os.environ, "TROS_SETUP": str(setup),
                   "PATH": str(folder) + os.pathsep + os.environ["PATH"]}
            result = subprocess.run(["bash", str(ROOT / "scripts/start-camera.sh")],
                env=env, capture_output=True, text=True, check=True)
            args = result.stdout.splitlines()
            self.assertTrue(Path(args[0]).is_file())
            self.assertEqual(args[1], "1")
            self.assertIn("mipi_frame_ts_type:=realtime", args)
            self.assertIn("dual_combine:=0", args)

    def test_empty_optional_argument_is_omitted_for_humble(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            setup = folder / "setup.bash"
            setup.write_text(":\n")
            ros2 = folder / "ros2"
            ros2.write_text("#!/bin/sh\nprintf '%s\\n' \"$@\"\n")
            ros2.chmod(0o755)
            env = {**os.environ, "TROS_SETUP": str(setup),
                   "MUSE_PET_VISION_SETUP": str(setup),
                   "PATH": str(folder) + os.pathsep + os.environ["PATH"]}
            for extra in ("", "world:/muse/world"):
                env["MUSE_PET_EXTRA_DETECTOR_TOPICS"] = extra
                result = subprocess.run(["bash", str(ROOT / "scripts/start-vision.sh")],
                    env=env, capture_output=True, text=True, check=True)
                args = result.stdout.splitlines()
                self.assertFalse(any(arg.endswith(":=") for arg in args))
                self.assertEqual(any(arg.startswith("extra_detector_topics:=") for arg in args), bool(extra))


if __name__ == "__main__":
    unittest.main()
