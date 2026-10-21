"""Regression coverage for the mixed body/hand message compatibility fix."""
from copy import deepcopy
from pathlib import Path
import sys
from types import SimpleNamespace as NS
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ros2_ws/src/muse_pet_vision"))
from muse_pet_vision.gesture_input import hand_only


def roi(kind="hand", x=10):
    return NS(type=kind, rect=NS(x_offset=x, y_offset=20, width=60, height=80))


def group(kind="hand_kps", count=21, x=10):
    return NS(type=kind, point=[NS(x=float(x + n), y=20.0) for n in range(count)])


def message(rois, groups):
    return NS(header=NS(stamp=NS(sec=123, nanosec=456)), disappeared_targets=[NS(track_id=9)],
              targets=[NS(track_id=42, type="person", attributes=[], rois=rois, points=groups)])


class GestureInputTests(unittest.TestCase):
    def test_mixed_body_points_do_not_reach_classifier_and_source_is_unchanged(self):
        source = message([roi("body"), roi()], [group("body_kps", 17), group()])
        before = deepcopy(source)
        result, stats = hand_only(source)
        self.assertEqual(source, before)
        self.assertEqual([g.type for g in result.targets[0].points], ["hand_kps"])
        self.assertEqual([r.type for r in result.targets[0].rois], ["hand"])
        self.assertEqual(result.header, source.header)
        self.assertEqual(result.disappeared_targets, source.disappeared_targets)
        self.assertEqual(result.targets[0].track_id, 42)
        self.assertEqual(stats, dict(targets=1, hands=1, valid=1, rejected=0))

    def test_two_hands_preserve_correspondence(self):
        source = message([roi(x=10), roi(x=100)], [group(x=10), group(x=100)])
        result, stats = hand_only(source)
        self.assertEqual(stats["valid"], 2)
        target = result.targets[0]
        self.assertEqual([r.rect.x_offset for r in target.rois], [10, 100])
        self.assertEqual([g.point[0].x for g in target.points], [10, 100])

    def test_ambiguous_or_malformed_hands_are_not_guessed(self):
        bad = group()
        bad.point[0].x = float("nan")
        cases = [([roi(), roi()], [group()]), ([roi()], [group(count=20)]),
                 ([roi()], [bad])]
        zero = roi()
        zero.rect.width = 0
        cases.append(([zero], [group()]))
        for rois, groups in cases:
            with self.subTest(rois=rois, groups=groups):
                result, stats = hand_only(message(rois, groups))
                self.assertEqual(result.targets, [])
                self.assertEqual(stats["rejected"], len(rois))

    def test_empty_and_body_only_frames_preserve_disappearance(self):
        source = message([roi("body")], [group("body_kps", 17)])
        result, stats = hand_only(source)
        self.assertEqual(result.targets, [])
        self.assertEqual(stats["hands"], 0)
        self.assertEqual(result.disappeared_targets, source.disappeared_targets)
        source.targets = []
        self.assertEqual(hand_only(source)[0], source)


if __name__ == "__main__":
    unittest.main()
