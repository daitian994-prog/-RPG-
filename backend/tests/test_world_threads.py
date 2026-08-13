import unittest

from backend.services.world_thread_service import WorldThreadService


class WorldThreadServiceTest(unittest.TestCase):
    def setUp(self):
        self.service = WorldThreadService()
        self.state = {"time": {"total_actions": 0}, "worldState": self.service.initial_state()}

    def tick(self, amount=1, location="pallas"):
        for _ in range(amount):
            self.state["time"]["total_actions"] += 1
            self.service.advance(self.state, action="test", location=location)

    def thread(self, thread_id):
        return next(item for item in self.state["worldState"]["activeThreads"] if item["id"] == thread_id)

    def test_threads_progress_without_player_participation_and_resolve(self):
        self.tick(14, location="war_ruins")
        thread = self.thread("noxian_remnants")
        self.assertTrue(thread["resolved"])
        self.assertEqual(thread["resolvedOutcome"]["id"], "villagers_captured")
        self.assertIn("villagers_captured", self.state["worldState"]["globalFlags"])
        self.assertIn("营救被俘村民", self.state["worldState"]["followUpHooks"])

    def test_progress_and_awareness_are_independent(self):
        self.tick(4, location="war_ruins")
        thread = self.thread("noxian_remnants")
        self.assertGreaterEqual(thread["stage"], 3)
        self.assertEqual(thread["awareness"], 10)

    def test_fairness_gate_emits_forced_warning_before_irreversible_stage(self):
        self.tick(4, location="war_ruins")
        thread = self.thread("noxian_remnants")
        self.assertEqual(thread["stage"], 4)
        self.state["time"]["total_actions"] += 1
        signals = self.service.advance(self.state, action="test", location="war_ruins")
        self.assertEqual(thread["stage"], 4)
        self.assertGreaterEqual(thread["awareness"], 60)
        self.assertTrue(signals[0]["forcedOpportunity"])
        self.assertEqual(thread["interventionWindow"], "CLOSING")

    def test_active_intervention_changes_natural_outcome(self):
        thread = self.thread("noxian_remnants")
        thread["awareness"] = 65
        thread["stage"] = 3
        self.service.intervene(self.state, thread["id"], "intervene")
        self.assertEqual(thread["selectedOutcome"]["id"], "remnants_disrupted")
        self.assertEqual(thread["stage"], 2)

    def test_delayed_intervention_is_allowed_while_closing_but_not_closed(self):
        thread = self.thread("spirit_anomaly")
        thread["stage"] = 4
        thread["awareness"] = 70
        thread["interventionWindow"] = "CLOSING"
        self.service.intervene(self.state, thread["id"], "intervene")
        self.assertEqual(thread["selectedOutcome"]["id"], "spirit_stabilized")
        thread["interventionWindow"] = "CLOSED"
        with self.assertRaises(ValueError):
            self.service.intervene(self.state, thread["id"], "intervene")


if __name__ == "__main__":
    unittest.main()
