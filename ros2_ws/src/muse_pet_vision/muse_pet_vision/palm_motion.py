"""Relative palm approach, inferred from 2-D landmarks rather than metric depth."""
from dataclasses import dataclass
import math


@dataclass(frozen=True)
class PalmSample:
    track_id: tuple[int, int]
    size: float
    center: tuple[float, float]


def palm_samples(message, width: int, height: int) -> list[PalmSample]:
    if width <= 0 or height <= 0:
        return []
    samples = []
    for target in message.targets:
        classified_palm = any(a.type == "gesture" and a.value == 5 for a in target.attributes)
        groups = [group for group in target.points if group.type == "hand_kps"]
        for index, group in enumerate(groups):
            points = [(p.x, p.y) for p in group.point]
            if len(points) != 21 or not all(
                math.isfinite(x) and math.isfinite(y) and 0 <= x < width and 0 <= y < height
                for x, y in points
            ):
                continue
            def distance(a, b):
                return math.dist(points[a], points[b])
            extended = 0
            for mcp, pip, tip in ((5, 6, 8), (9, 10, 12), (13, 14, 16), (17, 18, 20)):
                u = tuple(a - b for a, b in zip(points[mcp], points[pip]))
                v = tuple(a - b for a, b in zip(points[tip], points[pip]))
                length = math.hypot(*u) * math.hypot(*v)
                if length and sum(a * b for a, b in zip(u, v)) / length < -.7 and \
                        distance(0, tip) > 1.25 * distance(0, mcp):
                    extended += 1
            # OK, Victory and ThumbUp must not become proximity strokes.
            if extended < (3 if classified_palm else 4):
                continue
            size = math.sqrt(distance(0, 9) * distance(5, 17) / (width * height))
            if not .02 <= size <= .8:
                continue
            core = [points[i] for i in (0, 5, 9, 13, 17)]
            center = (sum(p[0] for p in core) / (5 * width),
                      sum(p[1] for p in core) / (5 * height))
            samples.append(PalmSample((int(target.track_id), index), size, center))
    return samples


class PalmApproachGate:
    """One stroke per approach; sustained retreat rearms it. Missing hands reset."""
    def __init__(self):
        self.reset()
        self.last_trigger = float("-inf")

    def reset(self):
        self.track = None
        self.last_seen = None
        self.started = None
        self.center = None
        self.size = self.baseline = None
        self.near = False
        self.crossing_since = None

    @property
    def present(self):
        return self.track is not None

    def expire(self, now):
        if self.last_seen is not None and now - self.last_seen > .4:
            self.reset()

    def observe(self, samples, now):
        self.expire(now)
        if not samples:
            return None  # Brief landmark dropouts must not discard the baseline.
        if len(samples) != 1:  # Avoid jumping between two visible hands.
            self.reset()
            return None
        sample = samples[0]
        if (sample.track_id != self.track or self.center is None or
                math.dist(sample.center, self.center) > .2):
            self.reset()
            self.track, self.started = sample.track_id, now
            self.size = self.baseline = sample.size
            self.center, self.last_seen = sample.center, now
            return None
        dt = now - self.last_seen
        self.last_seen, self.center = now, sample.center
        alpha = 1 - math.exp(-max(0, dt) / .12)
        self.size += alpha * (sample.size - self.size)
        if now - self.started < .3:
            self.baseline = min(self.baseline, self.size)
            return None
        if self.near:
            crossed = self.size <= self.baseline * 1.12
        else:
            self.baseline = min(self.baseline, self.size)
            crossed = self.size >= self.baseline * 1.35 and self.size - self.baseline >= .012
        if not crossed:
            self.crossing_since = None
            return None
        if self.crossing_since is None:
            self.crossing_since = now
            return None
        if now - self.crossing_since < .25:
            return None
        self.crossing_since = None
        if self.near:
            self.near = False
            self.baseline = min(self.baseline, self.size)
            return None
        self.near = True
        if now - self.last_trigger < 1.2:
            return None
        self.last_trigger = now
        return {"track_id": self.track[0], "size_ratio": round(self.size / self.baseline, 3)}
