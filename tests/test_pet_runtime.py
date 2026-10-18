"""Exercise the real offline backend socket, CLI protocol and frontend state."""
import asyncio
import os
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from backend import Bridge
from petctl import read_state, send_command

ROOT = Path(__file__).resolve().parents[1]


class RuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def test_local_pet_works_without_chat_and_state_renders(self):
        with tempfile.TemporaryDirectory(dir="/tmp", prefix="mrt-") as tmp:
            runtime = Path(tmp)
            with patch("backend.RUNTIME", runtime), patch.dict(os.environ, {"MUSE_UI_CHAT": "off"}), \
                    patch("backend.os.chown"), patch("grp.getgrnam", return_value=SimpleNamespace(gr_gid=0)):
                bridge = Bridge()
                server = asyncio.create_task(bridge.serve())

                async def wait_for(key, value):
                    for _ in range(100):
                        if read_state(runtime / "state").get(key) == value:
                            return
                        if server.done():
                            await server
                        await asyncio.sleep(.01)
                    self.fail(f"{key} never became {value}: {read_state(runtime / 'state')}")

                try:
                    await wait_for("link", "offline")
                    socket_path = runtime / "input.sock"
                    send_command({"action": "pet_command", "command": "invalid"}, socket_path)
                    send_command({"action": "pet_command", "command": "wake"}, socket_path)
                    await wait_for("pet_awake", "true")
                    send_command({"action": "pet_command", "command": "move right"}, socket_path)
                    await wait_for("pet_x", "10")
                    send_command({"action": "pet_command", "command": "timer",
                                  "seconds": 1}, socket_path)
                    await wait_for("pet_timer_state", "complete")
                    self.assertFalse(server.done())
                    binary = ROOT / "build/muse_simulator"
                    if binary.is_file():
                        proc = await asyncio.to_thread(subprocess.run,
                            [str(binary), "--headless", "--scenario", str(runtime / "state"),
                             "--screenshot", str(runtime / "frame.ppm")],
                            capture_output=True, text=True, timeout=10)
                        self.assertEqual(proc.returncode, 0, proc.stderr)
                        self.assertNotIn("unsupported or invalid", proc.stderr)
                        self.assertGreater((runtime / "frame.ppm").stat().st_size, 480 * 320 * 3)
                finally:
                    server.cancel()
                    await asyncio.gather(server, return_exceptions=True)
                    self.assertFalse((runtime / "input.sock").exists())


if __name__ == "__main__":
    unittest.main()
