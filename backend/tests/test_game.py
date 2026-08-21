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
            if attribute and not any(choice.get("attribute") == attribute for choice in event["choices"]):
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

    def _finish_event(self, game, event, first_index=0):
        initial_index = next((i for i, item in enumerate(event["choices"]) if "离开" in item["text"] or "撤离" in item["text"]), first_index) if event.get("round", 1) > 1 else first_index
        game, resolution = self.service.resolve(game["id"], event["id"], initial_index, event.get("round"))
        while not resolution.get("sceneEnded", True):
            event = resolution["nextEvent"]
            leave_index = next((i for i, item in enumerate(event["choices"]) if "离开" in item["text"] or "撤离" in item["text"]), 0)
            game, resolution = self.service.resolve(game["id"], event["id"], leave_index, event.get("round"))
        return game, resolution

    def test_chapter_yasuo_meeting_reflects_first_meeting_recognition_and_memory(self):
        first = self.service.new_game(["peace"] * 6)
        first_event = self.service._chapter_boss_event(first, narrate=False)
        self.assertIn("第一次真正与这名剑客", first_event["text"])

        known = self.service.new_game(["peace"] * 6)
        known["heroActors"]["yasuo"]["playerRelation"]["recognition"] = 10
        known_event = self.service._chapter_boss_event(known, narrate=False)
        self.assertIn("亚索认出了你", known_event["text"])

        remembered = self.service.new_game(["peace"] * 6)
        remembered["heroActors"]["yasuo"]["importantMemories"] = [{"summary": "你们曾在遗迹共同追查斥候"}]
        memory_event = self.service._chapter_boss_event(remembered, narrate=False)
        self.assertIn("你们曾在遗迹共同追查斥候", memory_event["text"])

    def test_complete_action_loop(self):
        game = self.service.new_game(["peace", "power", "freedom", "spirit", "destiny", "peace+spirit"])
        self.assertEqual(game["action_points"], 4)
        game, event = self.service.travel(game["id"], "war_ruins")
        self.assertEqual(game["action_points"], 3)
        game, first = self.service.resolve(game["id"], event["id"], 0, event.get("round"))
        self.assertTrue(first["aiResult"]["factsAdded"] or first["aiResult"]["questionsResolved"] or first["sceneEnded"])
        if first["sceneEnded"]:
            resolution = first
        else:
            game, resolution = self._finish_event(game, first["nextEvent"])
        self.assertTrue(resolution["narrative"])
        self.assertIn("changes", resolution)
        self.assertIn(event["id"], game["completed_events"])
        self.assertEqual(len(game["player"]["memories"]), 1)
        self.assertGreaterEqual(len("".join(first["narrative"].split())), 40)
        self.assertNotIn("已经确定的结果", resolution["narrative"])

    def test_prepare_travel_resolves_facts_without_remote_narration(self):
        game = self.service.new_game(["peace", "power", "freedom", "spirit", "destiny", "peace"])
        with patch.object(self.service.ai, "_narrate") as narrate:
            game, event = self.service.travel(game["id"], "war_ruins", narrate=False)
        narrate.assert_not_called()
        self.assertEqual(game["location"], "war_ruins")
        self.assertIn(len(event["choices"]), {2, 3, 4})
        self.assertTrue(all("assessment" in choice for choice in event["choices"]))
        self.assertEqual(event["narrative_source"], "fallback")
        self.assertGreaterEqual(len("".join(event["text"].split())), 220)
        self.assertGreaterEqual(len(event["text"].split("\n\n")), 4)
        for fact in event["sceneProposal"]["playerObservableFacts"]:
            self.assertLessEqual(event["text"].count(fact), 1)

    def test_identity_trait_never_becomes_an_event_action(self):
        game = self.service.new_game(["peace"] * 6)
        self.assertEqual(game["player"]["traits"][0]["classification"], "identity")
        for location in ("pallas", "windbreak", "war_ruins", "mountain_temple"):
            pool = self.service.dynamic_events.generate_pool(game, location)
            action_text = " ".join(choice["text"] for event in pool for choice in event["choices"])
            self.assertNotIn("凭借“无名者”", action_text)

    def test_local_stream_falls_back_to_paragraph_ready_prose(self):
        game = self.service.new_game(["peace", "power", "freedom", "spirit", "destiny", "peace"])
        game, event = self.service.travel(game["id"], "war_ruins", narrate=False)
        with patch.object(type(self.service.ai.remote_ai), "configured", new_callable=unittest.mock.PropertyMock, return_value=False):
            chunks = list(self.service.stream_event(game["id"], event["id"]))
        self.assertTrue(chunks)
        self.assertIn("\n\n", "".join(chunks))

    def test_structured_scene_is_not_sent_through_a_second_event_rewrite(self):
        game = self.service.new_game(["peace"] * 6)
        with patch.dict("os.environ", {"RUNETERRA_DISABLE_REMOTE_AI": "1"}, clear=False), patch.object(self.service.ai, "_contract_narrate") as contract:
            _game, event = self.service.travel(game["id"], "windbreak", narrate=True)
        contract.assert_not_called()
        self.assertEqual(event["narrative_source"], "fallback")

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
        self.assertEqual(game["gameVersion"], "0.4.1")

    def test_world_thread_intervention_costs_time_and_persists(self):
        game = self.service.new_game(["peace", "power", "freedom", "spirit", "destiny", "peace"])
        thread = game["worldState"]["activeThreads"][0]
        thread["awareness"] = 65
        from backend.database.db import save_game
        save_game(game["id"], game)
        updated, result = self.service.intervene_world_thread(game["id"], thread["id"], "intervene")
        self.assertEqual(result["cost"], {"actionCost": 1, "timeCost": 1})
        self.assertEqual(updated["action_points"], 3)
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
        event = next(
            event for location in ("pallas", "windbreak", "war_ruins", "mountain_temple")
            for event in self.service.dynamic_events.generate_pool(game, location)
            if any(choice.get("attribute") == "martial" for choice in event["choices"])
        )
        index = next(i for i, choice in enumerate(event["choices"]) if choice.get("attribute") == "martial")
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
        event = next(
            event for location in ("pallas", "windbreak", "war_ruins", "mountain_temple")
            for event in self.service.dynamic_events.generate_pool(game, location)
            if any(choice.get("attribute") == "agility" for choice in event["choices"])
        )
        index = next(i for i, choice in enumerate(event["choices"]) if choice.get("attribute") == "agility")
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
        self.assertGreater(len(resolution["narrative"]), 40)
        self.assertTrue(resolution["aiResult"]["factsAdded"] or resolution["aiResult"]["questionsAdded"] or resolution["sceneEnded"])
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
        game, first = self.service.resolve(game["id"], event["id"], 0, event.get("round"))
        game, second = self.service.resolve(game["id"], event["id"], 0, event.get("round"))
        self.assertEqual(first["outcome"]["roll"], second["outcome"]["roll"])
        self.assertEqual(first["outcome"]["tier"], second["outcome"]["tier"])
        self.assertEqual(len(game["player"]["memories"]), int(first["sceneEnded"]))

    def test_completed_event_cannot_be_replayed_with_another_choice(self):
        game = self.service.new_game(["peace", "power", "freedom", "spirit", "destiny", "peace"])
        game, event = self.service.travel(game["id"], "war_ruins", narrate=False)
        game, first = self._finish_event(game, event)
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
        self.assertTrue(all(2 <= len(event["choices"]) <= 4 for event in events))
        self.assertTrue(all("result" in choice for event in events for choice in event["choices"]))

    def test_fifty_dynamic_events_have_varied_action_first_choices(self):
        game = self.service.new_game(["peace"] * 6)
        events = []
        for index in range(50):
            location = ["pallas", "windbreak", "war_ruins", "mountain_temple"][index % 4]
            game["time"]["total_actions"] = index
            game["worldState"]["worldTime"] = index
            pool = self.service.dynamic_events.generate_pool(game, location)
            events.append(pool[index % len(pool)])
        choices = [choice for event in events for choice in event["choices"]]
        self.assertEqual({len(event["choices"]) for event in events}, {2, 3, 4})
        self.assertGreaterEqual(len({choice.get("attribute") for choice in choices if choice.get("attribute")}), 5)
        self.assertGreaterEqual(sum(choice.get("requiresCheck") is False for choice in choices) / len(choices), 0.1)
        self.assertTrue(all(choice.get("semanticAction") and choice.get("goal") and choice.get("approach") for choice in choices))
        self.assertTrue(all(len({choice["text"] for choice in event["choices"]}) == len(event["choices"]) for event in events))

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

    def test_copper_bell_scene_continues_with_a_concrete_fact(self):
        from backend.database.db import save_game
        game = self.service.new_game(["peace"] * 6)
        event = {
            "id": "copper-bell-scene", "dynamic": True, "type": "探索", "title": "无槌铜钟",
            "text": "山寺后院没有风，一口没有撞槌的铜钟却在轻微震动。",
            "event_seed": "copper-bell", "director": {"intensity": "medium", "threadId": "spirit_anomaly"},
            "eventContext": {"hardFacts": ["铜钟没有撞槌"], "forbiddenChanges": ["不得推进世界线程阶段"]},
            "sceneProposal": {
                "localActors": ["寺庙老人"], "localObjects": ["铜钟", "钟座"],
                "immediateProblem": "铜钟为什么会在无风时震动？",
                "playerObservableFacts": ["铜钟没有撞槌", "周围没有明显风", "铜钟正在轻微震动"],
            },
            "choices": [{
                "id": "inspect-bell", "text": "检查铜钟与钟座的缝隙", "semanticAction": "检查铜钟与钟座的缝隙",
                "goal": "查明震动来源", "approach": "逐处核对", "attribute": "perception", "difficulty": 8,
                "automatic": "success", "requiresCheck": True, "risk": "中", "actionTags": ["investigate"],
                "targetTags": ["铜钟", "钟座"], "result": {"text": "检查钟座。", "personality": {"spirit": 1}},
            }],
        }
        game["location"] = "mountain_temple"
        game["scene"] = self.service._scene_from_event(event, {
            "id": event["id"], "templateId": event["id"], "eventSeed": event["event_seed"],
            "director": event["director"], "eventContext": event["eventContext"],
        })
        save_game(game["id"], game)
        with patch.dict("os.environ", {"RUNETERRA_DISABLE_REMOTE_AI": "1"}, clear=False):
            game, resolution = self.service.resolve(game["id"], event["id"], 0, 1)
        self.assertFalse(resolution["sceneEnded"])
        self.assertIn("震动来自钟座下方", " ".join(resolution["aiResult"]["factsAdded"]))
        self.assertEqual(resolution["nextEvent"]["round"], 2)
        self.assertIn("震动来自钟座下方", " ".join(game["scene"]["facts"]))

    def test_leaving_can_end_a_scene_in_one_round(self):
        from backend.database.db import save_game
        game = self.service.new_game(["peace"] * 6)
        event = {
            "id": "lost-object-scene", "dynamic": True, "type": "日常", "title": "路边遗失物",
            "text": "路边放着一只普通布包，附近没有人。", "event_seed": "leave-now", "director": {},
            "eventContext": {"hardFacts": [], "forbiddenChanges": []},
            "sceneProposal": {"localActors": [], "localObjects": ["布包"], "immediateProblem": "布包是谁遗失的？", "playerObservableFacts": ["布包无人看管"]},
            "choices": [{
                "id": "leave", "text": "不碰布包，直接离开", "semanticAction": "不碰布包，直接离开",
                "goal": "避免卷入", "approach": "保持距离", "requiresCheck": False, "risk": "低",
                "actionTags": ["withdraw"], "targetTags": ["布包"], "result": {"text": "你离开了。", "personality": {"freedom": 1}},
            }],
        }
        game["scene"] = self.service._scene_from_event(event, {"id": event["id"], "templateId": event["id"], "eventSeed": event["event_seed"], "director": {}, "eventContext": event["eventContext"]})
        save_game(game["id"], game)
        with patch.dict("os.environ", {"RUNETERRA_DISABLE_REMOTE_AI": "1"}, clear=False):
            game, resolution = self.service.resolve(game["id"], event["id"], 0, 1)
        self.assertTrue(resolution["sceneEnded"])
        self.assertIn(event["id"], game["completed_events"])

    def test_only_two_relevant_nonduplicate_clues_apply(self):
        game = self.service.new_game(["peace"] * 6)
        game["location"] = "mountain_temple"
        game["player"]["clues"] = [
            {"name": "旧铜钟记录", "ability": "perception", "bonus": 5, "targetTags": ["铜钟"], "dedupeKey": "bell"},
            {"name": "钟座裂隙拓印", "ability": "perception", "bonus": 8, "targetTags": ["铜钟"], "dedupeKey": "bell"},
            {"name": "灵体震颤规律", "ability": "perception", "bonus": 4, "actionTags": ["investigate"], "dedupeKey": "method"},
            {"name": "诺克萨斯换岗线索", "ability": "perception", "bonus": 9, "targetTags": ["诺克萨斯"]},
            {"name": "山道路况线索", "ability": "perception", "bonus": 9, "targetTags": ["山道"]},
            {"name": "井水倒影线索", "ability": "perception", "bonus": 9, "targetTags": ["井水"]},
        ]
        event = {"id": "bell-check", "event_seed": "bell", "type": "探索", "director": {"threadId": "spirit_anomaly"}}
        choice = {"id": "inspect", "text": "检查山寺铜钟", "semanticAction": "检查山寺铜钟", "goal": "查明震动", "approach": "观察", "attribute": "perception", "difficulty": 8, "actionTags": ["investigate"], "targetTags": ["铜钟"], "result": {"personality": {"spirit": 1}}}
        assessment = self.service.ai.assess_choice(event, choice, game, 0)
        clue_modifiers = [item for item in assessment["applied_modifiers"] if item["source"] == "clue"]
        self.assertEqual([item["label"] for item in clue_modifiers], ["钟座裂隙拓印", "灵体震颤规律"])
        self.assertEqual(sum(item["value"] for item in clue_modifiers), 12)

    def test_one_year_timeline_triggers_chapter_boss(self):
        game = self.service.new_game(["peace", "power", "freedom", "spirit", "destiny", "power"])
        event = None
        for _ in range(12):
            game, event = self.service.travel(game["id"], "pallas")
            game, _ = self._finish_event(game, event)
        self.assertEqual(game["time"]["chapter_limit"], 16)
        self.assertEqual(game["time"]["actions_per_season"], 4)
        self.assertEqual(game["chapter_phase"], "finale_ready")

        expected = ["chapter1_spirit_finale", "chapter1_yasuo_finale", "chapter1_defense_finale"]
        for expected_id in expected:
            game, event = self.service.travel(game["id"], "pallas", narrate=False)
            self.assertEqual(event["id"], expected_id)
            game, _ = self.service.resolve(game["id"], event["id"], 0)

        game, event = self.service.travel(game["id"], "pallas", narrate=False)
        self.assertEqual(game["time"]["total_actions"], 16)
        self.assertEqual(game["season"], "第一年 · 冬末")
        self.assertEqual(event["id"], "chapter1_boss")
        self.assertEqual(event["boss"]["name"], "血旗督军·卡尔戈")
        self.assertIn("亚索", event["text"])

        for version in range(500):
            game["player_state_version"] = version
            if self.service.ai.evaluate_event_outcome(event, event["choices"][0], game, 0)["code"] in {"critical", "success", "partial"}:
                break
        from backend.database.db import save_game
        save_game(game["id"], game)
        game, resolution = self.service.resolve(game["id"], event["id"], 0)
        self.assertTrue(resolution["battle"]["is_boss"])
        self.assertTrue(resolution["battle"]["victory"])
        self.assertTrue(game["chapter_complete"])
        self.assertTrue(game["demo_complete"])
        self.assertEqual(game["season"], "第一年 · 冬末 · 尾声")
        self.assertEqual(len(game["chapter_summary"]["lines"]), 3)
        self.assertEqual(game["heroActors"]["yasuo"]["availability"], "departed")
        self.assertIn("血旗断刃", [item["name"] for item in game["player"]["inventory"]])

    def test_legacy_two_year_save_migrates_to_one_year_finale(self):
        game = self.service.new_game(["peace", "power", "freedom", "spirit", "destiny", "power"])
        game["location"] = "greenwood"
        game["visited"] = ["greenwood", "war_ruins"]
        game["time"] = {"year": 2, "season_index": 1, "total_actions": 16, "chapter_limit": 24}
        game["season"] = "第二年 · 夏"
        self.assertTrue(self.service._normalize_state(game))
        self.assertEqual(game["time"], {"year": 1, "season_index": 3, "total_actions": 16, "chapter_limit": 16, "actions_per_season": 4})
        self.assertEqual(game["chapter_phase"], "invasion")
        self.assertEqual(game["season"], "第一年 · 冬末")
        self.assertEqual(game["location"], "pallas")
        self.assertEqual(game["visited"], ["pallas", "war_ruins"])


if __name__ == "__main__":
    unittest.main()
