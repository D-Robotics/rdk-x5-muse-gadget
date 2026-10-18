"""Preview setup must preserve the installed TROS viewer and its assets."""
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace as NS
import importlib.util

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ros2_ws/src/muse_pet_vision"))
from muse_pet_vision.preview import prepare_viewer
from muse_pet_vision.preview_frames import OverlayCache, render_screen


class PreviewTests(unittest.TestCase):
    def test_overlay_rounding_is_allowed_but_other_frames_and_stale_results_are_not(self):
        cache = OverlayCache(limit=2)
        message = NS(header=NS(stamp=NS(sec=10, nanosec=500)))
        cache.add(message, 1.0)
        self.assertIs(cache.match(10_000_000_000, 1.1), message)
        self.assertIsNone(cache.match(10_033_000_000, 1.1))
        self.assertIsNone(cache.match(10_000_000_000, 3.1))
        for sec in range(4):
            cache.add(NS(header=NS(stamp=NS(sec=sec, nanosec=0))), 4.0)
        self.assertEqual(len(cache.items), 2)

    @unittest.skipUnless(importlib.util.find_spec("cv2"), "OpenCV is installed on X5")
    def test_real_jpeg_renders_overlay_at_native_screen_size(self):
        import cv2
        import numpy as np
        source = np.zeros((1280, 1088, 3), dtype=np.uint8)
        source[:] = (60, 70, 80)
        _, jpeg = cv2.imencode('.jpg', source)
        target = NS(type='banana', attributes=[], points=[], rois=[NS(
            type='banana', rect=NS(x_offset=100, y_offset=100, width=300, height=400))])
        output = render_screen(bytes(jpeg), [NS(targets=[target]), None])
        self.assertEqual(output.shape, (256, 480, 3))
        self.assertTrue(((output[:, :224, 1] > 200) & (output[:, :224, 2] < 180)).any())
        with self.assertRaises(ValueError):
            render_screen(b'not jpeg', [None, None])

    def test_runtime_copy_enables_both_views_without_mutating_vendor_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            vendor = root / "vendor"
            source = vendor / "html/TogetheROS/index.html"
            source.parent.mkdir(parents=True)
            original = '<html><head></head><script src="./main.js"></script></html>'
            source.write_text(original)
            runtime = root / "runtime"
            config = prepare_viewer(vendor, runtime)
            self.assertEqual(source.read_text(), original)
            self.assertIn('path_num=2;', (runtime / "index.html").read_text())
            self.assertIn('video-wrap-8082', (runtime / "index.html").read_text())
            self.assertIn('listen 8000;', config.read_text())
            self.assertIn(str(vendor / "html"), config.read_text())
            self.assertIn('daemon off;', config.read_text())

    def test_unknown_viewer_version_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "html/TogetheROS/index.html"
            source.parent.mkdir(parents=True)
            source.write_text('<html></html>')
            with self.assertRaises(ValueError):
                prepare_viewer(root, root / "runtime")
