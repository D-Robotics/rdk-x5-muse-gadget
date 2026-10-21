import math
from pathlib import Path
import sys
from types import SimpleNamespace as NS
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ros2_ws/src/muse_pet_vision"))
from muse_pet_vision.palm_motion import PalmApproachGate, PalmSample, palm_samples
from muse_pet_vision.adapter import PetVisionAdapter
from pet import PetEngine


def hand(scale=1., folded=False):
    points = [NS(x=120., y=200.) for _ in range(21)]
    for root, x in ((5, 80), (9, 110), (13, 140), (17, 170)):
        for offset, y in enumerate((150, 120, 100, 80)):
            points[root + offset] = NS(x=120 + (x - 120) * scale,
                                       y=200 + (y - 200) * scale)
    if folded:  # Fold the index finger to form OK; other fingers remain extended.
        points[8] = NS(x=points[5].x, y=190.)
    return NS(targets=[NS(track_id=3, attributes=[], points=[NS(type="hand_kps", point=points)])])


class PalmMotionTests(unittest.TestCase):
    def sample(self, size=.1, track=1, center=(.5, .5)):
        return PalmSample((track, 0), size, center)

    def run_sizes(self, gate, sizes, start=0.):
        return [hit for i, size in enumerate(sizes)
                if (hit := gate.observe([self.sample(size)], start + i * .1)) is not None]

    def test_open_palm_geometry_and_resolution_invariance(self):
        sample = palm_samples(hand(), 272, 320)
        self.assertEqual(len(sample), 1)
        scaled = hand()
        for point in scaled.targets[0].points[0].point:
            point.x *= 2; point.y *= 2
        self.assertAlmostEqual(sample[0].size, palm_samples(scaled, 544, 640)[0].size)
        self.assertEqual(palm_samples(hand(folded=True), 272, 320), [])
        self.assertEqual(palm_samples(hand(), 0, 0), [])

    def test_clipped_nan_and_incomplete_hands_are_not_strokes(self):
        for change in (lambda p: setattr(p[8], "x", math.nan),
                       lambda p: setattr(p[8], "x", -2), lambda p: p.pop()):
            msg = hand(); change(msg.targets[0].points[0].point)
            self.assertEqual(palm_samples(msg, 272, 320), [])

    def test_stationary_palm_and_small_jitter_never_pet(self):
        self.assertEqual(self.run_sizes(PalmApproachGate(), [.1, .105, .095, .102] * 25), [])

    def test_one_event_while_near_and_second_only_after_retreat(self):
        gate = PalmApproachGate()
        hits = self.run_sizes(gate, [.1] * 6 + [.16] * 18)
        self.assertEqual(len(hits), 1)
        self.assertTrue(gate.near)
        self.assertGreater(hits[0]["size_ratio"], 1.35)
        self.assertEqual(self.run_sizes(gate, [.1] * 12, 2.4), [])
        self.assertFalse(gate.near)
        self.assertEqual(len(self.run_sizes(gate, [.16] * 12, 3.6)), 1)

    def test_missing_hand_and_new_track_do_not_look_like_approach(self):
        gate = PalmApproachGate()
        self.run_sizes(gate, [.1] * 6)
        gate.observe([], .6)
        self.assertTrue(gate.present)
        gate.expire(1.)
        self.assertFalse(gate.present)
        self.assertEqual(self.run_sizes(gate, [.2] * 8, 1.1), [])
        self.assertIsNone(gate.observe([self.sample(.3, track=2)], 2.))
        self.assertFalse(gate.near)

    def test_multiple_hands_and_center_jumps_reset_tracking(self):
        gate = PalmApproachGate()
        self.run_sizes(gate, [.1] * 6)
        self.assertIsNone(gate.observe([self.sample(.2), self.sample(.1, track=2)], .6))
        self.assertFalse(gate.present)
        gate.observe([self.sample(.1)], .7)
        self.assertIsNone(gate.observe([self.sample(.2, center=(.9, .9))], .8))
        self.assertFalse(gate.near)

    def test_tiny_far_hand_does_not_trigger_from_quantization_noise(self):
        self.assertEqual(self.run_sizes(PalmApproachGate(), [.02] * 6 + [.03] * 12), [])

    def test_real_adapter_event_reaches_pet_and_near_palm_does_not_overwrite_it(self):
        now = [100.]
        pet = PetEngine(clock=lambda: now[0]); adapter = PetVisionAdapter()
        accepted = []
        for i, scale in enumerate([.6] * 6 + [1.] * 14):
            now[0] = 100 + i * .1
            for event in adapter.hand_motion(hand(scale), 272, 320, now[0], i + 1):
                result = pet.handle_event(event["event"])
                if event["event"]["type"] == "gesture":
                    accepted.append(result)
        self.assertEqual(len(accepted), 1)
        self.assertTrue(accepted[0]["accepted"])
        self.assertEqual(accepted[0]["state"]["mode"], "cuddling")
        self.assertEqual(pet.status()["last_gesture"], "PalmApproach")
        self.assertEqual(adapter.gesture(5, now[0], 99), [])
        self.assertEqual(adapter.gesture(5, now[0] + .3, 100), [])

    def test_attention_is_bounded_in_rate_and_open_palm_suppresses_accidental_feed(self):
        adapter = PetVisionAdapter()
        attention = []
        for i in range(20):
            events = adapter.hand_motion(hand(), 272, 320, i * .1, i + 1)
            attention.extend(e for e in events if e["event"]["type"] == "attention")
            self.assertEqual(adapter.gesture(11, i * .1, i + 1), [])
        self.assertLessEqual(len(attention), 8)
        self.assertGreater(len(attention), 3)
        self.assertTrue(all(-1 <= e["event"]["x"] <= 1 for e in attention))
