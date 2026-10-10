import asyncio
import base64
import io
import struct
import unittest
import wave
from backend import ChatSession, make_voice_payload


class FakeBridge:
    def __init__(self):
        self.states = []
    def set_state(self, **state):
        self.states.append(state)


class Tests(unittest.IsolatedAsyncioTestCase):
    async def test_reply_ignores_other_parent_and_does_not_duplicate_final(self):
        s = object.__new__(ChatSession)
        s.bridge = FakeBridge()
        s.user_ids = {"our-user-message"}
        s.messages = {}
        s.turn_done = asyncio.get_running_loop().create_future()
        s.consume({"event": "message.assistant", "payload": {
            "message_id": "other-reply", "reply_to_message_id": "other-user-message",
            "display_text": "Should not speak this"}})
        self.assertFalse(s.turn_done.done())
        s.consume({"event": "delta.text_append", "payload": {
            "message_id": "reply", "reply_to_message_id": "our-user-message", "text": "你好"}})
        s.consume({"event": "delta.message_done", "payload": {"message_id": "reply"}})
        self.assertEqual(s.turn_done.result(), "你好")
        s.consume({"event": "message.assistant", "payload": {
            "message_id": "reply", "display_text": "你好"}})
        self.assertEqual(s.turn_done.result(), "你好")

    async def test_voice_note_is_valid_mono_pcm_wav(self):
        pcm = struct.pack("<hhh", -32768, 0, 32767)
        note = make_voice_payload(pcm)
        raw = base64.b64decode(note["items"][0]["data_base64"])
        with wave.open(io.BytesIO(raw)) as w:
            self.assertEqual((w.getnchannels(), w.getsampwidth(), w.getframerate()), (1, 2, 16000))
            self.assertEqual(w.readframes(3), pcm)


if __name__ == "__main__":
    unittest.main()
