import unittest
from unittest.mock import patch

from backend.services.game_service import GameService
from backend.services.check_engine import CheckEngine, CheckRequest, Modifier


class GameLoopTest(unittest.TestCase):
    def setUp(self):
        self.service = GameService()

    def _dynamic_event(self, game, *, event_type=None, attribute=None, location="windbreak"):
        game["directorState"]["tension"] = 80
        pool = self.service.dynamic_events.generate_pool(game, location)
        for event in pool:
            if event_type and event["type"] != event_type:
                continue
            if attribute and not any(choice["attribute"] == attribute for choice in event["choices"]):
                continue
            return event
        self.fail("未生成符合测试条件的动态事件")

    def _install_pending(self, game, event):
        from backend.database.db import save_game
        event_id = f"{event['id']}@test"
        profile = event["directorProfile"]
        director = {"category": profile["category"], "intent": profile["intents"][0], "intensity": profile["intensity"], "threadId": profile.get("threadId"), "heroId": profile.get("heroId"), "eventId": event_id}
        template = {**event, "id": event_id, "template_id": event["id"], "event_seed": "dynamic-test", "director": director, "directorPrelude": "动态测试现场", "eventContext": None}
        game["pendingEvent"] = {"id": event_id, "templateId": event["id"], "eventSeed": "dynamic-test", "director": director, "directorPrelude": "动态测试现场", "eventContext": None, "template": template}
        save_game(game["id"], game)
        return event_id

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
        self.assertNotIn("bonuses", game["player"]["inventory"][0])
        self.assertIn("effects", game["player"]["inventory"][0])
        self.assertEqual(game["gameVersion"], "0.3.8")

    def test_world_thread_intervention_costs_time_and_persists(self):
        game = self.service.new_game(["peace", "power", "freedom", "spirit", "destiny", "peace"])
        thread = game["worldState"]["activeThreads"][0]
        thread["awareness"] = 65
        from backend.database.db import save_game
        save_game(game["id"], game)
        updated, result = self.service.intervene_world_thread(game["id"], thread["id"], "intervene")
        self.assertEqual(result["cost"], {"actionCost": 1, "timeCost": 1})
        self.assertEqual(updated["action_points"], 2)
        self.assertEqual(updated["worldState"]["worldTime"], 1)
        self.assertEqual(self.service.get(game["id"])["worldState"]["activeThreads"][0]["selectedOutcome"]["id"], "remnants_disrupted")

    def test_new_character_has_all_layered_schema_fields(self):
        game = self.service.new_game(["peace", "power", "freedom", "spirit", "destiny", "peace"])
        player = game["player"]
        for key in ["coreAbilities", "personality", "fateAffinities", "bodyCondition", "statuses", "traits", "relations", "clues", "inventory", "legacyCombatStats"]:
            self.assertIn(key, player)
        self.assertEqual(set(player["coreAbilities"]), {"martial", "physique", "perception", "willpower", "agility", "social"})

    def test_questionnaire_ability_tendency_is_small(self):
        game = self.service.new_game(["peace+spirit"] * 6)
        values = list(game["player"]["coreAbilities"].values())
        self.assertLessEqual(max(values) - min(values), 4)

    def test_personality_change_does_not_change_core_ability(self):
        game = self.service.new_game(["peace", "power", "freedom", "spirit", "destiny", "peace"])
        before = dict(game["player"]["coreAbilities"])
        game, event = self.service.travel(game["id"], "war_ruins", narrate=False)
        game, _ = self.service.resolve(game["id"], event["id"], 0)
        self.assertEqual(before, game["player"]["coreAbilities"])

    def test_legacy_save_is_migrated_without_losing_hp(self):
        game = self.service.new_game(["peace", "power", "freedom", "spirit", "destiny", "peace"])
        player = game["player"]
        player["attributes"]["hp"] = 63
        for key in ["coreAbilities", "fateAffinities", "bodyCondition", "traits", "relations", "legacyCombatStats"]:
            player.pop(key, None)
        player["core_attributes"] = {"martial": 9, "physique": 8, "attunement": 10, "resolve": 7, "finesse": 9, "influence": 8}
        self.assertTrue(self.service._normalize_state(game))
        self.assertEqual(game["player"]["legacyCombatStats"]["hp"], 63)
        self.assertEqual(game["player"]["coreAbilities"]["perception"], 10)

    def test_body_injury_modifier_affects_checks(self):
        game = self.service.new_game(["peace", "power", "freedom", "spirit", "destiny", "power"])
        event = self._dynamic_event(game, attribute="martial")
        index = next(i for i, choice in enumerate(event["choices"]) if choice["attribute"] == "martial")
        healthy = self.service.ai.assess_choice(event, event["choices"][index], game, index)["final_probability"]
        game["player"]["injurySeverity"] = 2
        self.service._sync_character_layers(game)
        injured = self.service.ai.assess_choice(event, event["choices"][index], game, index)["final_probability"]
        self.assertLess(injured, healthy)

    def test_reliable_rest_recovers_injury_and_status_for_time_cost(self):
        game = self.service.new_game(["peace", "power", "freedom", "spirit", "destiny", "peace"])
        game["player"]["injurySeverity"] = 2
        game["player"]["statuses"] = [{"id": "fatigue", "name": "疲惫", "source": "跋涉", "duration": 2, "modifiers": {"agility": -5}}]
        self.service._sync_character_layers(game)
        from backend.database.db import save_game
        save_game(game["id"], game)
        recovered, result = self.service.recover(game["id"])
        self.assertEqual(recovered["player"]["bodyCondition"]["state"], "light_injury")
        self.assertEqual(result["cost"]["timeCost"], 1)
        self.assertEqual(recovered["player"]["statuses"], [])

    def test_rest_is_only_available_at_safe_location(self):
        game = self.service.new_game(["peace", "power", "freedom", "spirit", "destiny", "peace"])
        game["location"] = "war_ruins"
        from backend.database.db import save_game
        save_game(game["id"], game)
        with self.assertRaises(ValueError):
            self.service.recover(game["id"])

    def test_status_has_source_duration_and_real_modifier(self):
        game = self.service.new_game(["peace", "power", "freedom", "spirit", "destiny", "freedom"])
        game["player"]["statuses"] = [{"id": "tense", "name": "紧张", "source": "伏击", "duration": 2, "modifiers": {"agility": -10}}]
        event = self._dynamic_event(game, attribute="agility")
        index = next(i for i, choice in enumerate(event["choices"]) if choice["attribute"] == "agility")
        assessment = self.service.ai.assess_choice(event, event["choices"][index], game, index)
        self.assertTrue(any(item["source"] == "status" and item["value"] == -10 for item in assessment["applied_modifiers"]))

    def test_ordinary_failure_never_sets_dead(self):
        game = self.service.new_game(["peace", "power", "freedom", "spirit", "destiny", "peace"])
        game, event = self.service.travel(game["id"], "war_ruins", narrate=False)
        game, _ = self.service.resolve(game["id"], event["id"], 0)
        self.assertFalse(game.get("dead", False))
        self.assertGreater(game["player"]["legacyCombatStats"]["hp"], 0)

    def test_only_explicitly_lethal_failure_can_set_dead(self):
        game = self.service.new_game(["peace", "power", "freedom", "spirit", "destiny", "power"])
        lethal = {"id": "test_lethal", "event_seed": "test-lethal", "type": "战斗", "locations": ["pallas"], "title": "致命测试", "text": "测试", "choices": [{"id": "duel", "text": "独自挑战强敌", "hint": "你清楚这可能致命", "attribute": "martial", "difficulty": 99, "lethal": True, "result": {"text": "后果", "personality": {"power": 1}}}]}
        self.service.chapter_events.append(lethal)
        for version in range(500):
            game["player_state_version"] = version
            if self.service.ai.evaluate_event_outcome(lethal, lethal["choices"][0], game, 0)["code"] == "failure":
                break
        from backend.database.db import save_game
        save_game(game["id"], game)
        game, resolution = self.service.resolve(game["id"], "test_lethal", 0)
        self.assertEqual(resolution["outcome"]["risk"], "致命")
        self.assertEqual(resolution["outcome"]["code"], "failure")
        self.assertTrue(game["dead"])

    def test_battle_failure_can_create_captured_state_instead_of_death(self):
        game = self.service.new_game(["peace", "power", "freedom", "spirit", "destiny", "power"])
        event = self._dynamic_event(game, event_type="战斗")
        event_id = self._install_pending(game, event)
        installed = self.service._event_template(game, event_id)
        for index in range(500):
            game["player_state_version"] = index
            if self.service.ai.evaluate_event_outcome(installed, installed["choices"][0], game, 0)["code"] == "failure":
                break
        from backend.database.db import save_game
        save_game(game["id"], game)
        game, resolution = self.service.resolve(game["id"], event_id, 0)
        self.assertEqual(resolution["outcome"]["code"], "failure")
        self.assertTrue(game["captured"]["active"])
        self.assertFalse(game.get("dead", False))

    def test_map_and_dynamic_events_remain_available(self):
        game = self.service.new_game(["peace", "power", "freedom", "spirit", "destiny", "peace"])
        game, event = self.service.travel(game["id"], "windbreak", narrate=False)
        self.assertEqual(game["location"], "windbreak")
        self.assertTrue(event["choices"])

    def test_saved_character_layers_survive_reload(self):
        game = self.service.new_game(["peace", "power", "freedom", "spirit", "destiny", "peace"])
        loaded = self.service.get(game["id"])
        self.assertEqual(loaded["player"]["coreAbilities"], game["player"]["coreAbilities"])
        self.assertEqual(loaded["player"]["bodyCondition"], game["player"]["bodyCondition"])

    def test_rich_resolution_explains_every_effect(self):
        game = self.service.new_game(["peace", "power", "freedom", "spirit", "destiny", "peace"])
        game, event = self.service.travel(game["id"], "war_ruins", narrate=False)
        with patch("backend.services.ai_service.random.randint", return_value=1):
            game, resolution = self.service.resolve(game["id"], event["id"], 0)
        self.assertGreater(len(resolution["narrative"]), 100)
        self.assertIsInstance(resolution["changes"]["attributes"], dict)
        self.assertTrue(resolution["changes"]["personality"])
        self.assertEqual(resolution["changes"]["fate"], {})
        self.assertEqual(game["player"]["fateAffinities"], game["player"]["fate_weights"])
        self.assertIn("worldFeedback", resolution)
        self.assertTrue(event["dynamic"])
        self.assertTrue(event["components"])

    def test_seeded_resolution_cannot_be_changed_by_refresh(self):
        game = self.service.new_game(["peace", "power", "freedom", "spirit", "destiny", "peace"])
        game, event = self.service.travel(game["id"], "war_ruins", narrate=False)
        game, first = self.service.resolve(game["id"], event["id"], 0)
        game, second = self.service.resolve(game["id"], event["id"], 0)
        self.assertEqual(first["outcome"]["roll"], second["outcome"]["roll"])
        self.assertEqual(first["outcome"]["tier"], second["outcome"]["tier"])
        self.assertEqual(len(game["player"]["memories"]), 1)

    def test_completed_event_cannot_be_replayed_with_another_choice(self):
        game = self.service.new_game(["peace", "power", "freedom", "spirit", "destiny", "peace"])
        game, event = self.service.travel(game["id"], "war_ruins", narrate=False)
        game, first = self.service.resolve(game["id"], event["id"], 0)
        game, replay = self.service.resolve(game["id"], event["id"], 2)
        self.assertEqual(first["choice_index"], replay["choice_index"])
        self.assertEqual(len(game["player"]["memories"]), 1)

    def test_probability_curve_and_modifiers(self):
        engine = CheckEngine()
        self.assertEqual([engine.curve(delta) for delta in range(-5, 6)], [5, 10, 18, 28, 39, 50, 61, 72, 82, 90, 95])
        request = CheckRequest("e", "seed", "c", "agility", 7, 8, "1", [Modifier("clue", "巡逻路线", 15), Modifier("context", "夜色", 10), Modifier("status", "疲惫", -10)])
        result = engine.preview(request)
        self.assertEqual(result["base_probability"], 39)
        self.assertEqual(result["final_probability"], 54)

    def test_same_seed_is_stable_and_state_version_changes_roll(self):
        engine = CheckEngine()
        first = CheckRequest("e", "seed", "c", "willpower", 8, 8, "1")
        second = CheckRequest("e", "seed", "c", "willpower", 8, 8, "2")
        self.assertEqual(engine.execute(first)["roll"], engine.execute(first)["roll"])
        self.assertNotEqual(engine.seed_for(first), engine.seed_for(second))

    def test_all_event_choices_are_resolvable(self):
        game = self.service.new_game(["peace"] * 6)
        events = []
        for index, location in enumerate(["pallas", "windbreak", "war_ruins", "mountain_temple"] * 6):
            game["time"]["total_actions"] = index
            game["worldState"]["worldTime"] = index
            events.extend(self.service.dynamic_events.generate_pool(game, location))
        self.assertGreater(len({event["id"] for event in events}), 200)
        self.assertTrue(all(len(event["choices"]) == 3 for event in events))
        self.assertTrue(all("result" in choice for event in events for choice in event["choices"]))

    def test_at_least_ten_events_use_distinct_core_attributes(self):
        game = self.service.new_game(["peace"] * 6)
        events = self.service.dynamic_events.generate_pool(game, "pallas")
        mapped = [event for event in events if len({choice.get("attribute") for choice in event["choices"] if choice.get("attribute")}) >= 2]
        self.assertGreaterEqual(len(mapped), 10)

    def test_battle_uses_the_same_check_engine(self):
        game = self.service.new_game(["peace", "power", "freedom", "spirit", "destiny", "power"])
        event = self._dynamic_event(game, event_type="战斗")
        event_id = self._install_pending(game, event)
        game, resolution = self.service.resolve(game["id"], event_id, 0)
        self.assertIn(resolution["outcome"]["tier"], {"critical", "success", "partial", "failure"})
        self.assertEqual(resolution["battle"]["chance"], resolution["outcome"]["final_probability"])

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
