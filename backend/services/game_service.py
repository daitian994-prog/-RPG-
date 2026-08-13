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

TRAIT_TO_FATE = {
    "peace": "guardian",
    "power": "strong",
    "freedom": "wanderer",
    "spirit": "spirit",
    "destiny": "breaker",
}
SEASONS = ["春", "夏", "秋", "冬"]
CHAPTER_ONE_ACTIONS = 12


class GameService:
    def __init__(self) -> None:
        init_db()
        self.ai = AIService()
        self.locations = self._read("locations.json")
        self.npcs = self._read("npc.json")
        self.events = self._read("events.json")
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
    def _initial_fate(personality: dict[str, int]) -> dict[str, int]:
        return {fate: 10 + personality[trait] for trait, fate in TRAIT_TO_FATE.items()}

    def _item(self, name: str) -> dict[str, Any]:
        item = self.item_catalog.get(name)
        if item:
            return {**item, "bonuses": dict(item.get("bonuses", {}))}
        return {"name": name, "rarity": "未知", "description": "这件物品的来历尚未被记录。", "bonuses": {}}

    def _apply_item_bonuses(self, player: dict[str, Any], item: dict[str, Any]) -> tuple[dict[str, int], dict[str, int]]:
        attribute_changes: dict[str, int] = {}
        fate_changes: dict[str, int] = {}
        for key, value in item.get("bonuses", {}).items():
            if key.endswith("_fate"):
                fate_key = key.removesuffix("_fate")
                player["fate_weights"][fate_key] += value
                fate_changes[fate_key] = fate_changes.get(fate_key, 0) + value
            elif key in player["attributes"]:
                player["attributes"][key] += value
                attribute_changes[key] = attribute_changes.get(key, 0) + value
                if key == "max_hp":
                    player["attributes"]["hp"] += value
                    attribute_changes["hp"] = attribute_changes.get("hp", 0) + value
        return attribute_changes, fate_changes

    def _normalize_state(self, state: dict[str, Any]) -> bool:
        """Upgrade V1 saves in place without discarding the player's journey."""
        player = state["player"]
        changed = False
        old_inventory = player.get("inventory", [])
        inventory_was_legacy = bool(old_inventory) and isinstance(old_inventory[0], str)

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
            player["fate_weights"] = self._initial_fate(player["personality"])
            changed = True
        if inventory_was_legacy:
            player["inventory"] = [self._item(name) for name in old_inventory]
            for item in player["inventory"]:
                self._apply_item_bonuses(player, item)
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
            "fate_weights": self._initial_fate(personality),
            "memories": [],
            "inventory": [],
        }
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
            "log": [birth["story"]],
        }
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
            "personality": state["player"]["personality"],
            "fate": state["player"]["fate_weights"],
            "completed": state["completed_events"], "relationships": state["relationships"],
        }
        return hashlib.sha256(json.dumps(snapshot, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()[:16]

    @staticmethod
    def _event_weight(event: dict[str, Any], fate: dict[str, int]) -> int:
        weights = {
            "日常": fate["guardian"],
            "探索": fate["wanderer"],
            "成长": max(fate["strong"], fate["spirit"]),
            "NPC": fate["guardian"],
            "战斗": fate["strong"],
            "命运": max(fate["breaker"], fate["spirit"]),
        }
        return max(1, weights.get(event["type"], 10))

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
        weights = [self._event_weight(event, state["player"]["fate_weights"]) for event in candidates]
        template = random.choices(candidates, weights=weights, k=1)[0]
        event = self.ai.generate_event(template, state, location, narrate=narrate)
        event["fate_influence"] = self._event_weight(template, state["player"]["fate_weights"])
        event["world_state_version"] = self.state_version(state)
        save_game(game_id, state)
        return state, event

    def _chapter_boss_event(self, state: dict[str, Any], *, narrate: bool = True) -> dict[str, Any]:
        template = next(event for event in self.events if event["id"] == "chapter1_boss")
        location = next(location for location in self.locations if location["id"] == "pallas")
        event = self.ai.generate_event(template, state, location, narrate=narrate)
        event["boss"] = template["boss"]
        event["chapter_finale"] = True
        event["world_state_version"] = self.state_version(state)
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
        event = next((e for e in self.events if e["id"] == event_id), None)
        if not event:
            raise ValueError("事件已经消散")
        choice = event["choices"][choice_index]
        result = choice["result"]
        player = state["player"]
        changes: dict[str, dict[str, int]] = {"personality": {}, "attributes": {}, "fate": {}, "relations": {}}
        costs: dict[str, dict[str, int]] = {"personality": {}, "attributes": {}, "fate": {}, "relations": {}}
        outcome = None if event["type"] == "战斗" else self.ai.evaluate_event_outcome(event, choice, state, choice_index)
        reward_multiplier = outcome["reward_multiplier"] if outcome else 1.0

        for trait, base_delta in result.get("personality", {}).items():
            delta = max(1, round(base_delta * reward_multiplier))
            player["personality"][trait] += delta
            changes["personality"][trait] = delta
            fate_key = TRAIT_TO_FATE[trait]
            player["fate_weights"][fate_key] += delta
            changes["fate"][fate_key] = changes["fate"].get(fate_key, 0) + delta

            growth = 0 if outcome and outcome["code"] == "failure" else max(1, math.ceil(delta / 3))
            stat_map = {
                "peace": {"max_hp": growth, "defense": max(1, growth - 1)},
                "power": {"attack": growth},
                "freedom": {"attack_speed": growth},
                "spirit": {"magic_power": growth, "magic_resist": max(1, growth - 1)},
                "destiny": {"skill_haste": growth},
            }
            if growth:
                for stat, value in stat_map[trait].items():
                    player["attributes"][stat] += value
                    changes["attributes"][stat] = changes["attributes"].get(stat, 0) + value
                    if stat == "max_hp":
                        player["attributes"]["hp"] += value
                        changes["attributes"]["hp"] = changes["attributes"].get("hp", 0) + value

        if outcome:
            tradeoff_trait = outcome["tradeoff_trait"]
            tradeoff_loss = min(outcome["tradeoff_loss"], max(0, player["personality"][tradeoff_trait] - 5))
            if tradeoff_loss:
                player["personality"][tradeoff_trait] -= tradeoff_loss
                changes["personality"][tradeoff_trait] = changes["personality"].get(tradeoff_trait, 0) - tradeoff_loss
                costs["personality"][tradeoff_trait] = -tradeoff_loss
                tradeoff_fate = TRAIT_TO_FATE[tradeoff_trait]
                player["fate_weights"][tradeoff_fate] = max(5, player["fate_weights"][tradeoff_fate] - tradeoff_loss)
                changes["fate"][tradeoff_fate] = changes["fate"].get(tradeoff_fate, 0) - tradeoff_loss
                costs["fate"][tradeoff_fate] = -tradeoff_loss
            if outcome["fate_setback"]:
                primary_fate = TRAIT_TO_FATE[outcome["primary_trait"]]
                setback = min(outcome["fate_setback"], max(0, player["fate_weights"][primary_fate] - 5))
                player["fate_weights"][primary_fate] -= setback
                changes["fate"][primary_fate] = changes["fate"].get(primary_fate, 0) - setback
                costs["fate"][primary_fate] = costs["fate"].get(primary_fate, 0) - setback

        for npc_id, delta in result.get("relations", {}).items():
            rel = state["relationships"][npc_id]
            adjusted_delta = round(delta * outcome["relationship_factor"]) if outcome else delta
            if adjusted_delta == 0 and outcome and outcome["code"] == "costly":
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

        battle: dict[str, Any] | None = None
        battle_text = ""
        if event["type"] == "战斗":
            stats = player["attributes"]
            is_boss = event.get("chapter_only", False)
            base_chance = 18 if is_boss else 36
            chance_cap = 78 if is_boss else 88
            chance = min(chance_cap, base_chance + stats["attack"] + stats["defense"] // 2 + stats["magic_power"] // 3 + choice_index * 3)
            victory = random.randint(1, 100) <= chance
            battle_text = self.ai.generate_battle_text(player, victory, choice_index)
            state["battle_complete"] = True
            battle = {"victory": victory, "chance": chance, "is_boss": is_boss, "boss": event.get("boss")}
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
                damage = min(30, max(12, 35 - stats["defense"]))
                stats["hp"] = max(1, stats["hp"] - damage)
                changes["attributes"]["hp"] = changes["attributes"].get("hp", 0) - damage
                costs["attributes"]["hp"] = costs["attributes"].get("hp", 0) - damage
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
            "narrative": narrative,
            "changes": changes,
            "costs": costs,
            "items": acquired_items,
            "missed_items": missed_items,
            "battle": battle,
            "outcome": outcome,
            "chapter_complete": state.get("chapter_complete", False),
        }
        if event_id not in state["completed_events"]:
            state["completed_events"].append(event_id)
        player["memories"].append(narrative)
        state["log"].append(narrative)
        state["last_resolution"] = resolution
        save_game(game_id, state)
        return state, resolution

    def dialogue(self, game_id: str, npc_id: str) -> tuple[dict[str, Any], str]:
        state = self.get(game_id)
        npc = next((n for n in self.npcs if n["id"] == npc_id), None)
        if not npc:
            raise ValueError("找不到这个人")
        text = self.ai.generate_dialogue(npc, state["relationships"][npc_id])
        state["log"].append(text)
        save_game(game_id, state)
        return state, text
