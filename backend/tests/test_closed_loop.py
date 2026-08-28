import copy
import unittest

from backend.services.check_engine import CheckEngine, CheckRequest
from backend.services.dynamic_event_service import DynamicEventService
from backend.services.event_context_service import EventContextService
from backend.services.event_director_service import EventDirectorService
from backend.services.narrator_contract import NarratorContract
from backend.services.outcome_engine import OutcomeEngine
from backend.services.world_thread_service import WorldThreadService


class ClosedLoopTest(unittest.TestCase):
    def setUp(self):
        self.world = WorldThreadService()
        self.director = EventDirectorService()
        self.generator = DynamicEventService()
        self.outcomes = OutcomeEngine()
        self.locations = [{"id": "pallas", "name": "帕拉斯"}, {"id": "windbreak", "name": "断风森林"}, {"id": "war_ruins", "name": "战争遗迹"}, {"id": "mountain_temple", "name": "山间寺庙"}]
        self.state = {
            "id": "closed-loop", "season": "第一年 · 春", "location": "pallas",
            "time": {"total_actions": 2}, "action_points": 2,
            "player": {
                "name": "测试者", "coreAbilities": {key: 9 for key in ("martial", "physique", "perception", "willpower", "agility", "social")},
                "bodyCondition": {"label": "良好"}, "personality": {"peace": 40},
                "statuses": [], "traits": [], "clues": [], "inventory": [], "injurySeverity": 0,
            },
            "relationships": {}, "heroRelationships": {}, "stateChangeLog": [],
            "worldState": self.world.initial_state(), "directorState": self.director.initial_state(),
        }

    def test_event_context_has_complete_authoritative_protocol(self):
        events = self.generator.generate_pool(self.state, "pallas")
        selection = self.director.select(self.state, "pallas", events)
        selection["directorContext"] = self.director.context(self.state, selection, "帕拉斯")
        template = next(item for item in events if item["id"] == selection["templateId"])
        context = EventContextService().build(self.state, self.locations[0], selection, template)
        required = {"location", "time", "playerSummary", "statuses", "traits", "clues", "activeThreadsSummary", "directorIntent", "selectedCandidate", "eventIntent", "hardFacts", "forbiddenChanges"}
        self.assertTrue(required.issubset(context))
        self.assertGreaterEqual(len(context["forbiddenChanges"]), 6)
        self.assertNotIn("probability", context["selectedCandidate"])

    def test_narrator_contract_rejects_gameplay_authority(self):
        contract = NarratorContract()
        valid = contract.validate('{"narrative":"你听见风穿过树林。","choicePresentation":[],"npcDialogue":[],"flavorTags":[]}')
        invalid = contract.validate('{"narrative":"你成功了。","probability":95,"stage":6}')
        invented_reward = contract.validate('{"narrative":"你把陌生军牌收进怀里。","choicePresentation":[],"npcDialogue":[],"flavorTags":[]}')
        self.assertTrue(valid["valid"])
        self.assertFalse(invalid["valid"])
        self.assertFalse(invented_reward["valid"])
        self.assertTrue(any("未授权" in item or "规则" in item for item in invalid["errors"]))

    def test_world_feedback_never_changes_thread_stage_and_failure_creates_play(self):
        thread = self.state["worldState"]["activeThreads"][0]
        before_stage = thread["stage"]
        director = {"threadId": thread["id"], "eventId": "e01@x", "intent": "conflict"}
        feedback = self.outcomes.apply_world_feedback(self.state, director, {"code": "failure"}, {"id": "choice-a"})
        self.assertEqual(thread["stage"], before_stage)
        self.assertIsNotNone(feedback["newPlayableSituation"])
        self.assertIn(feedback["newPlayableSituation"], self.state["worldState"]["followUpHooks"])

    def test_hero_relation_is_program_owned_and_remembers_history(self):
        feedback = self.outcomes.apply_world_feedback(self.state, {"heroId": "shen", "eventId": "e08@x"}, {"code": "critical"}, {"id": "a"})
        self.assertEqual(feedback["hero"]["delta"], 6)
        self.assertEqual(self.state["heroRelationships"]["shen"]["score"], 6)
        self.assertEqual(len(self.state["heroRelationships"]["shen"]["history"]), 1)

    def test_ai_result_validator_accepts_specific_progress_and_rejects_thread_stage_changes(self):
        scene = {
            "id": "bell", "round": 1, "maxRounds": 4, "actors": ["寺庙老人"], "objects": ["铜钟"],
            "facts": ["铜钟没有撞槌"], "questions": ["铜钟为什么震动？"], "ended": False,
        }
        outcome = {"code": "success", "label": "成功"}
        choice = {"id": "inspect", "semanticAction": "检查钟座", "attribute": "perception", "result": {}}
        valid = {
            "narrative": "你在钟座下方找到一道持续渗出冷气的裂隙，寺庙老人俯身确认后，第一次说出昨夜也听见过地下回声。",
            "factsAdded": ["铜钟的震动来自钟座下方的裂隙"], "questionsAdded": ["裂隙通向哪里？"],
            "questionsResolved": ["铜钟为什么震动？"], "npcReactions": ["寺庙老人确认昨夜听见地下回声"],
            "sceneDecision": {"continueScene": True, "reason": "地下裂隙仍在现场形成一个必须立即判断的问题。", "nextFocus": "钟座下方的裂隙"},
            "continueScene": True, "suggestedClue": None,
        }
        accepted, debug = self.outcomes.validate_ai_result(valid, scene, outcome, choice, {"threadId": "spirit_anomaly"}, self.state)
        self.assertTrue(debug["valid"])
        self.assertIsNotNone(accepted)
        invalid = {**valid, "narrative": valid["narrative"] + " 世界线程阶段推进至第六阶段。"}
        rejected, debug = self.outcomes.validate_ai_result(invalid, scene, outcome, choice, {"threadId": "spirit_anomaly"}, self.state)
        self.assertIsNone(rejected)
        self.assertTrue(any("Thread Stage" in item for item in debug["errors"]))

    def test_state_change_log_is_auditable_and_bounded(self):
        for index in range(55):
            before = self.outcomes.snapshot(self.state)
            self.state["action_points"] = index
            self.outcomes.record(self.state, "simulation", before, metadata={"index": index})
        self.assertEqual(len(self.state["stateChangeLog"]), 50)
        self.assertTrue(self.state["stateChangeLog"][-1]["changes"])

    def test_lead_disposition_requires_scene_closure_and_valid_replacement(self):
        current = {
            "id": "lead-a", "title": "不明脚印", "summary": "林中有不明脚印", "trackable": True,
            "status": "active", "relatedLocations": ["windbreak"], "threadId": "noxian_remnants",
        }
        self.state["journal"] = [current]
        self.state["playerIntent"] = {"kind": "track_lead", "leadId": "lead-a", "threadId": "noxian_remnants"}
        scene = {"questions": ["脚印由谁留下？"], "facts": [], "actors": [], "objects": ["脚印"]}
        outcome = {"code": "success"}
        choice = {"semanticAction": "检查脚印", "attribute": "perception", "result": {}}
        base = {
            "narrative": "你逐一比对脚印的深浅和步幅，确认它们来自穿着靴子的人类，并且沿着旧军道离开了森林。",
            "factsAdded": ["脚印来自人类"], "questionsAdded": [], "questionsResolved": ["脚印由谁留下？"],
            "npcReactions": [], "sceneDecision": {"continueScene": False, "reason": "原问题已经回答。", "nextFocus": ""},
            "suggestedClue": None, "suggestedLead": None,
        }
        resolved, debug = self.outcomes.validate_ai_result(
            {**base, "leadDisposition": "RESOLVED"}, scene, outcome, choice, {"threadId": "noxian_remnants"}, self.state,
        )
        self.assertTrue(debug["valid"])
        self.assertEqual(resolved["leadDisposition"], "RESOLVED")
        rejected, debug = self.outcomes.validate_ai_result(
            {**base, "leadDisposition": "SUPERSEDED"}, scene, outcome, choice, {"threadId": "noxian_remnants"}, self.state,
        )
        self.assertIsNone(rejected)
        self.assertTrue(any("SUPERSEDED" in item for item in debug["errors"]))

    def test_three_builds_and_probability_calibration(self):
        engine = CheckEngine()
        builds = {"martial": 11, "perception": 11, "agility": 11}
        observed = {}
        for attribute, ability in builds.items():
            success = 0
            for index in range(1000):
                request = CheckRequest("calibration", "phase4", f"{attribute}-{index}", attribute, ability, 9, str(index))
                result = engine.execute(request)
                success += result["tier"] in {"critical", "success"}
            observed[attribute] = success / 10
        self.assertTrue(all(abs(rate - 72) < 5 for rate in observed.values()), observed)

    def test_36_explorations_keep_world_selector_varied(self):
        selections = []
        for index in range(36):
            state = self.state
            state["time"]["total_actions"] = index + 1
            state["worldState"]["worldTime"] = index + 1
            location = self.locations[index % 4]["id"]
            events = self.generator.generate_pool(state, location)
            selection = self.director.select(state, location, events)
            selections.append(selection)
            self.director.record_selection(state, selection)
        self.assertEqual(len({item["templateId"] for item in selections}), 36)
        self.assertGreaterEqual(len({item["intent"] for item in selections}), 6)
        self.assertIn("world_thread", {item["category"] for item in selections})


if __name__ == "__main__":
    unittest.main()
