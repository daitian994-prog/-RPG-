import json
import math
import random
import uuid
import hashlib
from pathlib import Path
from typing import Any

from backend.database.db import init_db, load_game, save_game
from backend.services.ai_service import AIService

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
CHAPTER_ONE_ACTIONS = 12
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
        self.locations = self._read("locations.json")
        self.npcs = self._read("npc.json")
        self.events = self._read("events.json")
        check_profiles = self._read("check_profiles.json")
        for event in self.events:
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
            player["traits"] = [{"id": "nameless", "name": "无名者", "level": 1, "source": "角色背景", "modifiers": {}}]
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
            used = max(0, 3 - int(state.get("action_points", 3)))
            state["time"] = {"year": 1, "season_index": 0, "total_actions": used, "chapter_limit": CHAPTER_ONE_ACTIONS}
            state["season"] = "第一年 · 春"
            state.setdefault("chapter_phase", "journey")
            state.setdefault("chapter_complete", False)
            changed = True
        elif state["time"].get("chapter_limit") != CHAPTER_ONE_ACTIONS:
            state["time"]["chapter_limit"] = CHAPTER_ONE_ACTIONS
            state["time"]["total_actions"] = min(int(state["time"].get("total_actions", 0)), CHAPTER_ONE_ACTIONS)
            if state.get("chapter_complete"):
                state["time"]["year"] = 2
                state["time"]["season_index"] = 0
                state["season"] = "第二年 · 春 · 战后"
            elif state["time"]["total_actions"] >= CHAPTER_ONE_ACTIONS:
                state["chapter_phase"] = "invasion"
                state["location"] = "pallas"
                state["time"]["year"] = 1
                state["time"]["season_index"] = 3
                state["season"] = "第一年 · 冬末"
            changed = True
        if state.get("gameVersion") != PROJECT_VERSION:
            state["gameVersion"] = PROJECT_VERSION
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
            "traits": [{"id": "nameless", "name": "无名者", "level": 1, "source": "角色背景", "modifiers": {}}],
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
            "time": {"year": 1, "season_index": 0, "total_actions": 0, "chapter_limit": CHAPTER_ONE_ACTIONS},
            "action_points": 3,
            "relationships": {npc["id"]: {"score": 0, "memories": []} for npc in self.npcs},
            "visited": ["pallas"],
            "completed_events": [],
            "chapter": 1,
            "chapter_phase": "journey",
            "chapter_complete": False,
            "battle_complete": False,
            "last_resolution": None,
            "player_state_version": 1,
            "log": [birth["story"]],
            "lastRecovery": None,
            "gameVersion": PROJECT_VERSION,
        }
        self._sync_character_layers(state)
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
        }
        return hashlib.sha256(json.dumps(snapshot, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()[:16]

    def travel(self, game_id: str, location_id: str, *, narrate: bool = True) -> tuple[dict[str, Any], dict[str, Any]]:
        state = self.get(game_id)
        if state.get("chapter_phase") == "invasion" and not state.get("chapter_complete"):
            return state, self._chapter_boss_event(state, narrate=narrate)
        if state["action_points"] <= 0:
            if state["time"]["total_actions"] >= CHAPTER_ONE_ACTIONS and not state.get("chapter_complete"):
                state["chapter_phase"] = "invasion"
                state["location"] = "pallas"
                save_game(game_id, state)
                return state, self._chapter_boss_event(state, narrate=narrate)
            state["action_points"] = 3
            period = state["time"]["total_actions"] // 3
            state["time"]["year"] = period // 4 + 1
            state["time"]["season_index"] = period % 4
            state["season"] = f"第{state['time']['year']}年 · {SEASONS[state['time']['season_index']]}"
            state["log"].append(f"季节向前推移。{state['season']}到来，你获得了新的三次行动。")
        location = next((x for x in self.locations if x["id"] == location_id), None)
        if not location:
            raise ValueError("未知地点")
        state["action_points"] -= 1
        state["time"]["total_actions"] += 1
        state["location"] = location_id
        state["last_resolution"] = None
        if location_id not in state["visited"]:
            state["visited"].append(location_id)
        if state["time"]["total_actions"] >= CHAPTER_ONE_ACTIONS and not state.get("chapter_complete"):
            state["chapter_phase"] = "invasion"
            state["location"] = "pallas"
            state["season"] = "第一年 · 冬末"
            state["log"].append("第一年冬末，帕拉斯北面的山道响起了战争号角。一年的平静在这一刻结束。")
            save_game(game_id, state)
            return state, self._chapter_boss_event(state, narrate=narrate)

        candidates = [e for e in self.events if not e.get("chapter_only") and location_id in e["locations"] and e["id"] not in state["completed_events"]]
        if not candidates:
            candidates = [e for e in self.events if not e.get("chapter_only") and location_id in e["locations"]]
        template = random.choice(candidates)
        event = self.ai.generate_event(template, state, location, narrate=narrate)
        event["world_state_version"] = self.state_version(state)
        event["event_seed"] = template.get("event_seed", template["id"])
        save_game(game_id, state)
        return state, event

    def _chapter_boss_event(self, state: dict[str, Any], *, narrate: bool = True) -> dict[str, Any]:
        template = next(event for event in self.events if event["id"] == "chapter1_boss")
        location = next(location for location in self.locations if location["id"] == "pallas")
        event = self.ai.generate_event(template, state, location, narrate=narrate)
        event["boss"] = template["boss"]
        event["chapter_finale"] = True
        event["world_state_version"] = self.state_version(state)
        event["event_seed"] = template.get("event_seed", template["id"])
        return event

    def narrate_event(self, game_id: str, event_id: str) -> str:
        state = self.get(game_id)
        template = next((event for event in self.events if event["id"] == event_id), None)
        if not template:
            raise ValueError("事件已经消散")
        location = next(location for location in self.locations if location["id"] == state["location"])
        return self.ai.narrate_event(template, state, location)

    def stream_event(self, game_id: str, event_id: str):
        state = self.get(game_id)
        template = next((event for event in self.events if event["id"] == event_id), None)
        if not template:
            raise ValueError("事件已经消散")
        location = next(location for location in self.locations if location["id"] == state["location"])
        return self.ai.stream_event(template, state, location)

    @staticmethod
    def _merge_changes(target: dict[str, int], source: dict[str, int]) -> None:
        for key, value in source.items():
            target[key] = target.get(key, 0) + value

    def resolve(self, game_id: str, event_id: str, choice_index: int) -> tuple[dict[str, Any], dict[str, Any]]:
        state = self.get(game_id)
        previous = state.get("last_resolution")
        if previous and previous.get("event_id") == event_id:
            return state, previous
        if event_id in state.get("completed_events", []):
            raise ValueError("这个事件已经结算，不能重新选择")
        event = next((e for e in self.events if e["id"] == event_id), None)
        if not event:
            raise ValueError("事件已经消散")
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
            battle = {"victory": victory, "chance": chance, "nodes": 4 if is_boss else 2, "is_boss": is_boss, "boss": event.get("boss")}
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
                state["chapter_complete"] = True
                state["chapter_phase"] = "aftermath"
                state["action_points"] = 3
                state["time"]["year"] = 2
                state["time"]["season_index"] = 0
                state["season"] = "第二年 · 春 · 战后"

        location = next(x for x in self.locations if x["id"] == state["location"])
        narrative = self.ai.generate_resolution(event, choice, state, location, battle_text, outcome)
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
        }
        if event_id not in state["completed_events"]:
            state["completed_events"].append(event_id)
        player["memories"].append(narrative)
        state["log"].append(narrative)
        state["last_resolution"] = resolution
        state["player_state_version"] = int(state.get("player_state_version", 1)) + 1
        state.pop("check_state_version", None)
        self._sync_character_layers(state)
        save_game(game_id, state)
        return state, resolution

    def recover(self, game_id: str, method: str = "rest") -> tuple[dict[str, Any], dict[str, Any]]:
        state = self.get(game_id)
        if state["location"] != "pallas":
            raise ValueError("只有安全地点才能进行稳定休息")
        if state.get("chapter_phase") == "invasion" and not state.get("chapter_complete"):
            raise ValueError("入侵期间无法安全休息")
        player = state["player"]
        before = player["injurySeverity"]
        cleared = [item["name"] for item in player["statuses"] if item.get("id") in {"fatigue", "tense"} or item["name"] in {"疲惫", "紧张"}]
        player["statuses"] = [item for item in player["statuses"] if item.get("id") not in {"fatigue", "tense"} and item["name"] not in {"疲惫", "紧张"}]
        player["injurySeverity"] = max(0, before - 1)
        hp_gain = min(player["attributes"]["max_hp"] - player["attributes"]["hp"], 15)
        player["attributes"]["hp"] += hp_gain
        state["action_points"] = max(0, state["action_points"] - 1)
        state["time"]["total_actions"] += 1
        cost = {"actionCost": 1, "resourceCost": [], "moneyCost": 0, "futureWorldTimeCost": 1, "timeCost": 1}
        recovery = {"method": method, "injuryBefore": BODY_CONDITIONS[before]["state"], "injuryAfter": BODY_CONDITIONS[player["injurySeverity"]]["state"], "clearedStatuses": cleared, "legacyHpRecovered": hp_gain, "cost": cost}
        state["lastRecovery"] = recovery
        state["last_resolution"] = None
        state["player_state_version"] = int(state.get("player_state_version", 1)) + 1
        state["log"].append("你在帕拉斯安全休息。疲惫逐渐退去，伤势得到稳定处理；这段恢复消耗了一次行动。")
        self._sync_character_layers(state)
        save_game(game_id, state)
        return state, recovery

    def dialogue(self, game_id: str, npc_id: str) -> tuple[dict[str, Any], str]:
        state = self.get(game_id)
        npc = next((n for n in self.npcs if n["id"] == npc_id), None)
        if not npc:
            raise ValueError("找不到这个人")
        text = self.ai.generate_dialogue(npc, state["relationships"][npc_id])
        state["log"].append(text)
        save_game(game_id, state)
        return state, text
