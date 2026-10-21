"""Normalize mixed body/hand results for the TROS 2.4.1 gesture classifier."""

from copy import deepcopy
from math import isfinite
from typing import Any


def hand_only(message: Any) -> tuple[Any, dict[str, int]]:
    """Keep paired hand ROIs and 21-point landmarks without changing the source.

    The classifier counts every point group, including body keypoints. Its input
    must therefore contain only hand groups. Unequal counts are ambiguous: never
    guess which ROI belongs to a surviving landmark group.
    """
    output = deepcopy(message)
    output.targets = []
    stats = dict(targets=len(message.targets), hands=0, valid=0, rejected=0)
    for original in message.targets:
        rois = [roi for roi in original.rois if roi.type == "hand"]
        points = [group for group in original.points if group.type == "hand_kps"]
        stats["hands"] += len(rois)
        if not rois:
            continue
        valid = len(rois) == len(points) and all(
            roi.rect.width > 0 and roi.rect.height > 0 for roi in rois
        ) and all(
            len(group.point) == 21 and all(
                isfinite(point.x) and isfinite(point.y) for point in group.point
            ) for group in points
        )
        if not valid:
            stats["rejected"] += len(rois)
            continue
        target = deepcopy(original)
        target.rois = deepcopy(rois)
        target.points = deepcopy(points)
        output.targets.append(target)
        stats["valid"] += len(rois)
    return output, stats
