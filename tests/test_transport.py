"""Exercise actual startup scripts and offline service profile generation."""
import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


class TransportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)
        setup = self.folder / "setup.bash"
        setup.write_text(":\n")
        ros = self.folder / "ros2"
        ros.write_text("#!/bin/sh\nprintf '%s\\n' \"$FASTRTPS_DEFAULT_PROFILES_FILE\" "
                       "\"$ROS_DISABLE_LOANED_MESSAGES\" \"$ROS_LOCALHOST_ONLY\" \"$@\"\n")
        ros.chmod(0o755)
        self.env = {key: value for key, value in os.environ.items() if not key.startswith("MUSE_PET_")}
        self.env.update(TROS_SETUP=str(setup), MUSE_PET_VISION_SETUP=str(setup),
                        MUSE_PET_TRANSPORT_CONFIG=str(self.folder / "missing"),
                        PATH=str(self.folder) + os.pathsep + os.environ["PATH"])

    def run_launcher(self, name, **env):
        return subprocess.run(["bash", str(ROOT / f"scripts/start-{name}.sh")],
                              env={**self.env, **env}, text=True, capture_output=True, timeout=10)

    def test_shared_mode_overrides_stale_disable_and_configures_every_consumer(self):
        values = dict(MUSE_PET_TRANSPORT="shm", ROS_DISABLE_LOANED_MESSAGES="1",
                      RMW_FASTRTPS_USE_QOS_FROM_XML="1",
                      FASTRTPS_DEFAULT_PROFILES_FILE="/old/udp.xml")
        for name in ("camera", "vision", "preview"):
            result = self.run_launcher(name, **values)
            self.assertEqual(result.returncode, 0, result.stderr)
            profile, loans, local, *args = result.stdout.splitlines()
            self.assertEqual(Path(profile).name, "fastdds-shm.xml")
            self.assertEqual((loans, local), ("0", "1"))
            if name == "camera":
                self.assertIn("mipi_io_method:=shared_mem", args)
                self.assertIn("mipi_sub_stream_enable:=false", args)
            else:
                self.assertIn("image_transport:=shared_mem", args)
                self.assertIn("left_topic:=/hbmem_left_img" if name == "vision" else
                              "left_topic:=/muse/camera/preview/hbmem", args)

    def test_optional_substream_keeps_capture_and_inference_topics_in_sync(self):
        values = dict(MUSE_PET_TRANSPORT="shm", MUSE_PET_SHM_SUBSTREAM="true",
                      MUSE_PET_LEFT_TOPIC="/image_left_raw")  # Legacy UDP setting.
        camera = self.run_launcher("camera", **values)
        vision = self.run_launcher("vision", **values)
        self.assertEqual((camera.returncode, vision.returncode), (0, 0))
        self.assertIn("mipi_sub_stream_enable:=true", camera.stdout)
        self.assertIn("mipi_sub_image_width:=272", camera.stdout)
        self.assertIn("mipi_sub_image_height:=320", camera.stdout)
        self.assertIn("left_topic:=/sub_hbmem_left_img", vision.stdout)
        self.assertIn("right_topic:=/sub_hbmem_right_img", vision.stdout)
        fallback = self.run_launcher("camera", **{**values, "MUSE_PET_TRANSPORT": "udp"})
        self.assertIn("mipi_sub_stream_enable:=false", fallback.stdout)
        self.assertIn("mipi_io_method:=ros", fallback.stdout)

    def test_common_profile_is_used_and_explicit_environment_can_select_fallback(self):
        config = self.folder / "common.env"
        config.write_text("MUSE_PET_TRANSPORT=shm\n")
        result = self.run_launcher("vision", MUSE_PET_TRANSPORT_CONFIG=str(config))
        self.assertIn("image_transport:=shared_mem", result.stdout)
        result = self.run_launcher("vision", MUSE_PET_TRANSPORT_CONFIG=str(config),
                                   MUSE_PET_TRANSPORT="udp")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("left_topic:=/image_left_raw", result.stdout)
        self.assertEqual(result.stdout.splitlines()[1:3], ["1", "0"])

    def test_invalid_profile_and_unbounded_shared_preview_are_rejected(self):
        for name in ("camera", "vision", "preview"):
            result = self.run_launcher(name, MUSE_PET_TRANSPORT="unknown")
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(result.stdout)
        result = self.run_launcher("camera", MUSE_PET_TRANSPORT="shm", MUSE_PET_SHM_SUBSTREAM="bad")
        self.assertNotEqual(result.returncode, 0)
        result = self.run_launcher("preview", MUSE_PET_TRANSPORT="shm", MUSE_PET_THROTTLE="false")
        self.assertNotEqual(result.returncode, 0)
        result = self.run_launcher("vision", MUSE_PET_DDS_PROFILE="/missing/profile.xml")
        self.assertNotEqual(result.returncode, 0)

    def test_service_profile_has_matching_uids_is_idempotent_and_can_revert(self):
        spec = importlib.util.spec_from_file_location("select_transport", ROOT / "scripts/select-pet-transport.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        files = module.configure(self.folder, "shm")
        before = {str(path): path.stat().st_mtime_ns for path in files}
        module.configure(self.folder, "shm")
        self.assertEqual(before, {str(path): path.stat().st_mtime_ns for path in files})
        for path in files:
            if path.suffix == ".conf":
                self.assertIn("User=root\nGroup=root\n", path.read_text())
                self.assertIn("EnvironmentFile=-/etc/default/muse-pet-transport", path.read_text())
        common = self.folder / "etc/default/muse-pet-transport"
        with common.open("a") as stream:
            stream.write("MUSE_PET_SHM_LEFT_TOPIC=/custom/left\n")
        files = module.configure(self.folder, "udp")
        self.assertIn("MUSE_PET_TRANSPORT=udp", common.read_text())
        self.assertIn("MUSE_PET_SHM_LEFT_TOPIC=/custom/left", common.read_text())
        for path in files:
            if path.suffix == ".conf":
                user = "root" if "camera" in str(path) else "sunrise"
                self.assertIn(f"User={user}\nGroup={user}\n", path.read_text())

    def test_shared_dds_profile_allows_bounded_data_sharing_without_forcing_unbounded_messages(self):
        namespace = {"d": "http://www.eprosima.com/XMLSchemas/fastRTPS_Profiles"}
        tree = ET.parse(ROOT / "scripts/fastdds-shm.xml")
        kinds = tree.findall(".//d:data_sharing/d:kind", namespace)
        self.assertEqual([kind.text for kind in kinds], ["AUTOMATIC", "AUTOMATIC"])


if __name__ == "__main__":
    unittest.main()
