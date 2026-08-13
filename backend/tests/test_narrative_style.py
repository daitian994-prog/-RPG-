import unittest

from backend.services.ai_service import AIService


class NarrativeStyleTest(unittest.TestCase):
    def setUp(self):
        self.ai = AIService()

    def test_prompt_layers_global_chapter_location_event_and_format(self):
        prompt = self.ai._style_prompt(
            kind="event",
            event_type="探索",
            location_id="windbreak",
            chapter_phase="journey",
        )
        self.assertIn("第二人称有限视角", prompt)
        self.assertIn("第一章前期", prompt)
        self.assertIn("断风森林", prompt)
        self.assertIn("线索逐层出现", prompt)
        self.assertIn("总字数 300—450 字", prompt)

    def test_perspective_normalizer_uses_you_and_player_never_name(self):
        result = self.ai._normalize_perspective("玩家砚青听见风声，主角向林中走去。", "砚青")
        self.assertEqual(result, "你听见风声，你向林中走去。")
        self.assertNotIn("玩家", result)
        self.assertNotIn("砚青", result)

    def test_first_person_narration_is_rejected(self):
        self.assertIsNone(self.ai._normalize_perspective("我听见树林深处传来铃声。你停在原地。"))

    def test_npc_first_person_inside_dialogue_is_allowed(self):
        result = self.ai._normalize_perspective("“我听见了。”沉弓看向你。你没有立刻回答。")
        self.assertIsNotNone(result)


if __name__ == "__main__":
    unittest.main()
