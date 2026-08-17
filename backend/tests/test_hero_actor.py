import unittest

from backend.services.hero_actor_service import HeroActorService
from backend.services.outcome_engine import OutcomeEngine
from backend.services.world_thread_service import WorldThreadService


class DummyLore:
    @staticmethod
    def champion(_hero_id):
        return {"name": "亚索", "title": "疾风剑豪", "profile": "流浪剑客", "motivation": "调查异动"}


class HeroActorTest(unittest.TestCase):
    def setUp(self):
        self.service = HeroActorService()
        self.state = {
            "id": "hero-test", "time": {"total_actions": 0}, "location": "pallas",
            "worldState": WorldThreadService().initial_state(),
            "directorState": {"narrativeBudget": {"heroUsed": 0}},
            "heroActors": self.service.initial_state(), "heroActionLog": [], "heroRelationships": {},
        }

    def test_twenty_ticks_follow_routes_and_do_not_solve_thread(self):
        thread = next(item for item in self.state["worldState"]["activeThreads"] if item["id"] == "noxian_remnants")
        initial_stage = thread["stage"]
        routes = self.service.templates["yasuo"]["routeGraph"]
        for world_time in range(1, 21):
            self.state["worldState"]["worldTime"] = world_time
            previous = self.state["heroActors"]["yasuo"]["currentLocation"]
            action = self.service.tick(self.state)
            current = self.state["heroActors"]["yasuo"]["currentLocation"]
            self.assertIn(current, routes[previous])
            self.assertIn(action["type"], {"move_toward_goal", "investigate_noxus"})
        self.assertEqual(thread["stage"], initial_stage)
        self.assertFalse(thread["resolved"])
        self.assertLessEqual(self.state["heroActors"]["yasuo"]["goalProgress"], 100)

    def test_all_encounter_levels_are_reachable(self):
        runtime = self.state["heroActors"]["yasuo"]
        self.assertEqual(self.service.encounter(self.state, "pallas", force_level=0)["levelName"], "none")
        runtime["currentLocation"] = "war_ruins"
        runtime["lastAction"] = {"location": "pallas", "publicTrace": "一道剑痕"}
        self.assertEqual(self.service.encounter(self.state, "pallas")["levelName"], "trace")
        runtime["lastAction"]["publicRumor"] = "背剑浪人来过"
        self.assertEqual(self.service.encounter(self.state, "pallas")["levelName"], "rumor")
        runtime["currentLocation"] = "pallas"
        runtime["lastEncounterTime"] = 0
        self.assertEqual(self.service.encounter(self.state, "pallas")["levelName"], "glimpse")
        runtime["playerRelation"]["recognition"] = 10
        self.assertEqual(self.service.encounter(self.state, "pallas")["levelName"], "interaction")
        runtime["playerRelation"].update({"recognition": 30, "trust": 20})
        self.assertEqual(self.service.encounter(self.state, "pallas")["levelName"], "cooperation")

    def test_important_memory_is_written_and_available_to_later_prompt(self):
        engine = OutcomeEngine()
        director = {"heroId": "yasuo", "eventId": "yasuo-meeting", "threadId": "noxian_remnants", "intent": "investigation"}
        choice = {"id": "help", "semanticAction": "协助调查斥候痕迹", "result": {"personality": {"peace": 2}}}
        feedback = engine.apply_world_feedback(self.state, director, {"code": "success", "label": "成功"}, choice)
        memories = self.state["heroActors"]["yasuo"]["importantMemories"]
        self.assertEqual(len(memories), 1)
        self.assertEqual(feedback["hero"]["importantMemory"]["id"], memories[0]["id"])
        prompt = self.service.canon_prompt(DummyLore(), self.state)
        self.assertEqual(prompt["runtime"]["importantMemories"][0]["summary"], memories[0]["summary"])
        prompt["runtime"]["importantMemories"][0]["summary"] = "changed copy"
        self.assertNotEqual(prompt["runtime"]["importantMemories"][0]["summary"], memories[0]["summary"])


if __name__ == "__main__":
    unittest.main()
