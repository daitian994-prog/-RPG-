import copy
import unittest

from backend.services.dynamic_event_service import DynamicEventService
from backend.services.event_director_service import EventDirectorService
from backend.services.world_thread_service import WorldThreadService


class EventDirectorServiceTest(unittest.TestCase):
    def setUp(self):
        self.director = EventDirectorService()
        self.generator = DynamicEventService()
        self.world_threads = WorldThreadService()
        self.state = {
            "id": "director-test", "time": {"total_actions": 0},
            "player": {"bodyCondition": {"label": "良好", "state": "healthy"}, "coreAbilities": {key: 9 for key in ("martial", "physique", "perception", "willpower", "agility", "social")}},
            "worldState": self.world_threads.initial_state(), "directorState": self.director.initial_state(),
        }

    def pool(self, location="windbreak"):
        return self.generator.generate_pool(self.state, location)

    def test_candidates_expose_components_and_complete_weight_snapshot(self):
        candidates = self.director.candidates(self.state, "windbreak", self.pool())
        self.assertTrue(candidates)
        for candidate in candidates:
            self.assertTrue(candidate["templateId"].startswith("dyn-"))
            self.assertTrue(candidate["dynamicComponents"])
            self.assertGreater(candidate["finalWeight"], 0)
            self.assertEqual(set(candidate["modifiers"]), {"threadStage", "urgency", "tension", "recentHistory", "playerFocus", "worldRelevance", "narrativeBudget", "randomFactor"})

    def test_director_reads_world_threads_without_advancing_them(self):
        before = copy.deepcopy(self.state["worldState"])
        self.director.select(self.state, "pallas", self.pool("pallas"))
        self.assertEqual(before, self.state["worldState"])

    def test_focus_increases_related_weight_without_monopoly(self):
        thread = self.state["worldState"]["activeThreads"][0]
        thread["awareness"] = 30
        before = self.director.candidates(self.state, "windbreak", self.pool("windbreak"))
        before_weight = next(item["finalWeight"] for item in before if item.get("threadId") == thread["id"])
        self.director.set_focus(self.state, thread["id"], True)
        after = self.director.candidates(self.state, "windbreak", self.pool("windbreak"))
        focused = next(item for item in after if item.get("threadId") == thread["id"])
        self.assertEqual(focused["modifiers"]["playerFocus"], 1.25)
        self.assertGreater(focused["finalWeight"], before_weight)
        self.assertTrue(any(item["category"] != "world_thread" for item in after))

    def test_forty_explorations_generate_more_than_twenty_unique_events(self):
        locations = ["pallas", "windbreak", "war_ruins", "mountain_temple"]
        generated_ids, selected, component_sets = set(), [], set()
        for index in range(40):
            location = locations[index % 4]
            self.state["time"]["total_actions"] = index + 1
            self.state["worldState"]["worldTime"] = index + 1
            pool = self.pool(location)
            generated_ids.update(item["id"] for item in pool)
            component_sets.update(tuple(item["components"].values()) for item in pool)
            choice = self.director.select(self.state, location, pool)
            selected.append(choice)
            self.director.record_selection(self.state, choice)
        self.assertGreater(len(generated_ids), 300)
        self.assertGreater(len(component_sets), 80)
        self.assertTrue(all(not item["templateId"].startswith("e") for item in selected))
        self.assertIn("world_thread", {item["category"] for item in selected})
        self.assertIn("hero", {item["category"] for item in selected})

    def test_same_snapshot_builds_same_pool_and_selection(self):
        first_state, second_state = copy.deepcopy(self.state), copy.deepcopy(self.state)
        first_pool = self.generator.generate_pool(first_state, "war_ruins")
        second_pool = self.generator.generate_pool(second_state, "war_ruins")
        self.assertEqual(first_pool, second_pool)
        first = self.director.select(first_state, "war_ruins", first_pool)
        second = self.director.select(second_state, "war_ruins", second_pool)
        self.assertEqual(first["candidateId"], second["candidateId"])
        self.assertEqual(first["seed"], second["seed"])

    def test_resolved_thread_exposes_effects_and_follow_up_hooks(self):
        thread = self.state["worldState"]["activeThreads"][0]
        thread["stage"] = thread["maxStage"]
        thread["resolved"] = True
        thread["resolvedOutcome"] = copy.deepcopy(thread["naturalOutcome"])
        candidate = next(item for item in self.director.candidates(self.state, "pallas", self.pool("pallas")) if item.get("threadId") == thread["id"])
        context = self.director.context(self.state, candidate, "帕拉斯")
        self.assertEqual(candidate["intent"], "aftermath")
        self.assertIn("山道戒严", context)
        self.assertIn("营救被俘村民", context)


if __name__ == "__main__":
    unittest.main()
