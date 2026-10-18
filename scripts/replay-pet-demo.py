#!/usr/bin/env python3
"""Replay synthetic perception to test the UI; no camera/model inference."""
import argparse
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "ros2_ws/src/muse_pet_vision"))
from muse_pet_vision.adapter import PetVisionAdapter, UnixEventSink
from petctl import send_command


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", default=os.environ.get("MUSE_UI_RUNTIME", "/run/muse-ui"))
    args = parser.parse_args()
    socket = Path(args.runtime) / "input.sock"
    adapter = PetVisionAdapter()
    with UnixEventSink(str(socket)) as sink:
        def send(events):
            for event in events:
                sink.send(event)

        def gesture(value):
            for _ in range(5):
                send(adapter.gesture(value, time.monotonic(), time.time_ns()))
                time.sleep(.1)

        print("Synthetic demo: palm → move → banana + OK → short timer", flush=True)
        gesture(5)
        gesture(12)
        gesture(13)
        for _ in range(3):
            send(adapter.objects([{"label": "banana", "confidence": .9}],
                                 time.monotonic(), time.time_ns()))
            time.sleep(.1)
        gesture(11)
        time.sleep(2.5)
        send_command({"action": "pet_command", "command": "timer", "seconds": 5}, socket)
        time.sleep(5.5)
        print("Done. Read petctl status for the resulting state.")


if __name__ == "__main__":
    main()
