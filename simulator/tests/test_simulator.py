#!/usr/bin/env python3
# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Headless smoke and deterministic framebuffer tests for the UI simulator."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import socket
import tempfile
import struct
import time

WIDTH, HEIGHT = 480, 320
HERE = Path(__file__).resolve().parent
SCENARIOS = tuple(sorted(path for path in (HERE / "scenarios").glob("*.txt")
                         if not path.name.startswith(".")))


def read_ppm(path: Path) -> bytes:
    raw = path.read_bytes()
    header = f"P6\n{WIDTH} {HEIGHT}\n255\n".encode()
    assert raw.startswith(header), f"{path}: wrong PPM header"
    pixels = raw[len(header) :]
    assert len(pixels) == WIDTH * HEIGHT * 3, f"{path}: truncated framebuffer"
    assert len(set(pixels)) > 8, f"{path}: framebuffer has too few colours"
    return pixels


def render(binary: Path, scenario: Path, output: Path) -> tuple[str, subprocess.CompletedProcess[str]]:
    env = {**os.environ, "SDL_VIDEODRIVER": "dummy", "SDL_AUDIODRIVER": "dummy"}
    proc = subprocess.run(
        [
            str(binary),
            "--headless",
            "--scenario",
            str(scenario),
            "--run-ms",
            "200",
            "--screenshot",
            str(output),
        ],
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=30,
    )
    assert proc.returncode == 0, f"{scenario.name}:\n{proc.stdout}\n{proc.stderr}"
    pixels = read_ppm(output)
    return hashlib.sha256(pixels).hexdigest(), proc


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", type=Path, required=True)
    args = parser.parse_args()
    binary = args.binary.resolve()
    assert binary.is_file(), binary
    assert SCENARIOS, "no simulator scenarios found"

    with tempfile.TemporaryDirectory(prefix="muse-simulator-test-") as tmp:
        tmp_path = Path(tmp)
        hashes: dict[str, str] = {}
        for scenario in SCENARIOS:
            first, _ = render(binary, scenario, tmp_path / f"{scenario.stem}-1.ppm")
            second, _ = render(binary, scenario, tmp_path / f"{scenario.stem}-2.ppm")
            assert first == second, f"{scenario.name}: framebuffer is not deterministic"
            hashes[scenario.stem] = first

        assert len(set(hashes.values())) == len(hashes), f"scenarios rendered identically: {hashes}"

        # Showing shutdown must not lock subsequent preview state selections.
        after_off = tmp_path / "after-off.txt"
        after_off.write_text("face=off\n" + (HERE / "scenarios/listening.txt").read_text())
        recovered, _ = render(binary, after_off, tmp_path / "after-off.ppm")
        assert recovered == hashes["listening"], "Off prevented the next preview state"

        invalid = tmp_path / "invalid.txt"
        for setting in ("face=definitely-not-a-mode", "level=nan", "pet_x=101", "pet_look_x=101", "pet_hand_present=maybe"):
            invalid.write_text(f"{setting}\n")
            proc = subprocess.run(
                [str(binary), "--headless", "--scenario", str(invalid)],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=10,
            )
            assert proc.returncode == 2
            assert "unsupported or invalid setting" in proc.stderr

        # Real SDL pointer input must pet the avatar without recording audio.
        # Hold/release on the microphone must generate start/stop instead.
        with tempfile.TemporaryDirectory(dir="/tmp", prefix="mui-") as runtime:
            preview = Path(runtime) / "vision.bmp"
            pixels = b'\x00\x00\xff' * (480 * 320)
            preview.write_bytes(struct.pack('<2sIHHI', b'BM', 54 + len(pixels), 0, 0, 54) +
                struct.pack('<IiiHHIIiiII', 40, 480, 320, 1, 24, 0, len(pixels), 0, 0, 0, 0) + pixels)
            vision = tmp_path / "vision.txt"
            vision.write_text('face=idle\npage=vision\nadvance=500\n')
            for stale in (False, True):
                if stale:
                    os.utime(preview, (time.time() - 5, time.time() - 5))
                screenshot = tmp_path / f"vision-{stale}.ppm"
                proc = subprocess.run([str(binary), '--headless', '--scenario', str(vision),
                    '--screenshot', str(screenshot)], env={**os.environ, 'MUSE_UI_RUNTIME': runtime},
                    capture_output=True, text=True, timeout=10)
                assert proc.returncode == 0, proc.stderr
                assert (Path(runtime) / "muse-preview.active").is_file(), "Vision did not request frames"
                pixel = read_ppm(screenshot)[(100 * WIDTH + 20) * 3: (100 * WIDTH + 20) * 3 + 3]
                is_red = pixel[0] > 200 and pixel[1] < 20 and pixel[2] < 20
                assert is_red != stale, ('native preview stale handling', stale, pixel)
                if not stale:
                    bottom = read_ppm(screenshot)[(310 * WIDTH + 240) * 3: (310 * WIDTH + 240) * 3 + 3]
                    assert bottom[0] > 200 and bottom[1] < 20, 'Preview did not use full screen height'
            vision.write_text('face=idle\npage=vision\nadvance=500\npage=face\nadvance=500\n')
            proc = subprocess.run([str(binary), '--headless', '--scenario', str(vision)],
                env={**os.environ, 'MUSE_UI_RUNTIME': runtime}, capture_output=True, text=True, timeout=10)
            assert proc.returncode == 0, proc.stderr
            assert not (Path(runtime) / "muse-preview.active").exists(), "Hidden preview kept requesting frames"
            depth = Path(runtime) / "depth.bmp"
            depth.write_bytes(preview.read_bytes())
            for stale in (False, True):
                if stale: os.utime(depth, (time.time() - 5, time.time() - 5))
                vision.write_text('face=idle\npage=depth\nadvance=500\n')
                screenshot = tmp_path / f"depth-{stale}.ppm"
                proc = subprocess.run([str(binary), '--headless', '--scenario', str(vision),
                    '--screenshot', str(screenshot)], env={**os.environ,
                    'MUSE_UI_RUNTIME': runtime, 'MUSE_PET_DEPTH_RUNTIME': runtime},
                    capture_output=True, text=True, timeout=10)
                assert proc.returncode == 0, proc.stderr
                assert (Path(runtime) / "muse-depth.active").exists(), "Depth did not request pipeline"
                assert not (Path(runtime) / "muse-preview.active").exists(), "Depth requested Vision too"
                pixel = read_ppm(screenshot)[(100 * WIDTH + 20) * 3: (100 * WIDTH + 20) * 3 + 3]
                assert (pixel[0] > 200 and pixel[1] < 20) != stale, ('depth stale handling', stale, pixel)
            vision.write_text('face=idle\npage=depth\nadvance=500\npage=vision\nadvance=500\n')
            proc = subprocess.run([str(binary), '--headless', '--scenario', str(vision)],
                env={**os.environ, 'MUSE_UI_RUNTIME': runtime}, capture_output=True, text=True, timeout=10)
            assert proc.returncode == 0, proc.stderr
            assert not (Path(runtime) / "muse-depth.active").exists(), "Hidden Depth kept running"
            assert (Path(runtime) / "muse-preview.active").exists(), "Returning to Vision did not request video"
            with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as receiver:
                receiver.bind(str(Path(runtime) / "input.sock"))
                receiver.settimeout(.1)
                for x, y, page, expected in ((240, 160, "face", ["pet_command"]),
                                       (340, 17, "face", ["start", "stop"]),
                                       (240, 111, "pet", ["pet_command"])):
                    touch = tmp_path / "touch.txt"
                    touch.write_text(f"face=idle\naudio=true\npaired=true\npage={page}\nadvance=300\n"
                                     f"touch_down={x},{y}\nadvance=650\n"
                                     f"touch_up={x},{y}\nadvance=200\n")
                    proc = subprocess.run([str(binary), "--headless", "--scenario", str(touch)],
                        env={**os.environ, "MUSE_UI_RUNTIME": runtime},
                        capture_output=True, text=True, timeout=10)
                    assert proc.returncode == 0, proc.stderr
                    actions = []
                    while True:
                        try:
                            actions.append(json.loads(receiver.recv(4096))["action"])
                        except socket.timeout:
                            break
                    assert actions == expected, (x, y, actions)

                # Every control dispatches its command and returns to the pet
                # so the action is visible, including from the second row.
                for x, y, command in ((114, 111, "wake"), (240, 111, "feed"),
                                      (366, 111, "play"), (114, 163, "look"),
                                      (240, 163, "stretch"), (366, 163, "timer start 25"),
                                      (114, 215, "find banana"), (240, 215, "sleep"),
                                      (366, 215, "timer cancel")):
                    touch.write_text(f"face=idle\npage=pet\nadvance=300\n"
                                     f"touch_down={x},{y}\nadvance=150\n"
                                     f"touch_up={x},{y}\nadvance=650\n")
                    screenshot = tmp_path / "control-return.ppm"
                    proc = subprocess.run([str(binary), "--headless", "--scenario", str(touch),
                        "--screenshot", str(screenshot)],
                        env={**os.environ, "MUSE_UI_RUNTIME": runtime},
                        capture_output=True, text=True, timeout=10)
                    assert proc.returncode == 0, proc.stderr
                    message = json.loads(receiver.recv(4096))
                    assert message == {"action": "pet_command", "command": command}, message
                    pixels = read_ppm(screenshot)
                    left = pixels[(302 * WIDTH + 224) * 3 + 2]
                    right = pixels[(302 * WIDTH + 240) * 3 + 2]
                    assert left > right, ("Control did not return to pet page", command)

    for name, digest in sorted(hashes.items()):
        print(f"{name}: {digest}")


if __name__ == "__main__":
    main()
