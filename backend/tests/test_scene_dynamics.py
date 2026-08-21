import copy
import unittest

from backend.services.outcome_engine import OutcomeEngine


class SceneDynamicsTest(unittest.TestCase):
    def setUp(self):
        self.outcomes = OutcomeEngine()
        self.outcome = {"code": "success", "label": "成功", "roll": 42, "final_probability": 70, "attribute_label": "灵觉"}
        self.validator = {"valid": True, "errors": []}

    @staticmethod
    def _scene(name: str) -> dict:
        return {
            "id": name, "round": 1, "maxRounds": 4,
            "actors": ["现场见证人"], "objects": ["异常痕迹"],
            "facts": [f"{name}的初始事实"], "questions": [f"{name}的核心问题？"],
            "actions": [{"id": "old-action", "text": "检查最初的痕迹"}],
            "previousActions": [], "currentFocus": f"{name}的核心问题",
            "ended": False, "continueScene": True,
            "loopGuard": {"stagnantRounds": 0, "forcedClosure": False},
        }

    @staticmethod
    def _result(scene: dict, *, continue_scene: bool, index: int) -> dict:
        question = scene["questions"][0]
        next_question = f"第{index + 1}个即时问题？" if continue_scene else ""
        return {
            "narrative": f"你处理了当前焦点，现场出现了足以改变判断的具体事实；在场者确认了这一变化，并据此重新判断眼前的局面。第{index}次结果已经发生。",
            "factsAdded": [f"第{index}轮新增事实"],
            "questionsAdded": [next_question] if next_question else [],
            "questionsResolved": [question], "npcReactions": ["见证人确认变化"],
            "actorsAdded": [], "objectsAdded": [],
            "sceneDecision": {
                "continueScene": continue_scene,
                "reason": "仍有必须现在处理的新决策。" if continue_scene else "核心问题已解决，当前没有即时后果。",
                "nextFocus": next_question.rstrip("？") if continue_scene else "",
            },
            "continueScene": continue_scene, "suggestedClue": None,
        }

    def test_ten_scenes_end_at_varied_natural_depths(self):
        expected_depths = [1, 2, 3, 1, 2, 3, 1, 2, 3, 4]
        observed = []
        for scene_index, expected_depth in enumerate(expected_depths):
            scene = self._scene(f"scene-{scene_index}")
            for round_index in range(1, expected_depth + 1):
                should_continue = round_index < expected_depth
                choice = {
                    "id": f"action-{round_index}", "semanticAction": f"处理第{round_index}个新焦点",
                    "goal": "解决当前问题", "actionTags": [f"action-{round_index}"],
                    "targetTags": [f"focus-{round_index}"],
                }
                ended = self.outcomes.update_scene_state(
                    scene, self._result(scene, continue_scene=should_continue, index=round_index),
                    choice, self.outcome, self.validator,
                )
                self.assertEqual(scene["actions"], [])
                if should_continue:
                    self.assertFalse(ended)
                    self.assertTrue(scene["currentFocus"])
                else:
                    self.assertTrue(ended)
            observed.append(scene["lastResult"]["round"])
        self.assertEqual(observed, expected_depths)
        self.assertIn(1, observed)
        self.assertIn(2, observed)
        self.assertIn(3, observed)
        self.assertNotEqual(set(observed), {4})

    def test_max_rounds_is_only_a_hard_safety_limit(self):
        scene = self._scene("limit")
        scene["round"] = 4
        result = self._result(scene, continue_scene=True, index=4)
        ended = self.outcomes.update_scene_state(
            scene, result, {"id": "keep-going", "semanticAction": "追查新变化", "actionTags": ["investigate"], "targetTags": ["新变化"]},
            self.outcome, self.validator,
        )
        self.assertTrue(ended)
        self.assertIn("最大安全轮数", scene["sceneDecision"]["reason"])

    def test_two_stagnant_repeated_rounds_trigger_loop_guard(self):
        scene = self._scene("loop")
        scene["previousActions"] = [{"text": "反复查看石碑", "actionTags": ["investigate"], "targetTags": ["石碑"]}]
        stagnant = {
            "narrative": "你又一次查看石碑，但现场没有出现任何新的事实，原来的疑问与周围人的位置都没有发生变化，只能停在相同判断上。",
            "factsAdded": [], "questionsAdded": [], "questionsResolved": [], "npcReactions": [],
            "actorsAdded": [], "objectsAdded": [],
            "sceneDecision": {"continueScene": True, "reason": "仍想继续查看。", "nextFocus": "loop的核心问题"},
            "continueScene": True, "suggestedClue": None,
        }
        choice = {"id": "repeat", "semanticAction": "再次反复查看石碑", "actionTags": ["investigate"], "targetTags": ["石碑"]}
        first = self.outcomes.update_scene_state(scene, copy.deepcopy(stagnant), choice, {**self.outcome, "code": "failure"}, self.validator)
        self.assertFalse(first)
        second = self.outcomes.update_scene_state(scene, copy.deepcopy(stagnant), choice, {**self.outcome, "code": "failure"}, self.validator)
        self.assertTrue(second)
        self.assertTrue(scene["loopGuard"]["forcedClosure"])
        self.assertIn("防循环", scene["sceneDecision"]["reason"])


if __name__ == "__main__":
    unittest.main()
