import copy
import json
import unittest
from pathlib import Path

from backend.services.event_director_service import EventDirectorService
from backend.services.world_thread_service import WorldThreadService


DATA_DIR = Path(__file__).resolve().parents[2] / "game-data"


class EventDirectorServiceTest(unittest.TestCase):
    def setUp(self):
        self.director = EventDirectorService()
        self.world_threads = WorldThreadService()
        self.events = json.loads((DATA_DIR / "events.json").read_text(encoding="utf-8"))
        self.state = {
            "id": "director-test",
            "time": {"total_actions": 0},
            "player": {"bodyCondition": {"label": "良好"}},
            "worldState": self.world_threads.initial_state(),
            "directorState": self.director.initial_state(),
        }

    def test_candidates_expose_complete_weight_snapshot(self):
        candidates = self.director.candidates(self.state, "windbreak", self.events)
        self.assertTrue(candidates)
        for candidate in candidates:
            self.assertGreater(candidate["finalWeight"], 0)
            self.assertEqual(
                set(candidate["modifiers"]),
                {"threadStage", "urgency", "tension", "recentHistory", "playerFocus", "worldRelevance", "narrativeBudget", "randomFactor"},
            )
            self.assertGreaterEqual(candidate["modifiers"]["randomFactor"], 0.85)
            self.assertLessEqual(candidate["modifiers"]["randomFactor"], 1.15)

    def test_director_reads_world_threads_without_advancing_them(self):
        before = copy.deepcopy(self.state["worldState"])
        self.director.select(self.state, "pallas", self.events)
        self.assertEqual(before, self.state["worldState"])

    def test_focus_increases_related_weight_without_monopoly(self):
        thread = self.state["worldState"]["activeThreads"][0]
        thread["awareness"] = 30
        before = self.director.candidates(self.state, "windbreak", self.events)
        before_weight = next(item["finalWeight"] for item in before if item.get("threadId") == thread["id"])
        result = self.director.set_focus(self.state, thread["id"], True)
        after = self.director.candidates(self.state, "windbreak", self.events)
        after_candidate = next(item for item in after if item.get("threadId") == thread["id"])
        after_weight = after_candidate["finalWeight"]
        self.assertTrue(result["focused"])
        self.assertEqual(after_candidate["modifiers"]["playerFocus"], 1.25)
        self.assertGreater(after_weight, before_weight)
        self.assertTrue(any(item["category"] != "world_thread" and item["finalWeight"] > 0 for item in after))

    def test_thirty_explorations_are_seeded_varied_and_auditable(self):
        locations = ["pallas", "windbreak", "war_ruins", "mountain_temple"]
        selections = []
        for index in range(30):
            location = locations[index % len(locations)]
            self.state["time"]["total_actions"] = index + 1
            self.state["worldState"]["worldTime"] = index + 1
            selection = self.director.select(self.state, location, self.events)
            selections.append(selection)
            self.director.record_selection(self.state, selection)
        categories = {item["category"] for item in selections}
        templates = {item["templateId"] for item in selections}
        intents = {item["intent"] for item in selections}
        self.assertEqual(categories, {"environment", "world_thread", "personal", "hero"})
        self.assertIn("world_thread", categories)
        self.assertGreaterEqual(len(templates), 10)
        self.assertGreaterEqual(len(intents), 6)
        self.assertEqual(len({item["eventId"] for item in selections}), 30)
        self.assertTrue(all(item["candidateWeights"] for item in selections))
        longest_repeat = 1
        current_repeat = 1
        for previous, current in zip(selections, selections[1:]):
            if previous["templateId"] == current["templateId"]:
                current_repeat += 1
                longest_repeat = max(longest_repeat, current_repeat)
            else:
                current_repeat = 1
        self.assertLessEqual(longest_repeat, 2)

    def test_same_snapshot_selects_same_event(self):
        first = self.director.select(copy.deepcopy(self.state), "war_ruins", self.events)
        second = self.director.select(copy.deepcopy(self.state), "war_ruins", self.events)
        self.assertEqual(first["candidateId"], second["candidateId"])
        self.assertEqual(first["seed"], second["seed"])

    def test_resolved_thread_exposes_effects_and_follow_up_hooks_to_narrator(self):
        thread = self.state["worldState"]["activeThreads"][0]
        thread["stage"] = thread["maxStage"]
        thread["resolved"] = True
        thread["resolvedOutcome"] = copy.deepcopy(thread["naturalOutcome"])
        candidate = next(
            item for item in self.director.candidates(self.state, "pallas", self.events)
            if item.get("threadId") == thread["id"]
        )
        context = self.director.context(self.state, candidate, "帕拉斯")
        self.assertEqual(candidate["intent"], "aftermath")
        self.assertIn("山道戒严", context)
        self.assertIn("营救被俘村民", context)


if __name__ == "__main__":
    unittest.main()
