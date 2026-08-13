import unittest
from unittest.mock import patch

from backend.services.game_service import GameService


class GameLoopTest(unittest.TestCase):
    def setUp(self):
        self.service = GameService()

    def test_complete_action_loop(self):
        game = self.service.new_game(["peace", "power", "freedom", "spirit", "destiny", "peace+spirit"])
        self.assertEqual(game["action_points"], 3)
        game, event = self.service.travel(game["id"], "war_ruins")
        self.assertEqual(game["action_points"], 2)
        game, resolution = self.service.resolve(game["id"], event["id"], 0)
        self.assertTrue(resolution["narrative"])
        self.assertIn("changes", resolution)
        self.assertIn(event["id"], game["completed_events"])
        self.assertEqual(len(game["player"]["memories"]), 1)

    def test_prepare_travel_resolves_facts_without_remote_narration(self):
        game = self.service.new_game(["peace", "power", "freedom", "spirit", "destiny", "peace"])
        with patch.object(self.service.ai, "_narrate") as narrate:
            game, event = self.service.travel(game["id"], "war_ruins", narrate=False)
        narrate.assert_not_called()
        self.assertEqual(game["location"], "war_ruins")
        self.assertEqual(len(event["choices"]), 3)
        self.assertTrue(all("assessment" in choice for choice in event["choices"]))
        self.assertEqual(event["narrative_source"], "local")

    def test_local_stream_falls_back_to_paragraph_ready_prose(self):
        game = self.service.new_game(["peace", "power", "freedom", "spirit", "destiny", "peace"])
        game, event = self.service.travel(game["id"], "war_ruins", narrate=False)
        with patch.object(type(self.service.ai.remote_ai), "configured", new_callable=unittest.mock.PropertyMock, return_value=False):
            chunks = list(self.service.stream_event(game["id"], event["id"]))
        self.assertTrue(chunks)
        self.assertIn("\n\n", "".join(chunks))

    def test_world_state_version_invalidates_after_player_change(self):
        game = self.service.new_game(["peace", "power", "freedom", "spirit", "destiny", "peace"])
        before = self.service.state_version(game)
        game["player"]["attributes"]["hp"] -= 1
        self.assertNotEqual(before, self.service.state_version(game))

    def test_visible_stats_fate_and_items(self):
        game = self.service.new_game(["peace", "power", "freedom", "spirit", "destiny", "spirit"])
        self.assertEqual(len(game["player"]["attributes"]), 9)
        self.assertEqual(len(game["player"]["fate_weights"]), 5)
        self.assertTrue(game["player"]["inventory"][0]["description"])
        self.assertIn("bonuses", game["player"]["inventory"][0])

    def test_rich_resolution_explains_every_effect(self):
        game = self.service.new_game(["peace", "power", "freedom", "spirit", "destiny", "peace"])
        with patch("backend.services.ai_service.random.randint", return_value=1):
            game, resolution = self.service.resolve(game["id"], "e01", 0)
        self.assertGreater(len(resolution["narrative"]), 100)
        self.assertTrue(resolution["changes"]["attributes"])
        self.assertTrue(resolution["changes"]["personality"])
        self.assertTrue(resolution["changes"]["fate"])
        self.assertEqual(resolution["items"][0]["name"], "苦叶膏")
        self.assertTrue(resolution["items"][0]["description"])
        self.assertTrue(resolution["items"][0]["bonuses"])

    def test_failure_has_real_penalties_and_missed_reward(self):
        game = self.service.new_game(["peace", "power", "freedom", "spirit", "destiny", "peace"])
        with patch("backend.services.ai_service.random.randint", return_value=100):
            game, resolution = self.service.resolve(game["id"], "e01", 0)
        self.assertEqual(resolution["outcome"]["code"], "failure")
        self.assertLess(resolution["changes"]["attributes"]["hp"], 0)
        self.assertLess(resolution["changes"]["relations"]["healer"], 0)
        self.assertIn("苦叶膏", resolution["missed_items"])
        self.assertTrue(any(value < 0 for value in resolution["changes"]["fate"].values()))

    def test_costly_success_keeps_reward_but_charges_cost(self):
        game = self.service.new_game(["peace", "power", "freedom", "spirit", "destiny", "peace"])
        event = next(event for event in self.service.events if event["id"] == "e01")
        assessment = self.service.ai.assess_choice(event, event["choices"][0], game, 0)
        with patch("backend.services.ai_service.random.randint", return_value=min(96, assessment["chance"] + 5)):
            game, resolution = self.service.resolve(game["id"], "e01", 0)
        self.assertEqual(resolution["outcome"]["code"], "costly")
        self.assertLess(resolution["costs"]["attributes"]["hp"], 0)
        self.assertEqual(resolution["items"][0]["name"], "苦叶膏")

    def test_all_event_choices_are_resolvable(self):
        self.assertEqual(len(self.service.events), 21)
        for event in self.service.events:
            self.assertEqual(len(event["choices"]), 3)
            self.assertTrue(all("result" in choice for choice in event["choices"]))

    def test_one_year_timeline_triggers_chapter_boss(self):
        game = self.service.new_game(["peace", "power", "freedom", "spirit", "destiny", "power"])
        event = None
        for _ in range(12):
            game, event = self.service.travel(game["id"], "pallas")
        self.assertEqual(game["time"]["total_actions"], 12)
        self.assertEqual(game["time"]["chapter_limit"], 12)
        self.assertEqual(game["season"], "第一年 · 冬末")
        self.assertEqual(event["id"], "chapter1_boss")
        self.assertEqual(event["boss"]["name"], "血旗督军·卡尔戈")
        self.assertIn("亚索", event["text"])

        with patch("backend.services.game_service.random.randint", return_value=1):
            game, resolution = self.service.resolve(game["id"], event["id"], 0)
        self.assertTrue(resolution["battle"]["is_boss"])
        self.assertTrue(resolution["battle"]["victory"])
        self.assertTrue(game["chapter_complete"])
        self.assertEqual(game["season"], "第二年 · 春 · 战后")
        self.assertIn("血旗断刃", [item["name"] for item in game["player"]["inventory"]])

    def test_legacy_two_year_save_migrates_to_one_year_finale(self):
        game = self.service.new_game(["peace", "power", "freedom", "spirit", "destiny", "power"])
        game["location"] = "greenwood"
        game["visited"] = ["greenwood", "war_ruins"]
        game["time"] = {"year": 2, "season_index": 1, "total_actions": 16, "chapter_limit": 24}
        game["season"] = "第二年 · 夏"
        self.assertTrue(self.service._normalize_state(game))
        self.assertEqual(game["time"], {"year": 1, "season_index": 3, "total_actions": 12, "chapter_limit": 12})
        self.assertEqual(game["chapter_phase"], "invasion")
        self.assertEqual(game["season"], "第一年 · 冬末")
        self.assertEqual(game["location"], "pallas")
        self.assertEqual(game["visited"], ["pallas", "war_ruins"])


if __name__ == "__main__":
    unittest.main()
