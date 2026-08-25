import json
import unittest

from backend.services.ai_service import AIService


class FakeAuditRemote:
    configured = True

    def __init__(self, verdict="PASS"):
        self.verdict = verdict
        self.prompts = []

    def generate(self, **kwargs):
        self.prompts.append(kwargs)
        issues = []
        if self.verdict == "REPAIR":
            issues = [{
                "field": "narrative",
                "type": "DOES_NOT_ANSWER_ACTION",
                "reason": "正文没有回答玩家选择的目标",
                "repairInstruction": "让结果明确回应本轮玩家行动",
            }]
        return {"text": json.dumps({"verdict": self.verdict, "issues": issues}, ensure_ascii=False)}


class ContextAuditTest(unittest.TestCase):
    def setUp(self):
        self.scene = {
            "round": 2, "actors": ["药师"], "objects": ["裂开的木箱"],
            "facts": ["木箱裂口来自外侧"], "questions": ["谁动过木箱？"],
            "currentFocus": "木箱裂口的来源", "previousActions": [{"text": "检查木箱裂口"}],
        }
        self.choice = {
            "semanticAction": "询问药师谁靠近过木箱", "goal": "确认接触过木箱的人",
            "approach": "核对药师证词", "actionTags": ["social"], "targetTags": ["药师"],
        }
        self.result = {
            "narrative": "药师回忆起刚才靠近木箱的人，并指出对方离开的方向。",
            "factsAdded": ["药师看见一名脚夫靠近木箱"], "questionsAdded": [],
            "questionsResolved": ["谁动过木箱？"], "npcReactions": ["药师愿意作证"],
            "sceneDecision": {"continueScene": False, "reason": "问题已回答", "nextFocus": ""},
        }

    def test_result_auditor_accepts_contextual_result(self):
        service = AIService()
        remote = FakeAuditRemote("PASS")
        service.remote_ai = remote
        audit, raw = service.audit_scene_result(self.scene, self.choice, self.result)
        self.assertEqual(audit["verdict"], "PASS")
        self.assertEqual(service.audit_repair_feedback(audit), [])
        self.assertIn("独立结果审核员", remote.prompts[0]["system"])
        self.assertTrue(raw)

    def test_result_auditor_returns_field_level_repair_instruction(self):
        service = AIService()
        service.remote_ai = FakeAuditRemote("REPAIR")
        audit, _raw = service.audit_scene_result(self.scene, self.choice, self.result)
        self.assertEqual(audit["verdict"], "REPAIR")
        self.assertEqual(service.audit_repair_feedback(audit), ["narrative：让结果明确回应本轮玩家行动"])


if __name__ == "__main__":
    unittest.main()
