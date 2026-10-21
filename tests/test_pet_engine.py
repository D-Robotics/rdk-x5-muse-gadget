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

    def test_wake_and_timer_stop_have_brief_visible_reactions(self):
        self.assertEqual(self.pet.wake()["mode"], "waking")
        self.clock.advance(1.3)
        self.assertEqual(self.pet.status()["mode"], "idle")
        self.pet.timer_start(60)
        self.assertEqual(self.pet.timer_cancel()["mode"], "happy")
        self.clock.advance(1.1)
        self.assertEqual(self.pet.status()["mode"], "idle")
        self.pet.sleep()
        self.assertEqual(self.pet.timer_cancel()["mode"], "sleeping")

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

    def test_okay_feeds_virtual_snack_without_an_object_and_keeps_cooldown(self):
        fed = self.event("Okay", "virtual-snack")
        self.assertTrue(fed["accepted"])
        self.assertEqual(fed["action"], "feed")
        self.assertEqual((fed["state"]["last_food"], fed["state"]["mode"]),
                         ("snack", "eating"))
        self.assertEqual(fed["state"]["last_gesture"], "Okay")
        self.assertEqual(self.event("Okay", "too-soon")["reason"], "cooldown")
        self.clock.advance(3.1)
        self.assertTrue(self.event("Okay", "another-snack")["accepted"])

    def test_expired_food_is_not_reused_by_okay(self):
        self.pet.handle_event({"type": "object", "label": "banana",
                               "observed_at": self.clock.value})
        self.clock.advance(1.1)
        fed = self.event("Okay", "expired-food")
        self.assertTrue(fed["accepted"])
        self.assertEqual(fed["state"]["last_food"], "snack")

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
        self.clock.advance(2.6)
        self.assertEqual(self.event("ThumbUp", "g-5")["action"], "pet")
        self.clock.advance(2.1)
        victory = self.event("Victory", "g-6")
        self.assertTrue(victory["accepted"])
        self.assertEqual((victory["action"], victory["state"]["mode"]),
                         ("dance", "dancing"))

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

    def test_palm_does_not_restart_wake_or_interrupt_a_reaction(self):
        self.pet.feed("snack")
        self.assertEqual(self.event("Palm", "palm-during-food")["reason"], "already_awake")
        self.assertEqual(self.event("ThumbLeft", "move-during-food")["reason"], "busy")
        self.assertEqual(self.event("ThumbUp", "pet-during-food")["reason"], "busy")
        self.assertEqual(self.pet.status()["mode"], "eating")
        self.clock.advance(2.6)
        self.assertTrue(self.event("ThumbLeft", "move-after-food")["accepted"])
        # Explicit controls retain priority even during an animation.
        self.pet.feed("snack")
        self.assertEqual(self.pet.command("sleep")["mode"], "sleeping")

    def test_palm_approach_has_a_distinct_cuddle_and_resumes_the_active_task(self):
        self.pet.timer_start(60)
        response = self.event("PalmApproach", "cuddle")
        self.assertTrue(response["accepted"])
        self.assertEqual(response["state"]["mode"], "cuddling")
        self.assertEqual(self.event("Victory", "v-during-cuddle")["reason"], "busy")
        self.clock.advance(2.3)
        self.assertEqual(self.pet.status()["mode"], "focus")

    def test_play_stretch_and_look_have_bounded_durations_and_stop_motion(self):
        for command, mode, duration in (("play", "dancing", 5.),
                                        ("stretch", "stretching", 3.5),
                                        ("look", "curious", 4.)):
            self.pet.wake()
            self.pet.move("left")
            state = self.pet.command(command)
            self.assertEqual((state["mode"], state["direction"]), (mode, "stop"))
            self.clock.advance(duration + .1)
            self.assertEqual(self.pet.status()["mode"], "idle")

    def test_attention_is_bounded_expires_and_does_not_wake_a_sleeping_pet(self):
        event = {"type": "attention", "x": .8, "y": -.2}
        self.assertTrue(self.pet.handle_event(event)["accepted"])
        self.assertFalse(self.pet.status()["awake"])
        self.assertFalse(self.pet.status()["hand_present"])
        self.pet.wake()
        self.assertEqual(self.pet.state_fields()["pet_look_x"], "80")
        self.assertEqual(self.pet.state_fields()["pet_hand_present"], "true")
        self.assertFalse(self.pet.handle_event({**event, "x": float("nan")})["accepted"])
        self.assertFalse(self.pet.handle_event({**event, "y": 1.1})["accepted"])
        self.clock.advance(.7)
        self.assertEqual(self.pet.state_fields()["pet_hand_present"], "false")
        self.assertEqual(self.pet.state_fields()["pet_look_x"], "0")

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
