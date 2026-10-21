from pathlib import Path
from types import SimpleNamespace as NS
import importlib.util
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'ros2_ws/src/muse_pet_vision'))
from pet import depth_session as session
from muse_pet_vision.depth_frames import fit_visual


class DepthTests(unittest.TestCase):
    def test_lease_stops_after_missing_stale_or_future_timestamp(self):
        import os
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'request'
            self.assertFalse(session.active_lease(path, 10))
            path.touch(); os.utime(path, (10, 10))
            self.assertTrue(session.active_lease(path, 12.9))
            self.assertFalse(session.active_lease(path, 13))
            self.assertFalse(session.active_lease(path, 9))

    def test_prepare_never_stops_camera_or_perception(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(session, 'RUNTIME', Path(tmp)), \
             patch.object(session, 'systemctl', return_value=NS(stdout='active')) as ctl:
            session.prepare()
            self.assertEqual([c.args for c in ctl.call_args_list], [('is-active', session.SERVICES[0]), ('is-active', session.SERVICES[2])])
            self.assertFalse((Path(tmp) / 'services.json').exists())

    def test_upgrade_restores_previous_exclusive_mode_journal(self):
        import json
        with tempfile.TemporaryDirectory() as tmp, patch.object(session, 'RUNTIME', Path(tmp)):
            (Path(tmp) / 'services.json').write_text(json.dumps(list(session.SERVICES)))
            with patch.object(session, 'systemctl', return_value=NS(returncode=0)) as ctl:
                session.resume()
                self.assertEqual([c.args for c in ctl.call_args_list], [('start', s) for s in session.SERVICES])
                self.assertFalse((Path(tmp) / 'services.json').exists())

    def test_model_stays_cached_across_page_changes_and_stops_on_controller_exit(self):
        with patch.object(session, 'systemctl', return_value=NS(returncode=0)) as ctl, \
             patch.object(session, 'resume'), patch.object(session, 'status'), \
             patch.object(session, 'RUNTIME', Path('/tmp/muse-test-nonexistent')), \
             patch.object(session, 'active_lease', side_effect=[False, True, True, False]), \
             patch.object(session.time, 'monotonic', side_effect=[0, 1, 2, 3]), \
             patch.object(session.time, 'sleep', side_effect=[None, None, None, KeyboardInterrupt]):
            with self.assertRaises(KeyboardInterrupt): session.watch()
            self.assertEqual(ctl.call_args_list[0].args, ('stop', session.PIPELINE))
            starts = [c.args for c in ctl.call_args_list if c.args[0] == 'start']
            self.assertEqual(starts, [('start', session.PIPELINE)])
            self.assertEqual(ctl.call_args_list[-1].args, ('stop', session.PIPELINE))

    def test_failed_depth_stop_never_restores_a_competing_camera(self):
        with patch.object(session, 'systemctl', return_value=NS(returncode=1, stderr='busy')), \
             patch.object(session, 'resume') as restore:
            with self.assertRaises(RuntimeError): session.stop_pipeline()
            restore.assert_not_called()

    def test_hidden_depth_renderer_does_no_image_work(self):
        from muse_pet_vision.depth_frames import DepthRenderer
        with tempfile.TemporaryDirectory() as tmp, patch('muse_pet_vision.depth_frames.fit_visual') as fit:
            renderer = DepthRenderer(Path(tmp) / 'out', Path(tmp) / 'absent-lease')
            self.assertFalse(renderer.render(object()))
            fit.assert_not_called()
            self.assertFalse((Path(tmp) / 'out').exists())

    @unittest.skipUnless(importlib.util.find_spec('cv2'), 'OpenCV is installed on X5')
    def test_vendor_distance_visual_uses_only_depth_half_and_preserves_aspect(self):
        import numpy as np
        source = np.zeros((704, 640, 3), dtype=np.uint8)
        source[:352] = (0, 0, 255)
        source[352:] = (255, 0, 0)
        message = NS(width=640, height=704, step=1920, encoding='bgr8', data=source.tobytes())
        out = fit_visual(message)
        self.assertEqual(out.shape, (320, 480, 3))
        self.assertTrue((out[28:292, :, 0] == 255).all())
        self.assertFalse(out[:, :, 2].any())
        self.assertFalse(out[:28].any())
        for change in ({'data': b'bad'}, {'encoding':'16UC1'}, {'width':0}):
            with self.assertRaises(ValueError): fit_visual(NS(**(vars(message) | change)))


if __name__ == '__main__': unittest.main()
