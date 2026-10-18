import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import petctl


class PetctlTests(unittest.TestCase):
    def parse(self, *args):
        parsed = petctl.parser().parse_args(args)
        return petctl.command_from_args(parsed)

    def test_commands_use_pet_command_protocol(self):
        self.assertEqual(self.parse("wake"), {"action": "pet_command", "command": "wake"})
        self.assertEqual(self.parse("move", "left"), {
            "action": "pet_command", "command": "move", "direction": "left"})
        self.assertEqual(self.parse("feed", "banana")["food"], "banana")
        self.assertEqual(self.parse("timer", "start", "1.5")["minutes"], 1.5)
        self.assertEqual(self.parse("timer", "cancel")["operation"], "cancel")
        self.assertEqual(self.parse("find", "cup")["target"], "cup")

    def test_status_only_returns_pet_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / "state"
            state.write_text("face=idle\npet_awake=true\npet_mode=happy\n", encoding="utf-8")
            self.assertEqual(petctl.pet_status(state), {"awake": "true", "mode": "happy"})

    def test_send_command_uses_existing_unix_datagram(self):
        class FakeSocket:
            def __init__(self):
                self.sent = None
            def __enter__(self):
                return self
            def __exit__(self, *_):
                pass
            def sendto(self, payload, target):
                self.sent = payload, target

        fake = FakeSocket()
        path = Path("/run/muse-ui/input.sock")
        with patch("petctl.socket.socket", return_value=fake) as constructor:
            petctl.send_command({"action": "pet_command", "command": "wake"}, path)
        constructor.assert_called_once_with(petctl.socket.AF_UNIX, petctl.socket.SOCK_DGRAM)
        self.assertEqual(json.loads(fake.sent[0]),
                         {"action": "pet_command", "command": "wake"})
        self.assertEqual(fake.sent[1], str(path))


if __name__ == "__main__":
    unittest.main()
