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
        scene = "\n\n".join([
            f"帕拉斯的第{self.count}阵风卷过石阶，雨水沿屋檐落进浅沟，药草与湿木的气味被吹到路中央。原本忙着收摊的人忽然安静下来，纷纷望向药铺门前。",
            "药师正护着一只裂开的木箱，箱角留有陌生划痕，几束药草已经被雨水浸湿。送货的脚夫坚持箱子离手时完好无损，旁边的学徒却说刚才有人在巷口停留。",
            "你先查看地面的水痕，又留意到木箱裂口并不是从内侧撑开。药师没有催你，却始终挡在箱盖前；围观者各自说着猜测，谁也不愿承担打开它可能带来的风险。",
            "雨势正在加重，更多痕迹很快就会被冲掉，脚夫也准备离开。现在检查木箱或追问目击者都可能接近真相，也可能惊动留下划痕的人；如果退开，眼前唯一清楚的线索就会消失。",
        ])
        proposal = {
            "sceneTitle": f"风痕现场 {self.count}",
            "sceneSummary": scene,
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
        self.template["choices"][0]["result"] = {"items": ["不相关奖励"], "clues": [{"name": "不相关线索"}], "statuses": [{"name": "不相关状态"}]}
        event, debug = service.materialize(self.envelope, self.template)
        self.assertEqual([item.get("attribute") for item in event["choices"]], ["perception", "social", None])
        self.assertFalse(event["choices"][2]["requiresCheck"])
        self.assertTrue(all("mappingReason" in item for item in debug["accepted"]))
        self.assertTrue(all(not ({"items", "clues", "statuses"} & set(item["result"])) for item in event["choices"]))

    def test_rule_claim_is_rejected_and_uses_dynamic_synthesis(self):
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
        self.assertEqual(debug["source"], "dynamic_synthesis")
        self.assertTrue(debug["rejectedSceneFacts"])

    def test_offline_synthesis_is_full_length_grounded_and_has_no_old_templates(self):
        class OfflineAI:
            configured = False

        service = NarrativeAuthorityService(OfflineAI())
        event, debug = service.materialize(self.envelope, self.template)
        self.assertEqual(debug["source"], "dynamic_synthesis")
        self.assertGreaterEqual(len("".join(event["text"].split())), 220)
        self.assertGreaterEqual(len(event["text"].split("\n\n")), 4)
        self.assertNotIn("已经确定的结果", json.dumps(event, ensure_ascii=False))
        visible = json.dumps(event["choices"], ensure_ascii=False)
        for stale in ("沿新鲜脚印追查去向", "见过哪些相似足迹", "在背风处等待留下脚印的人返回", "记下方向并离开森林"):
            self.assertNotIn(stale, visible)
        self.assertTrue(all(any(entity in item["text"] for entity in ("石碑", "天色将暗", "旅人")) for item in event["choices"]))

    def test_short_ai_scene_is_retried_then_safely_expanded(self):
        ai = FakeSceneAI()
        original = ai.generate

        def short(**kwargs):
            value = original(**kwargs)
            data = json.loads(value["text"])
            data["sceneTitle"] = "药箱上的陌生划痕"
            data["sceneSummary"] = "雨水落在药箱上，药师正等待你判断划痕的来历。"
            return {"text": json.dumps(data, ensure_ascii=False)}

        ai.generate = short
        event, debug = NarrativeAuthorityService(ai).materialize(self.envelope, self.template)
        self.assertEqual(ai.count, 2)
        self.assertEqual(debug["source"], "ai_repaired")
        self.assertEqual(event["title"], "药箱上的陌生划痕")
        self.assertGreaterEqual(len("".join(event["text"].split())), 220)
        self.assertEqual(event["choices"][0]["semanticAction"], "检查木箱上的陌生划痕")

    def test_next_round_synthesis_uses_latest_focus_and_not_old_action(self):
        class OfflineAI:
            configured = False

        service = NarrativeAuthorityService(OfflineAI())
        scene = {
            "round": 2, "actors": ["老猎人"], "objects": ["铜铃", "新鲜脚印"],
            "facts": ["出现一组方向相反的新鲜脚印"], "questions": ["是谁留下了这组新鲜脚印？"],
            "currentFocus": "新鲜脚印的来源",
            "previousActions": [{"text": "检查铜铃附近痕迹", "actionTags": ["investigate"], "targetTags": ["铜铃"]}],
            "lastAction": {"text": "检查铜铃附近痕迹"}, "lastResult": {"checkResult": {"code": "success"}},
        }
        actions, debug = service.next_actions(scene, self.envelope, self.template, 8)
        texts = [item["text"] for item in actions]
        self.assertTrue(all("新鲜脚印的来源" in text or "铜铃" in text or "老猎人" in text for text in texts))
        self.assertNotIn("沿着新鲜脚印追查它的去向", texts)
        self.assertNotIn("检查铜铃附近痕迹", texts)
        self.assertEqual(debug["currentFocus"], "新鲜脚印的来源")
        self.assertEqual(debug["previousActions"][0]["text"], "检查铜铃附近痕迹")
        self.assertTrue(all(not item["hint"] for item in actions))

    def test_context_auditor_requests_targeted_repair_before_acceptance(self):
        class AuditAwareAI(FakeSceneAI):
            def __init__(self):
                super().__init__()
                self.audits = 0

            def generate(self, **kwargs):
                if "独立上下文审核员" in kwargs.get("system", ""):
                    self.audits += 1
                    verdict = "REPAIR" if self.audits == 1 else "PASS"
                    issues = [{
                        "field": "suggestedActions[0]", "type": "REPEATS_RESOLVED_QUESTION",
                        "reason": "重复旧问题", "repairInstruction": "围绕当前木箱裂口重写行动",
                    }] if verdict == "REPAIR" else []
                    return {"text": json.dumps({"verdict": verdict, "issues": issues}, ensure_ascii=False)}
                return super().generate(**kwargs)

        ai = AuditAwareAI()
        event, debug = NarrativeAuthorityService(ai).materialize(self.envelope, self.template)
        self.assertEqual(debug["source"], "ai_context_repaired")
        self.assertEqual(ai.audits, 1)
        self.assertGreaterEqual(ai.count, 2)
        self.assertTrue(event["choices"])

    def test_action_guard_rejects_same_action_tag_target_and_meaning(self):
        service = NarrativeAuthorityService(FakeSceneAI())
        proposals = [
            {"semanticAction": "再次检查铜钟", "goal": "确认震动", "approach": "观察", "expectedRiskType": "中", "target": "铜钟"},
            {"semanticAction": "询问寺庙老人是否听过回声", "goal": "确认昨夜经过", "approach": "沟通", "expectedRiskType": "低", "target": "寺庙老人"},
            {"semanticAction": "离开铜钟所在的回廊", "goal": "结束风险", "approach": "保持距离", "expectedRiskType": "低", "target": "回廊"},
        ]
        actions, debug = service.map_actions(
            proposals, self.envelope, 8, [],
            previous_actions=[{"text": "检查铜钟", "actionTags": ["investigate"], "targetTags": ["铜钟"]}],
            current_focus="地下回声", current_round=2,
        )
        self.assertNotIn("再次检查铜钟", [item["text"] for item in actions])
        self.assertTrue(any("重复" in item["reason"] for item in debug["rejectedActions"]))


if __name__ == "__main__":
    unittest.main()
