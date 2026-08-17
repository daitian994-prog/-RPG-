import json
import os
import unittest

from backend.services.narrative_authority_service import NarrativeAuthorityService


class FakeSceneAI:
    configured = True

    def __init__(self):
        self.count = 0

    def generate(self, **_kwargs):
        self.count += 1
        proposal = {
            "sceneTitle": f"风痕现场 {self.count}",
            "sceneSummary": f"帕拉斯的第{self.count}阵风卷过石阶，药师护住一只裂开的木箱。",
            "localActors": ["药师"],
            "localObjects": ["裂开的木箱"],
            "immediateProblem": "箱中药草正被雨水浸湿",
            "playerObservableFacts": ["木箱裂开", "雨水正在变大"],
            "suggestedActions": [
                {"semanticAction": "检查木箱上的陌生划痕", "goal": "辨认来路", "approach": "观察细节", "expectedRiskType": "低"},
                {"semanticAction": "询问药师刚才看见了谁", "goal": "确认经过", "approach": "平静沟通", "expectedRiskType": "中"},
                {"semanticAction": "先离开并记下这个位置", "goal": "避免卷入", "approach": "保持距离", "expectedRiskType": "低"},
            ],
        }
        return {"text": json.dumps(proposal, ensure_ascii=False)}


class NarrativeAuthorityTest(unittest.TestCase):
    def setUp(self):
        self.disabled_ai = os.environ.pop("RUNETERRA_DISABLE_REMOTE_AI", None)
        self.envelope = {
            "location": {"id": "pallas", "name": "帕拉斯"},
            "directorIntent": {"intensity": "medium"},
            "hardFacts": ["地点固定为帕拉斯", "世界线程阶段固定为1"],
            "requiredElements": ["现场需要有一个局部问题"],
            "forbiddenChanges": ["不得改变线程阶段"],
            "creativeFreedom": ["创造普通NPC与物件"],
            "heroContext": None,
            "heroEncounter": {"level": 0},
        }
        self.template = {
            "id": "fallback", "type": "探索", "title": "保底现场",
            "components": {"actor": "旅人", "object": "石碑", "setting": "帕拉斯", "pressure": "天色将暗"},
            "choices": [
                {"text": "观察石碑", "hint": "寻找痕迹", "risk": "低"},
                {"text": "询问旅人", "hint": "了解经过", "risk": "中"},
            ],
        }

    def tearDown(self):
        if self.disabled_ai is not None:
            os.environ["RUNETERRA_DISABLE_REMOTE_AI"] = self.disabled_ai

    def test_thirty_scenes_vary_without_mutating_hard_facts(self):
        service = NarrativeAuthorityService(FakeSceneAI())
        scenes = []
        for _ in range(30):
            event, debug = service.materialize(self.envelope, self.template)
            scenes.append(event["text"])
            self.assertEqual(debug["narrativeEnvelope"]["hardFacts"], self.envelope["hardFacts"])
            self.assertEqual(debug["source"], "ai")
        self.assertEqual(len(set(scenes)), 30)

    def test_semantic_actions_are_mapped_only_after_proposal(self):
        service = NarrativeAuthorityService(FakeSceneAI())
        event, debug = service.materialize(self.envelope, self.template)
        self.assertEqual([item.get("attribute") for item in event["choices"]], ["perception", "social", None])
        self.assertFalse(event["choices"][2]["requiresCheck"])
        self.assertTrue(all("mappingReason" in item for item in debug["accepted"]))

    def test_rule_claim_is_rejected_and_falls_back(self):
        ai = FakeSceneAI()
        service = NarrativeAuthorityService(ai)
        original = ai.generate

        def invalid(**kwargs):
            value = original(**kwargs)
            data = json.loads(value["text"])
            data["sceneSummary"] += " 成功率为95%。"
            return {"text": json.dumps(data, ensure_ascii=False)}

        ai.generate = invalid
        _event, debug = service.materialize(self.envelope, self.template)
        self.assertEqual(debug["source"], "fallback")
        self.assertTrue(debug["rejectedSceneFacts"])


if __name__ == "__main__":
    unittest.main()
