import unittest

from pet import PetCommandError, PetEngine


class FakeClock:
    def __init__(self, value=100.0):
        self.value = value

    def __call__(self):
        return self.value

    def advance(self, seconds):
        self.value += seconds


class PetEngineTests(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        self.pet = PetEngine(clock=self.clock)

    def event(self, name, event_id, **values):
        return self.pet.handle_event({
            "type": "gesture",
            "name": name,
            "event_id": event_id,
            "observed_at": self.clock.value,
            "stable_ms": 300,
            **values,
        })

    def test_direct_commands_cover_pet_lifecycle(self):
        self.assertFalse(self.pet.status()["awake"])
        with self.assertRaises(PetCommandError):
            self.pet.move("left")

        self.pet.command("wake")
        moved = self.pet.command("move", direction="left")
        self.assertEqual((moved["position"], moved["direction"], moved["mode"]),
                         (45, "left", "moving"))
        self.clock.advance(1)
        self.assertEqual(self.pet.status()["direction"], "stop")

        happiness = self.pet.status()["happiness"]
        self.assertEqual(self.pet.command("pet")["happiness"], happiness + 5)
        fed = self.pet.command("feed", food="banana")
        self.assertEqual((fed["last_food"], fed["mode"]), ("banana", "eating"))
        self.assertFalse(self.pet.command("sleep")["awake"])

    def test_timer_uses_monotonic_clock_and_completes_once(self):
        self.pet.timer_start(10)
        self.clock.advance(3)
        self.assertEqual(self.pet.status()["timer_remaining"], 7)
        self.clock.value = 90  # A broken injected clock cannot extend the timer.
        self.assertEqual(self.pet.status()["timer_remaining"], 7)
        self.clock.value = 111
        complete = self.pet.status()
        self.assertEqual((complete["timer_state"], complete["timer_remaining"]),
                         ("complete", 0))
        happiness = complete["happiness"]
        self.assertEqual(self.pet.status()["happiness"], happiness)

    def test_object_events_drive_feed_and_find(self):
        self.pet.wake()
        seen = self.pet.handle_event({
            "type": "object", "label": "banana", "confidence": 0.9,
            "event_id": "banana-1", "observed_at": self.clock.value,
        })
        self.assertTrue(seen["accepted"])
        self.assertEqual(seen["state"]["pending_food"], "banana")
        fed = self.event("Okay", "ok-1")
        self.assertTrue(fed["accepted"])
        self.assertEqual(fed["state"]["last_food"], "banana")

        self.pet.find("cup")
        self.clock.advance(0.5)
        found = self.pet.handle_event({
            "type": "object", "label": "cup", "confidence": 0.8,
            "event_id": "cup-1", "observed_at": self.clock.value,
        })
        self.assertTrue(found["accepted"])
        self.assertEqual((found["state"]["find_state"], found["state"]["mode"]),
                         ("found", "happy"))

    def test_all_supported_gestures_have_deterministic_actions(self):
        self.assertEqual(self.event("Palm", "g-1")["action"], "wake")
        self.clock.advance(0.4)
        self.assertEqual(self.event("ThumbLeft", "g-2")["state"]["position"], 45)
        self.clock.advance(0.4)
        self.assertEqual(self.event("ThumbRight", "g-3")["state"]["position"], 50)

        self.pet.handle_event({
            "type": "object", "label": "banana", "event_id": "o-1",
            "observed_at": self.clock.value,
        })
        self.assertEqual(self.event("Okay", "g-4")["action"], "feed")
        self.clock.advance(1.1)
        self.assertEqual(self.event("ThumbUp", "g-5")["action"], "pet")
        self.clock.advance(2.1)
        victory = self.event("Victory", "g-6")
        self.assertEqual((victory["action"], victory["state"]["find_target"]),
                         ("find", "banana"))

    def test_event_expiry_duplicate_stability_and_cooldown(self):
        stale = self.pet.handle_event({
            "type": "gesture", "name": "Palm", "event_id": "stale",
            "observed_at": self.clock.value - 2,
        })
        self.assertEqual(stale["reason"], "stale")

        unstable = self.pet.handle_event({
            "type": "gesture", "name": "Palm", "event_id": "unstable",
            "observed_at": self.clock.value, "stable_ms": 10,
        })
        self.assertEqual(unstable["reason"], "unstable")

        first = self.event("Palm", "same")
        self.assertTrue(first["accepted"])
        self.assertEqual(self.event("Palm", "same")["reason"], "duplicate")
        self.assertEqual(self.event("Palm", "new")["reason"], "cooldown")

    def test_state_fields_are_backend_line_protocol_values(self):
        fields = self.pet.state_fields()
        self.assertTrue(fields)
        self.assertTrue(all(key.startswith("pet_") or key == "vision" for key in fields))
        self.assertEqual(fields["pet_awake"], "false")
        self.assertEqual(fields["pet_timer_remaining"], "0")
        self.assertEqual(fields["pet_x"], "0")
        for key in ("pet_hunger", "pet_energy", "pet_object", "pet_gesture",
                    "pet_timer", "pet_app", "vision"):
            self.assertIn(key, fields)

    def test_display_command_strings_and_vision_health_are_supported(self):
        self.pet.command("wake")
        self.assertEqual(self.pet.command("move right")["position"], 55)
        self.assertEqual(self.pet.command("feed")["last_food"], "banana")
        timer = self.pet.command("timer start 25")
        self.assertEqual((timer["timer_state"], timer["timer_duration"]),
                         ("running", 1500))
        self.assertEqual(self.pet.command("find banana")["find_target"], "banana")
        health = self.pet.handle_event({
            "type": "health", "status": "ready", "event_id": "health-1",
            "observed_at": self.clock.value,
        })
        self.assertTrue(health["accepted"])
        self.assertEqual(self.pet.state_fields()["vision"], "ready")


if __name__ == "__main__":
    unittest.main()
