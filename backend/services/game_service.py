import json
import copy
import math
import random
import uuid
import hashlib
from pathlib import Path
from typing import Any

from backend.database.db import init_db, load_game, save_game
from backend.services.ai_service import AIService
from backend.services.dynamic_event_service import DynamicEventService
from backend.services.event_director_service import EventDirectorService
from backend.services.event_context_service import EventContextService
from backend.services.hero_actor_service import HeroActorService
from backend.services.narrative_authority_service import NarrativeAuthorityService
from backend.services.outcome_engine import OutcomeEngine
from backend.services.world_thread_service import WorldThreadService

DATA_DIR = Path(__file__).resolve().parents[2] / "game-data"
PROJECT_VERSION = (DATA_DIR.parent / "VERSION").read_text(encoding="utf-8").strip()

TRAIT_TO_FATE = {
    "peace": "guardian",
    "power": "strong",
    "freedom": "wanderer",
    "spirit": "spirit",
    "destiny": "breaker",
}
SEASONS = ["春", "夏", "秋", "冬"]
ACTIONS_PER_SEASON = 4
CHAPTER_ONE_ACTIONS = 16
CHAPTER_ONE_FINALE_START = 12
FINALE_EVENTS = {
    13: ("chapter1_spirit_finale", "mountain_temple", "finale_spirit"),
    14: ("chapter1_yasuo_finale", "war_ruins", "finale_yasuo"),
    15: ("chapter1_defense_finale", "pallas", "finale_defense"),
}
CORE_ABILITY_KEYS = ("martial", "physique", "perception", "willpower", "agility", "social")
LEGACY_CORE_KEY_MAP = {"attunement": "perception", "resolve": "willpower", "finesse": "agility", "influence": "social"}
BODY_CONDITIONS = {
    0: {"state": "healthy", "label": "良好", "description": "没有明显身体负担。", "modifiers": {}},
    1: {"state": "light_injury", "label": "轻伤", "description": "部分身体相关行动受到轻度影响。", "modifiers": {"martial": -10, "physique": -5}},
    2: {"state": "injured", "label": "受伤", "description": "行动能力受到一定影响。", "modifiers": {"martial": -15, "physique": -10, "agility": -10}},
    3: {"state": "severe_injury", "label": "重伤", "description": "继续高风险行动十分危险。", "modifiers": {"martial": -25, "physique": -20, "agility": -20, "willpower": -10}},
    4: {"state": "critical", "label": "濒危", "description": "生命处于严重危险，需要尽快治疗。", "modifiers": {"martial": -40, "physique": -35, "agility": -35, "willpower": -20}},
}


class GameService:
    def __init__(self) -> None:
        init_db()
        self.ai = AIService()
        self.dynamic_events = DynamicEventService()
        self.world_threads = WorldThreadService()
        self.director = EventDirectorService()
        self.event_context = EventContextService()
        self.hero_actors = HeroActorService()
        self.narrative_authority = NarrativeAuthorityService(self.ai.remote_ai)
        self.outcomes = OutcomeEngine()
        self.locations = self._read("locations.json")
        self.npcs = self._read("npc.json")
        self.chapter_events = self._read("chapter_events.json")
        check_profiles = self._read("check_profiles.json")
        for event in self.chapter_events:
            for index, profile in enumerate(check_profiles.get(event["id"], [])):
                event["choices"][index].update(profile)
        self.world = self._read("world.json")
        self.items = self._read("items.json")
        self.item_catalog = {item["name"]: item for item in self.items}

    @staticmethod
    def _read(name: str) -> Any:
        return json.loads((DATA_DIR / name).read_text(encoding="utf-8"))

    @staticmethod
    def _initial_attributes(personality: dict[str, int]) -> dict[str, int]:
        return {
            "hp": 100,
            "max_hp": 100,
            "attack": 10 + personality["power"] // 10,
            "defense": 8 + personality["peace"] // 12,
            "magic_power": 5 + personality["spirit"] // 10,
            "magic_resist": 7 + personality["spirit"] // 12,
            "attack_speed": 10 + personality["freedom"] // 12,
            "skill_haste": 5 + personality["destiny"] // 12,
            "combat_xp": 0,
        }

    @staticmethod
    def _initial_core_abilities(answers: list[str]) -> dict[str, int]:
        """Questionnaire gives small capability tendencies, independently of personality."""
        mappings = [
            {"peace+spirit": {"social": 1, "perception": 1}, "power+destiny": {"agility": 1, "willpower": 1}, "freedom": {"willpower": 1}},
            {"peace": {"willpower": 1, "social": 1}, "power+destiny": {"martial": 1}, "freedom": {"agility": 1}},
            {"spirit": {"perception": 1}, "destiny+power": {"willpower": 1, "physique": 1}, "freedom+peace": {"agility": 1}},
            {"peace+spirit": {"social": 1}, "power": {"physique": 1}, "freedom": {"agility": 1}},
            {"peace": {"willpower": 1}, "spirit+destiny": {"perception": 1}, "power+freedom": {"martial": 1}},
            {"destiny": {"willpower": 1}, "freedom": {"agility": 1}, "spirit+peace": {"perception": 1, "social": 1}},
        ]
        abilities = {key: 8 for key in CORE_ABILITY_KEYS}
        for index, answer in enumerate(answers[:6]):
            for key, delta in mappings[index].get(answer, {}).items():
                abilities[key] += delta
        return abilities

    @staticmethod
    def _initial_fate(answers: list[str]) -> dict[str, int]:
        fate = {key: 20 for key in TRAIT_TO_FATE.values()}
        for answer in answers:
            for trait in answer.split("+"):
                if trait in TRAIT_TO_FATE:
                    fate[TRAIT_TO_FATE[trait]] += 5
        return fate

    @staticmethod
    def _legacy_combat_stats(attributes: dict[str, int]) -> dict[str, int]:
        return {
            "hp": attributes["hp"], "maxHp": attributes["max_hp"], "attack": attributes["attack"],
            "defense": attributes["defense"], "abilityPower": attributes["magic_power"],
            "magicResist": attributes["magic_resist"], "attackSpeed": attributes["attack_speed"],
            "abilityHaste": attributes["skill_haste"], "battleExp": attributes["combat_xp"],
        }

    @staticmethod
    def _relation_stage(value: int) -> str:
        return "close" if value >= 40 else "trusted" if value >= 20 else "recognized" if value >= 5 else "hostile" if value <= -20 else "wary" if value < 0 else "stranger"

    def _sync_character_layers(self, state: dict[str, Any]) -> None:
        player = state["player"]
        severity = max(0, min(4, int(player.get("injurySeverity", 0))))
        player["injurySeverity"] = severity
        player["bodyCondition"] = {**BODY_CONDITIONS[severity]}
        player["core_attributes"] = player["coreAbilities"]
        player["fate_weights"] = player["fateAffinities"]
        player["legacyCombatStats"] = self._legacy_combat_stats(player["attributes"])
        player["relations"] = {
            npc_id: {"stage": self._relation_stage(data["score"]), "value": data["score"], "history": data["memories"]}
            for npc_id, data in state["relationships"].items()
        }
        state["relations"] = player["relations"]

    def _item(self, name: str) -> dict[str, Any]:
        item = self.item_catalog.get(name)
        if item:
            return {**item, "effects": list(item.get("effects", [])), "check_bonuses": dict(item.get("check_bonuses", {}))}
        return {"name": name, "rarity": "未知", "description": "这件物品的来历尚未被记录。", "effects": [], "check_bonuses": {}}

    def _apply_item_bonuses(self, player: dict[str, Any], item: dict[str, Any]) -> tuple[dict[str, int], dict[str, int]]:
        return {}, {}

    def _normalize_state(self, state: dict[str, Any]) -> bool:
        """Upgrade V1 saves in place without discarding the player's journey."""
        player = state["player"]
        changed = False
        old_inventory = player.get("inventory", [])
        normalized_inventory = [self._item(item if isinstance(item, str) else item.get("name", "未知物品")) for item in old_inventory]

        if state.get("location") == "greenwood":
            state["location"] = "pallas"
            changed = True
        if "greenwood" in state.get("visited", []):
            state["visited"] = ["pallas" if item == "greenwood" else item for item in state["visited"]]
            state["visited"] = list(dict.fromkeys(state["visited"]))
            changed = True

        if "attributes" not in player:
            player["attributes"] = self._initial_attributes(player["personality"])
            player["attributes"]["hp"] = player.pop("hp", player["attributes"]["hp"])
            player["attributes"]["combat_xp"] = player.pop("combat_xp", 0)
            changed = True
        if "fate_weights" not in player:
            player["fate_weights"] = {key: 20 for key in TRAIT_TO_FATE.values()}
            changed = True
        if "fateAffinities" not in player:
            player["fateAffinities"] = dict(player["fate_weights"])
            changed = True
        if "coreAbilities" not in player:
            legacy_core = player.get("core_attributes", {})
            player["coreAbilities"] = {key: 8 for key in CORE_ABILITY_KEYS}
            for old_key, value in legacy_core.items():
                player["coreAbilities"][LEGACY_CORE_KEY_MAP.get(old_key, old_key)] = max(5, min(12, int(value)))
            changed = True
        if "statuses" not in player:
            player["statuses"] = []
            changed = True
        if "clues" not in player:
            player["clues"] = []
            changed = True
        if "traits" not in player:
            player["traits"] = [{"id": "nameless", "name": "无名者", "level": 1, "source": "角色背景", "classification": "identity", "usableInEvents": False, "modifiers": {}}]
            changed = True
        for trait in player.get("traits", []):
            if trait.get("id") == "nameless":
                if trait.get("classification") != "identity" or trait.get("usableInEvents") is not False:
                    trait["classification"] = "identity"
                    trait["usableInEvents"] = False
                    changed = True
        if "injurySeverity" not in player:
            hp_ratio = player["attributes"]["hp"] / max(1, player["attributes"]["max_hp"])
            player["injurySeverity"] = 0 if hp_ratio >= .9 else 1 if hp_ratio >= .7 else 2 if hp_ratio >= .45 else 3 if hp_ratio >= .2 else 4
            changed = True
        if "player_state_version" not in state:
            state["player_state_version"] = 1
            changed = True
        if old_inventory != normalized_inventory:
            player["inventory"] = normalized_inventory
            changed = True
        elif not old_inventory:
            player["inventory"] = []
        if "time" not in state:
            used = max(0, ACTIONS_PER_SEASON - int(state.get("action_points", ACTIONS_PER_SEASON)))
            state["time"] = {"year": 1, "season_index": 0, "total_actions": used, "chapter_limit": CHAPTER_ONE_ACTIONS, "actions_per_season": ACTIONS_PER_SEASON}
            state["season"] = "第一年 · 春"
            state.setdefault("chapter_phase", "journey")
            state.setdefault("chapter_complete", False)
            changed = True
        elif state["time"].get("chapter_limit") != CHAPTER_ONE_ACTIONS:
            state["time"]["chapter_limit"] = CHAPTER_ONE_ACTIONS
            state["time"]["actions_per_season"] = ACTIONS_PER_SEASON
            state["time"]["total_actions"] = min(int(state["time"].get("total_actions", 0)), CHAPTER_ONE_ACTIONS)
            if state.get("chapter_complete"):
                state["time"]["year"] = 1
                state["time"]["season_index"] = 3
                state["season"] = "第一年 · 冬末 · 尾声"
            elif state["time"]["total_actions"] >= CHAPTER_ONE_ACTIONS:
                state["chapter_phase"] = "invasion"
                state["location"] = "pallas"
                state["time"]["year"] = 1
                state["time"]["season_index"] = 3
                state["season"] = "第一年 · 冬末"
            changed = True
        elif state["time"].get("actions_per_season") != ACTIONS_PER_SEASON:
            state["time"]["actions_per_season"] = ACTIONS_PER_SEASON
            changed = True
        for key, default in {
            "demo_complete": bool(state.get("chapter_complete", False)),
            "chapter_summary": None,
            "chapterFinale": {"completedStages": [], "choices": {}, "preparationStrength": 0},
        }.items():
            if key not in state:
                state[key] = copy.deepcopy(default)
                changed = True
        if state.get("gameVersion") != PROJECT_VERSION:
            state["gameVersion"] = PROJECT_VERSION
            changed = True
        pending = state.get("pendingEvent", {})
        if pending.get("templateId", "").startswith("e") and pending.get("templateId", "")[1:].isdigit():
            state.pop("pendingEvent", None)
            state.setdefault("log", []).append("旧版固定事件已经退出事件池；下一次旅行会根据当前世界状态生成新的现场。")
            changed = True
        if self.world_threads.normalize(state):
            changed = True
        if self.director.normalize(state):
            changed = True
        if self.hero_actors.normalize(state):
            changed = True
        for key, default in {
            "heroRelationships": {}, "stateChangeLog": [],
            "aiNarratorDebug": {"source": "none", "validation": {"valid": True, "errors": []}},
            "narrativeAuthorityDebug": {},
        }.items():
            if key not in state:
                state[key] = default
                changed = True
        self._sync_character_layers(state)
        return changed

    def new_game(self, answers: list[str]) -> dict[str, Any]:
        personality = {k: 20 for k in ["peace", "power", "freedom", "spirit", "destiny"]}
        for raw in answers:
            for trait in raw.split("+"):
                if trait in personality:
                    personality[trait] += 10
        birth = self.ai.generate_birth(personality)
        player = {
            **birth,
            "personality": personality,
            "attributes": self._initial_attributes(personality),
            "coreAbilities": self._initial_core_abilities(answers),
            "fateAffinities": self._initial_fate(answers),
            "fate_weights": {},
            "memories": [],
            "inventory": [],
            "statuses": [],
            "clues": [],
            "traits": [{"id": "nameless", "name": "无名者", "level": 1, "source": "角色背景", "classification": "identity", "usableInEvents": False, "modifiers": {}}],
            "injurySeverity": 0,
        }
        player["fate_weights"] = player["fateAffinities"]
        for item_name in ["青木枝", "干粮"]:
            item = self._item(item_name)
            player["inventory"].append(item)
            self._apply_item_bonuses(player, item)

        game_id = uuid.uuid4().hex
        state = {
            "id": game_id,
            "player": player,
            "location": "pallas",
            "season": "第一年 · 春",
            "time": {"year": 1, "season_index": 0, "total_actions": 0, "chapter_limit": CHAPTER_ONE_ACTIONS, "actions_per_season": ACTIONS_PER_SEASON},
            "action_points": ACTIONS_PER_SEASON,
            "relationships": {npc["id"]: {"score": 0, "memories": []} for npc in self.npcs},
            "visited": ["pallas"],
            "completed_events": [],
            "chapter": 1,
            "chapter_phase": "journey",
            "chapter_complete": False,
            "demo_complete": False,
            "chapter_summary": None,
            "chapterFinale": {"completedStages": [], "choices": {}, "preparationStrength": 0},
            "battle_complete": False,
            "last_resolution": None,
            "player_state_version": 1,
            "log": [birth["story"]],
            "lastRecovery": None,
            "gameVersion": PROJECT_VERSION,
            "worldState": self.world_threads.initial_state(),
            "directorState": self.director.initial_state(),
            "heroRelationships": {},
            "heroActors": self.hero_actors.initial_state(),
            "heroActionLog": [],
            "heroEncounter": {"heroId": "yasuo", "level": 0, "levelName": "none"},
            "stateChangeLog": [],
            "aiNarratorDebug": {"source": "none", "validation": {"valid": True, "errors": []}},
            "narrativeAuthorityDebug": {},
        }
        self._sync_character_layers(state)
        self.outcomes.record(state, "new_game", self.outcomes.snapshot(state), metadata={"version": PROJECT_VERSION})
        save_game(game_id, state)
        return state

    def get(self, game_id: str) -> dict[str, Any]:
        state = load_game(game_id)
        if not state:
            raise KeyError("旅程不存在或已经消散")
        if self._normalize_state(state):
            save_game(game_id, state)
        return state

    @staticmethod
    def state_version(state: dict[str, Any]) -> str:
        """Compact cache version; any gameplay-relevant change invalidates narrative reuse."""
        snapshot = {
            "location": state["location"], "time": state["time"],
            "attributes": state["player"]["attributes"],
            "coreAbilities": state["player"].get("coreAbilities", {}),
            "bodyCondition": state["player"].get("bodyCondition", {}),
            "statuses": state["player"].get("statuses", []),
            "clues": state["player"].get("clues", []),
            "personality": state["player"]["personality"],
            "fate": state["player"]["fateAffinities"],
            "completed": state["completed_events"], "relationships": state["relationships"],
            "worldState": state.get("worldState", {}),
            "directorState": state.get("directorState", {}),
            "heroActors": state.get("heroActors", {}),
        }
        return hashlib.sha256(json.dumps(snapshot, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()[:16]

    def travel(self, game_id: str, location_id: str, *, narrate: bool = True) -> tuple[dict[str, Any], dict[str, Any]]:
        state = self.get(game_id)
        before = self.outcomes.snapshot(state)
        if state.get("demo_complete"):
            raise ValueError("第一章试玩已经结束，可以查看结局总结或重新开始")
        pending = state.get("pendingEvent", {})
        if pending.get("template", {}).get("finale_stage"):
            return state, self._chapter_fixed_event(state, pending["templateId"], state["location"], pending["template"]["finale_stage"], narrate=narrate)
        if state.get("chapter_phase") == "invasion" and not state.get("chapter_complete"):
            return state, self._chapter_boss_event(state, narrate=narrate)
        if state["action_points"] <= 0:
            if state["time"]["total_actions"] >= CHAPTER_ONE_ACTIONS and not state.get("chapter_complete"):
                state["chapter_phase"] = "invasion"
                state["location"] = "pallas"
                save_game(game_id, state)
                return state, self._chapter_boss_event(state, narrate=narrate)
            state["action_points"] = ACTIONS_PER_SEASON
            period = state["time"]["total_actions"] // ACTIONS_PER_SEASON
            state["time"]["year"] = period // 4 + 1
            state["time"]["season_index"] = period % 4
            state["season"] = f"第{state['time']['year']}年 · {SEASONS[state['time']['season_index']]}"
            state["log"].append(f"季节向前推移。{state['season']}到来，你获得了新的四次行动。")
        location = next((x for x in self.locations if x["id"] == location_id), None)
        if not location:
            raise ValueError("未知地点")
        state["action_points"] -= 1
        state["time"]["total_actions"] += 1
        state["location"] = location_id
        state["last_resolution"] = None
        if location_id not in state["visited"]:
            state["visited"].append(location_id)
        state["latestWorldSignals"] = self.world_threads.advance(state, action="travel", location=location_id)
        self.hero_actors.tick(state)
        state["heroEncounter"] = self.hero_actors.encounter(state, location_id)
        finale = FINALE_EVENTS.get(state["time"]["total_actions"])
        if finale:
            event_id, forced_location, phase = finale
            state["chapter_phase"] = phase
            state["location"] = forced_location
            state["season"] = "第一年 · 冬 · 终章"
            save_game(game_id, state)
            return state, self._chapter_fixed_event(state, event_id, forced_location, phase, narrate=narrate)
        if state["time"]["total_actions"] >= CHAPTER_ONE_ACTIONS and not state.get("chapter_complete"):
            state["chapter_phase"] = "invasion"
            state["location"] = "pallas"
            state["season"] = "第一年 · 冬末"
            state["log"].append("第一年冬末，帕拉斯北面的山道响起了战争号角。一年的平静在这一刻结束。")
            save_game(game_id, state)
            return state, self._chapter_boss_event(state, narrate=narrate)

        if state["time"]["total_actions"] == CHAPTER_ONE_FINALE_START:
            state["chapter_phase"] = "finale_ready"
            state["log"].append("冬季渐深，三条纠缠了一年的线索开始同时收紧。接下来的行动将进入第一章终章。")

        generated_pool = self.dynamic_events.generate_pool(state, location_id)
        selection = self.director.select(state, location_id, generated_pool)
        template = self._event_template(state, selection["eventId"], selection=selection, catalog=generated_pool)
        selection["directorContext"] = self.director.context(state, selection, location["name"])
        template["director"] = selection
        template["directorPrelude"] = selection["directorContext"]
        hero_context = self.hero_actors.canon_prompt(self.ai.lore, state) if state["heroEncounter"].get("level", 0) >= 3 or selection.get("heroId") == "yasuo" else None
        template["eventContext"] = self.event_context.build(
            state, location, selection, template, hero_context=hero_context, hero_encounter=state["heroEncounter"],
        )
        template, authority_debug = self.narrative_authority.materialize(template["eventContext"], template)
        state["narrativeAuthorityDebug"] = authority_debug
        event = self.ai.generate_event(template, state, location, narrate=narrate)
        event["world_state_version"] = self.state_version(state)
        event["event_seed"] = selection["seed"]
        event["director"] = {key: value for key, value in selection.items() if key != "candidateWeights"}
        event["heroEncounter"] = state["heroEncounter"]
        event["narrativeAuthorityDebug"] = authority_debug
        self.hero_actors.record_encounter(state, state["heroEncounter"].get("level", 0))
        state["pendingEvent"] = {
            "id": selection["eventId"], "templateId": selection["templateId"],
            "eventSeed": selection["seed"], "director": event["director"],
            "directorPrelude": selection["directorContext"],
            "eventContext": template["eventContext"],
            "template": template,
        }
        self.director.record_selection(state, selection)
        self.outcomes.record(state, "travel_and_select_event", before, metadata={"locationId": location_id, "eventId": selection["eventId"], "candidateId": selection["candidateId"]})
        save_game(game_id, state)
        return state, event

    def _chapter_fixed_event(self, state: dict[str, Any], event_id: str, location_id: str, stage: str, *, narrate: bool = True) -> dict[str, Any]:
        template = copy.deepcopy(next(event for event in self.chapter_events if event["id"] == event_id))
        location = next(location for location in self.locations if location["id"] == location_id)
        selection = {
            **template.get("director", {}), "eventId": event_id, "templateId": event_id,
            "candidateId": f"{event_id}:authored", "seed": event_id,
            "threadStageLabel": stage, "directorContext": template.get("finale_context", "第一章终章的固定收束节点。"),
        }
        template["event_seed"] = event_id
        template["eventContext"] = self.event_context.build(state, location, selection, template)
        event = self.ai.generate_event(template, state, location, narrate=narrate)
        event["finale_stage"] = stage
        event["lockChoicesUntilComplete"] = True
        event["world_state_version"] = self.state_version(state)
        event["event_seed"] = event_id
        event["director"] = selection
        state["pendingEvent"] = {
            "id": event_id, "templateId": event_id, "eventSeed": event_id,
            "director": selection, "directorPrelude": selection["directorContext"],
            "eventContext": template["eventContext"], "template": template,
        }
        save_game(state["id"], state)
        return event

    def _event_template(
        self, state: dict[str, Any], event_id: str, *, selection: dict[str, Any] | None = None,
        catalog: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        pending = state.get("pendingEvent", {})
        if selection:
            template_id = selection["templateId"]
            seed = selection["seed"]
            director = selection
            prelude = selection.get("directorContext", "")
            event_context = selection.get("eventContext")
        elif pending.get("id") == event_id:
            template_id = pending["templateId"]
            seed = pending["eventSeed"]
            director = pending.get("director", {})
            prelude = pending.get("directorPrelude", "")
            event_context = pending.get("eventContext")
        else:
            template_id = event_id
            seed = event_id
            director = {}
            prelude = ""
            event_context = None
        if not selection and pending.get("id") == event_id and pending.get("template"):
            base = pending["template"]
        else:
            base = next((event for event in (catalog or self.chapter_events) if event["id"] == template_id), None)
        if not base:
            raise ValueError("事件已经消散")
        return {
            **base, "id": event_id, "template_id": template_id, "event_seed": seed,
            "director": director or base.get("director", {}), "directorPrelude": prelude,
            "eventContext": event_context or base.get("eventContext"),
        }

    def _chapter_boss_event(self, state: dict[str, Any], *, narrate: bool = True) -> dict[str, Any]:
        template = copy.deepcopy(next(event for event in self.chapter_events if event["id"] == "chapter1_boss"))
        preparation = int(state.get("chapterFinale", {}).get("preparationStrength", 0))
        if preparation:
            for choice in template["choices"]:
                choice["difficulty"] = max(7, int(choice.get("difficulty", 11)) - preparation)
                choice["hint"] = f"{choice['hint']} · 此前的守备准备正在发挥作用"
        location = next(location for location in self.locations if location["id"] == "pallas")
        runtime = state["heroActors"]["yasuo"]
        relation = runtime["playerRelation"]
        memories = runtime.get("importantMemories", [])
        if memories:
            meeting = f"亚索认出了你，也记得你们上次共同面对的事：{memories[-1]['summary']}。这次，他不再把你当作偶然闯入战局的陌生人。"
        elif relation.get("recognition", 0) >= 10:
            meeting = "亚索认出了你。他没有重提旧事，只用一个短促的点头承认你们已经见过。"
        else:
            meeting = "这是你第一次真正与这名剑客并肩站在同一场战斗里；他只报了自己的名字：亚索。"
        template["text"] = f"{template['text']}\n\n{meeting}"
        level = 5 if relation.get("trust", 0) >= 20 and relation.get("recognition", 0) >= 30 else 4
        state["heroEncounter"] = self.hero_actors.encounter(state, "pallas", force_level=level)
        selection = {
            **template["director"], "eventId": template["id"], "templateId": template["id"],
            "candidateId": "chapter1_boss:yasuo", "seed": template.get("event_seed", template["id"]),
            "threadStageLabel": "终局入侵", "directorContext": "第一章终局：亚索只能协助侧翼，玩家必须决定帕拉斯的命运。",
        }
        template["event_seed"] = selection["seed"]
        template["eventContext"] = self.event_context.build(
            state, location, selection, template,
            hero_context=self.hero_actors.canon_prompt(self.ai.lore, state),
            hero_encounter=state["heroEncounter"],
        )
        event = self.ai.generate_event(template, state, location, narrate=narrate)
        event["boss"] = template["boss"]
        event["chapter_finale"] = True
        event["lockChoicesUntilComplete"] = True
        event["world_state_version"] = self.state_version(state)
        event["event_seed"] = selection["seed"]
        event["director"] = selection
        event["heroEncounter"] = state["heroEncounter"]
        state["pendingEvent"] = {
            "id": template["id"], "templateId": template["id"], "eventSeed": selection["seed"],
            "director": selection, "directorPrelude": selection["directorContext"],
            "eventContext": template["eventContext"], "template": template,
        }
        self.hero_actors.record_encounter(state, level)
        save_game(state["id"], state)
        return event

    def _apply_finale_choice(self, state: dict[str, Any], event: dict[str, Any], choice: dict[str, Any]) -> None:
        effect = choice.get("chapter_effect")
        if not effect:
            return
        finale = state.setdefault("chapterFinale", {"completedStages": [], "choices": {}, "preparationStrength": 0})
        stage = event.get("finale_stage")
        if stage and stage not in finale["completedStages"]:
            finale["completedStages"].append(stage)
        finale["choices"][stage or event["id"]] = {
            "choice": choice["text"], "summary": effect.get("summary", ""),
        }
        if effect.get("line"):
            self.world_threads.finalize_for_chapter(state, effect["line"], favorable=bool(effect.get("favorable")))
        if effect.get("heroChoice"):
            runtime = state["heroActors"]["yasuo"]
            boosts = {
                "equals": {"recognition": 20, "trust": 12, "respect": 18, "alignment": 8},
                "guardian": {"recognition": 16, "trust": 14, "respect": 22, "alignment": 10},
                "honest": {"recognition": 18, "trust": 20, "respect": 12, "alignment": 12},
            }[effect["heroChoice"]]
            for key, value in boosts.items():
                runtime["playerRelation"][key] = min(100, runtime["playerRelation"].get(key, 0) + value)
            runtime["importantMemories"].append({"id": f"chapter1_yasuo_finale:{effect['heroChoice']}", "type": "chapter_bond", "importance": 4, "worldTime": state["time"]["total_actions"], "summary": effect["summary"]})
        if effect.get("preparation"):
            finale["preparation"] = effect["preparation"]
            finale["preparationStrength"] = int(effect.get("strength", 1))

    def _complete_demo(self, state: dict[str, Any], *, victory: bool) -> None:
        finale = state.setdefault("chapterFinale", {"completedStages": [], "choices": {}, "preparationStrength": 0})
        noxian = self.world_threads.finalize_for_chapter(state, "noxian_remnants", favorable=victory)
        spirit = next((item for item in state["worldState"]["activeThreads"] if item["id"] == "spirit_anomaly"), None)
        if spirit and not spirit.get("resolved"):
            spirit_outcome = self.world_threads.finalize_for_chapter(
                state, "spirit_anomaly", favorable=bool(spirit.get("selectedOutcome") or spirit.get("playerInterventions")),
            )
        else:
            spirit_outcome = copy.deepcopy((spirit or {}).get("resolvedOutcome", {}))
        runtime = state["heroActors"]["yasuo"]
        relation = runtime["playerRelation"]
        runtime["availability"] = "departed"
        runtime["status"] = "active"
        runtime["lastAction"] = {
            "type": "depart_after_chapter", "worldTime": state["time"]["total_actions"],
            "location": "pallas", "summary": "天亮后，亚索沿北面的山路离开帕拉斯，继续追查残军来路。",
        }
        yasuo_choice = finale.get("choices", {}).get("finale_yasuo", {}).get("summary")
        yasuo_summary = yasuo_choice or (
            "亚索记住了你守住帕拉斯的方式；天亮后，他沿北面的山路继续流浪。"
            if victory else "亚索把你从死亡线上带回，却没有替你抹去失败的代价；天亮后，他继续上路。"
        )
        preparation = finale.get("choices", {}).get("finale_defense", {}).get("summary", "帕拉斯在仓促中迎来了血旗。")
        state["chapter_summary"] = {
            "title": "第一章 · 血旗落下之后",
            "result": "你守住了帕拉斯，血旗在冬日黎明前坠落。" if victory else "帕拉斯没有陷落，但这一夜留下了焦土、伤者与尚未偿还的代价。",
            "playerLegacy": "帕拉斯守望者" if victory else "血旗之夜幸存者",
            "lines": [
                {"id": "spirit_anomaly", "title": "灵体异常", "closure": spirit_outcome.get("label", "灵界异象暂时平息"), "detail": finale.get("choices", {}).get("finale_spirit", {}).get("summary", "异常在冬末形成了暂时结果。"), "hook": "树影所畏惧的灵界震动仍来自艾欧尼亚深处。"},
                {"id": "yasuo", "title": "风与浪人", "closure": yasuo_summary, "detail": f"认可 {relation.get('recognition', 0)} · 信任 {relation.get('trust', 0)} · 尊重 {relation.get('respect', 0)}", "hook": "亚索带着残军进军图上的另一处标记继续北行。"},
                {"id": "noxian_remnants", "title": "诺克萨斯残军", "closure": noxian.get("label", "血旗军退出帕拉斯"), "detail": preparation, "hook": "卡尔戈只是旧军旗的一角，真正召集残军的人仍未现身。"},
            ],
            "nextChapterHook": "春天终会到来。山寺地底的树根、亚索带走的进军图，以及北方未曾熄灭的火光，都在等待下一章。",
        }
        state["chapter_complete"] = True
        state["demo_complete"] = True
        state["chapter_phase"] = "demo_complete"
        state["action_points"] = 0
        state["time"].update({"year": 1, "season_index": 3, "total_actions": CHAPTER_ONE_ACTIONS})
        state["season"] = "第一年 · 冬末 · 尾声"

    def narrate_event(self, game_id: str, event_id: str) -> str:
        state = self.get(game_id)
        template = self._event_template(state, event_id)
        location = next(location for location in self.locations if location["id"] == state["location"])
        return self.ai.narrate_event(template, state, location)

    def stream_event(self, game_id: str, event_id: str):
        state = self.get(game_id)
        template = self._event_template(state, event_id)
        location = next(location for location in self.locations if location["id"] == state["location"])
        def stream_and_persist():
            yield from self.ai.stream_event(template, state, location)
            save_game(game_id, state)
        return stream_and_persist()

    @staticmethod
    def _merge_changes(target: dict[str, int], source: dict[str, int]) -> None:
        for key, value in source.items():
            target[key] = target.get(key, 0) + value

    def resolve(self, game_id: str, event_id: str, choice_index: int) -> tuple[dict[str, Any], dict[str, Any]]:
        state = self.get(game_id)
        before = self.outcomes.snapshot(state)
        previous = state.get("last_resolution")
        if previous and previous.get("event_id") == event_id:
            return state, previous
        if event_id in state.get("completed_events", []):
            raise ValueError("这个事件已经结算，不能重新选择")
        event = self._event_template(state, event_id)
        choice = event["choices"][choice_index]
        result = choice["result"]
        player = state["player"]
        changes: dict[str, dict[str, int]] = {"personality": {}, "coreAbilities": {}, "attributes": {}, "fate": {}, "relations": {}}
        costs: dict[str, dict[str, int]] = {"personality": {}, "attributes": {}, "fate": {}, "relations": {}}
        check_event = {**event, "event_seed": event.get("event_seed", event["id"])}
        state["check_state_version"] = str(state.get("player_state_version", 1))
        outcome = self.ai.evaluate_event_outcome(check_event, choice, state, choice_index)
        reward_multiplier = outcome["reward_multiplier"]

        for trait, base_delta in result.get("personality", {}).items():
            delta = max(1, round(base_delta * reward_multiplier))
            player["personality"][trait] += delta
            changes["personality"][trait] = delta

        if outcome:
            tradeoff_trait = outcome["tradeoff_trait"]
            tradeoff_loss = min(outcome["tradeoff_loss"], max(0, player["personality"][tradeoff_trait] - 5))
            if tradeoff_loss:
                player["personality"][tradeoff_trait] -= tradeoff_loss
                changes["personality"][tradeoff_trait] = changes["personality"].get(tradeoff_trait, 0) - tradeoff_loss
                costs["personality"][tradeoff_trait] = -tradeoff_loss

        for npc_id, delta in result.get("relations", {}).items():
            rel = state["relationships"][npc_id]
            adjusted_delta = round(delta * outcome["relationship_factor"]) if outcome else delta
            if adjusted_delta == 0 and outcome["code"] == "partial":
                adjusted_delta = 1
            rel["score"] += adjusted_delta
            changes["relations"][npc_id] = adjusted_delta
            if adjusted_delta < 0:
                costs["relations"][npc_id] = adjusted_delta
            if result.get("memory") and adjusted_delta > 0:
                rel["memories"].append(result["memory"])

        acquired_items: list[dict[str, Any]] = []
        owned_names = {item["name"] for item in player["inventory"]}
        missed_items: list[str] = []
        for item_name in result.get("items", []):
            if outcome and not outcome["grants_items"]:
                missed_items.append(item_name)
                continue
            if item_name not in owned_names:
                item = self._item(item_name)
                player["inventory"].append(item)
                owned_names.add(item_name)
                acquired_items.append(item)
                attribute_bonus, fate_bonus = self._apply_item_bonuses(player, item)
                self._merge_changes(changes["attributes"], attribute_bonus)
                self._merge_changes(changes["fate"], fate_bonus)

        if outcome and outcome["hp_loss"]:
            actual_loss = min(outcome["hp_loss"], max(0, player["attributes"]["hp"] - 1))
            player["attributes"]["hp"] -= actual_loss
            changes["attributes"]["hp"] = changes["attributes"].get("hp", 0) - actual_loss
            costs["attributes"]["hp"] = -actual_loss

        granted_statuses: list[dict[str, Any]] = []
        for status in result.get("statuses", []):
            if status.get("on", "any") in {"any", outcome["code"]}:
                player["statuses"] = [item for item in player["statuses"] if item["name"] != status["name"]]
                player["statuses"].append(status)
                granted_statuses.append(status)
        injury_delta = 0
        if outcome["code"] == "partial" and event["type"] in {"探索", "成长", "命运", "战斗"}:
            injury_delta = 1
        elif outcome["code"] == "failure":
            injury_delta = 2 if event["type"] == "战斗" or outcome["risk"] == "致命" else 1
        if injury_delta:
            player["injurySeverity"] = min(4, player["injurySeverity"] + injury_delta)
        lethal_failure = bool(choice.get("lethal")) and outcome["risk"] == "致命" and outcome["code"] == "failure"
        if lethal_failure:
            state["dead"] = True
            player["injurySeverity"] = 4

        granted_clues: list[dict[str, Any]] = []
        for clue in result.get("clues", []):
            if outcome["code"] != "failure" and clue["name"] not in {item["name"] for item in player["clues"]}:
                player["clues"].append(clue)
                granted_clues.append(clue)

        battle: dict[str, Any] | None = None
        battle_text = ""
        if event["type"] == "战斗":
            stats = player["attributes"]
            is_boss = event.get("chapter_only", False)
            chance = outcome["final_probability"]
            victory = outcome["code"] in {"critical", "success", "partial"}
            battle_text = self.ai.generate_battle_text(player, victory, choice_index)
            state["battle_complete"] = True
            battle = {"victory": victory, "chance": chance, "nodes": 1 if is_boss else 2, "is_boss": is_boss, "boss": event.get("boss")}
            if victory:
                xp_gain = 40 if is_boss else 15
                stats["combat_xp"] += xp_gain
                changes["attributes"]["combat_xp"] = xp_gain
                if "初战幸存者" not in player["tags"]:
                    player["tags"].append("初战幸存者")
                if is_boss:
                    player["tags"].append("帕拉斯守望者")
                    battle_text += " 卡尔戈的重刃最终折断在村口。血旗从燃烧的屋脊坠下时，亚索只在远处收剑点头：‘这是你的村庄，也是你的胜利。’天亮后，人们第一次把你的名字与守住帕拉斯的那一夜放在一起。"
                    reward = self._item("血旗断刃")
                    if reward["name"] not in owned_names:
                        player["inventory"].append(reward)
                        acquired_items.append(reward)
                        attribute_bonus, fate_bonus = self._apply_item_bonuses(player, reward)
                        self._merge_changes(changes["attributes"], attribute_bonus)
                        self._merge_changes(changes["fate"], fate_bonus)
            else:
                if not lethal_failure:
                    state["captured"] = {"active": True, "sourceEvent": event_id, "escapeOptions": ["agility", "social", "perception"], "worldHooks": []}
                if is_boss:
                    player["tags"].append("血旗之夜幸存者")
                    battle_text += " 卡尔戈的重刃击碎了你最后的防守。就在刀锋再次落下前，疾风越过战场，亚索将你拖离死亡线。村庄最终没有陷落，却有许多屋舍化作灰烬。‘活下来，’他在离开前说，‘下一次，别把命交给路过的人。’"
            if is_boss:
                self._complete_demo(state, victory=victory)

        self._apply_finale_choice(state, event, choice)
        if event.get("finale_stage") and not state.get("demo_complete"):
            state["chapter_phase"] = "finale_ready"

        director = {**event.get("director", {}), "eventId": event_id}
        world_feedback = self.outcomes.apply_world_feedback(state, director, outcome, choice)
        location = next(x for x in self.locations if x["id"] == state["location"])
        narrative = self.ai.generate_resolution(event, choice, state, location, battle_text, outcome, world_feedback)
        resolution = {
            "event_id": event_id,
            "event_title": event["title"].format(location=location["name"]),
            "event_type": event["type"],
            "choice": choice["text"],
            "choice_index": choice_index,
            "narrative": narrative,
            "changes": changes,
            "costs": costs,
            "items": acquired_items,
            "missed_items": missed_items,
            "battle": battle,
            "outcome": outcome,
            "statuses": granted_statuses,
            "clues": granted_clues,
            "chapter_complete": state.get("chapter_complete", False),
            "worldFeedback": world_feedback,
        }
        if event_id not in state["completed_events"]:
            state["completed_events"].append(event_id)
        player["memories"].append(narrative)
        state["log"].append(narrative)
        state["last_resolution"] = resolution
        if state.get("pendingEvent", {}).get("id") == event_id:
            state.pop("pendingEvent", None)
        state["player_state_version"] = int(state.get("player_state_version", 1)) + 1
        state.pop("check_state_version", None)
        self._sync_character_layers(state)
        change_entry = self.outcomes.record(state, "resolve_event", before, metadata={"eventId": event_id, "choiceIndex": choice_index, "tier": outcome["code"]})
        resolution["stateChangeLog"] = change_entry
        save_game(game_id, state)
        return state, resolution

    def recover(self, game_id: str, method: str = "rest") -> tuple[dict[str, Any], dict[str, Any]]:
        state = self.get(game_id)
        snapshot = self.outcomes.snapshot(state)
        if state["location"] != "pallas":
            raise ValueError("只有安全地点才能进行稳定休息")
        if state.get("demo_complete"):
            raise ValueError("第一章试玩已经结束")
        if state["time"]["total_actions"] >= CHAPTER_ONE_FINALE_START or state.get("chapter_phase", "").startswith("finale") or state.get("chapter_phase") == "invasion":
            raise ValueError("终章已经开始，现在必须处理眼前的局势")
        if state["action_points"] <= 0:
            raise ValueError("本季行动次数已经用完，请通过下一次旅行进入新季节")
        player = state["player"]
        before = player["injurySeverity"]
        cleared = [item["name"] for item in player["statuses"] if item.get("id") in {"fatigue", "tense"} or item["name"] in {"疲惫", "紧张"}]
        player["statuses"] = [item for item in player["statuses"] if item.get("id") not in {"fatigue", "tense"} and item["name"] not in {"疲惫", "紧张"}]
        player["injurySeverity"] = max(0, before - 1)
        hp_gain = min(player["attributes"]["max_hp"] - player["attributes"]["hp"], 15)
        player["attributes"]["hp"] += hp_gain
        state["action_points"] = max(0, state["action_points"] - 1)
        state["time"]["total_actions"] += 1
        state["latestWorldSignals"] = self.world_threads.advance(state, action="recover", location=state["location"])
        self.hero_actors.tick(state)
        cost = {"actionCost": 1, "resourceCost": [], "moneyCost": 0, "futureWorldTimeCost": 1, "timeCost": 1}
        recovery = {"method": method, "injuryBefore": BODY_CONDITIONS[before]["state"], "injuryAfter": BODY_CONDITIONS[player["injurySeverity"]]["state"], "clearedStatuses": cleared, "legacyHpRecovered": hp_gain, "cost": cost}
        state["lastRecovery"] = recovery
        state["last_resolution"] = None
        state["player_state_version"] = int(state.get("player_state_version", 1)) + 1
        state["log"].append("你在帕拉斯安全休息。疲惫逐渐退去，伤势得到稳定处理；这段恢复消耗了一次行动。")
        self._sync_character_layers(state)
        self.outcomes.record(state, "recover", snapshot, metadata={"method": method})
        save_game(game_id, state)
        return state, recovery

    def intervene_world_thread(self, game_id: str, thread_id: str, strategy: str) -> tuple[dict[str, Any], dict[str, Any]]:
        state = self.get(game_id)
        snapshot = self.outcomes.snapshot(state)
        if state.get("demo_complete"):
            raise ValueError("第一章试玩已经结束")
        if state["time"]["total_actions"] >= CHAPTER_ONE_FINALE_START or state.get("chapter_phase", "").startswith("finale") or state.get("chapter_phase") == "invasion":
            raise ValueError("终章已经开始，世界线将通过最后四幕依次收束")
        if state["action_points"] <= 0:
            raise ValueError("本季行动次数已经用完")
        result = self.world_threads.intervene(state, thread_id, strategy)
        state["action_points"] -= 1
        state["time"]["total_actions"] += 1
        state["latestWorldSignals"] = self.world_threads.advance(state, action="world_intervention", location=state["location"])
        self.hero_actors.tick(state)
        result["cost"] = {"actionCost": 1, "timeCost": 1}
        state["last_resolution"] = None
        state["player_state_version"] = int(state.get("player_state_version", 1)) + 1
        state["log"].append(result["message"])
        self.outcomes.record(state, "world_thread_intervention", snapshot, metadata={"threadId": thread_id, "strategy": strategy})
        save_game(game_id, state)
        return state, result

    def focus_world_topic(self, game_id: str, topic_id: str, focused: bool) -> tuple[dict[str, Any], dict[str, Any]]:
        state = self.get(game_id)
        snapshot = self.outcomes.snapshot(state)
        result = self.director.set_focus(state, topic_id, focused)
        state["player_state_version"] = int(state.get("player_state_version", 1)) + 1
        state["log"].append(result["message"])
        self.outcomes.record(state, "set_world_focus", snapshot, metadata={"topicId": topic_id, "focused": focused})
        save_game(game_id, state)
        return state, result

    def dialogue(self, game_id: str, npc_id: str) -> tuple[dict[str, Any], str]:
        state = self.get(game_id)
        snapshot = self.outcomes.snapshot(state)
        npc = next((n for n in self.npcs if n["id"] == npc_id), None)
        if not npc:
            raise ValueError("找不到这个人")
        text = self.ai.generate_dialogue(npc, state["relationships"][npc_id])
        state["log"].append(text)
        self.outcomes.record(state, "dialogue", snapshot, metadata={"npcId": npc_id})
        save_game(game_id, state)
        return state, text
