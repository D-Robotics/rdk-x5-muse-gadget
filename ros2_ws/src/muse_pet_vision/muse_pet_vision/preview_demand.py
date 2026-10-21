"""Cheap viewer detection; no image work while both displays are closed."""
from pathlib import Path
import time


def screen_active(path, now=None):
    try:
        age = (time.time() if now is None else now) - Path(path).stat().st_mtime
        return 0 <= age < 3.0
    except OSError:
        return False


def web_active(paths=("/proc/net/tcp", "/proc/net/tcp6")):
    for path in paths:
        try:
            lines = Path(path).read_text().splitlines()[1:]
        except OSError:
            continue
        for line in lines:
            fields = line.split()
            if len(fields) >= 4 and fields[3] == "01":  # ESTABLISHED only
                try:
                    if int(fields[1].rsplit(":", 1)[1], 16) in (8080, 8082):
                        return True
                except (ValueError, IndexError):
                    continue
    return False


def latest_ready(pending, now, delay=.25, max_age=1.0):
    """Drop older eligible frames after a stall, instead of replaying a backlog."""
    latest = None
    while pending and now - pending[0][0] >= delay:
        received, frame = pending.popleft()
        if now - received <= max_age:
            latest = frame
    return latest
