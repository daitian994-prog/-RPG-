from __future__ import annotations

import hashlib
import json
import random
from pathlib import Path
from typing import Any


DATA_DIR = Path(__file__).resolve().parents[2] / "game-data"
ABILITY_KEYS = ("martial", "physique", "perception", "willpower", "agility", "social")
THREAD_RELEVANCE = {
    "noxian_remnants": {"pallas": "medium", "windbreak": "high", "war_ruins": "low", "mountain_temple": "medium"},
    "spirit_anomaly": {"pallas": "low", "windbreak": "high", "war_ruins": "medium", "mountain_temple": "high"},
}
THREAD_INTENTS = ("rumor", "rumor", "clue", "investigation", "encounter", "conflict", "aftermath")


class DynamicEventService:
    """Compose deterministic event mechanics from independent world components."""

    def __init__(self) -> None:
        self.config = json.loads((DATA_DIR / "dynamic_event_components.json").read_text(encoding="utf-8"))

    @staticmethod
    def _seed(state: dict[str, Any], location_id: str) -> str:
        material = {
            "game": state.get("id", "simulation"), "location": location_id,
            "worldTime": state.get("worldState", {}).get("worldTime", state.get("time", {}).get("total_actions", 0)),
            "threads": [(item["id"], item["stage"], item["urgency"], item["awareness"], item["resolved"]) for item in state.get("worldState", {}).get("activeThreads", [])],
            "condition": state.get("player", {}).get("bodyCondition", {}).get("state", "healthy"),
            "abilities": state.get("player", {}).get("coreAbilities", {}),
            "focus": state.get("directorState", {}).get("focus", []),
        }
        return hashlib.sha256(json.dumps(material, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()

    @staticmethod
    def _pick(values: list[Any], seed: str, salt: str) -> Any:
        digest = hashlib.sha256(f"{seed}:{salt}".encode()).hexdigest()
        return values[int(digest[:12], 16) % len(values)]

    def _approaches(self, state: dict[str, Any], seed: str, slot: int, difficulty: int, subject: str) -> list[dict[str, Any]]:
        abilities = state.get("player", {}).get("coreAbilities", {key: 8 for key in ABILITY_KEYS})
        strongest = max(ABILITY_KEYS, key=lambda key: (abilities.get(key, 8), key))
        weakest = min(ABILITY_KEYS, key=lambda key: (abilities.get(key, 8), key))
        rotated = list(ABILITY_KEYS)
        random.Random(int(hashlib.sha256(f"{seed}:approach:{slot}".encode()).hexdigest()[:16], 16)).shuffle(rotated)
        selected = []
        for key in (strongest, rotated[0], weakest, *rotated):
            if key not in selected:
                selected.append(key)
            if len(selected) == 3:
                break
        choices = []
        for index, key in enumerate(selected):
            approach = self.config["approaches"][key]
            clue = {"name": f"关于{subject}的可靠线索", "source": "动态事件", "modifiers": {"perception": 5}, "events": []}
            result: dict[str, Any] = {"text": approach["result"], "personality": {approach["trait"]: 3}}
            if key == "perception":
                result["clues"] = [clue]
            if key == "physique":
                result["statuses"] = [{"id": "dynamic_strain", "name": "劳损", "source": subject, "duration": 1, "modifiers": {"physique": -5}, "on": "partial"}]
            choices.append({
                "id": f"{key}-{index}", "text": f"{approach['label']}：处理{subject}", "hint": approach["hint"],
                "attribute": key, "difficulty": max(5, min(12, difficulty + (index - 1))), "result": result,
            })
        return choices

    def _compose(
        self, state: dict[str, Any], location_id: str, seed: str, slot: int, *, category: str,
        intent: str, thread: dict[str, Any] | None = None, hero: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        loc = self.config["locations"][location_id]
        setting = self._pick(loc["settings"], seed, f"setting:{slot}")
        actor = hero["name"] if hero else self._pick(loc["actors"], seed, f"actor:{slot}")
        obj = self._pick(loc["objects"], seed, f"object:{slot}")
        pressure = self._pick(loc["pressures"], seed, f"pressure:{slot}")
        profile = self.config["intents"][intent]
        title_pattern = self._pick(profile["titles"], seed, f"title:{slot}")
        title = title_pattern.format(object=obj, setting=setting, actor=actor)
        stage_fact = thread["stages"][thread["stage"]] if thread else None
        thread_line = f"这并非孤立事故：{thread['title']}当前处于“{stage_fact}”。" if thread else "这件事来自此地自行运转的日常，而非等待你领取的任务。"
        hero_line = f"{actor}没有表明完整身份，也没有替你处理问题；他只是因自己的目标短暂经过现场。" if hero else ""
        text = f"{setting}，{actor}正在查看{obj}。{pressure}。{thread_line}{hero_line}"
        intensity = "climax" if thread and not thread.get("resolved") and thread["stage"] >= thread["maxStage"] - 1 else profile["intensity"]
        difficulty = 6 if intensity == "low" else 8 if intensity == "medium" else 10 if intensity == "high" else 11
        composition = f"{location_id}|{category}|{intent}|{setting}|{actor}|{obj}|{pressure}|{stage_fact or '-'}"
        event_id = "dyn-" + hashlib.sha256(f"{seed}:{slot}:{composition}".encode()).hexdigest()[:16]
        return {
            "id": event_id, "type": profile["type"], "locations": [location_id], "title": title, "text": text,
            "choices": self._approaches(state, seed, slot, difficulty, obj),
            "dynamic": True, "compositionKey": hashlib.sha256(composition.encode()).hexdigest()[:12],
            "components": {"setting": setting, "actor": actor, "object": obj, "pressure": pressure, "stageFact": stage_fact},
            "directorProfile": {
                "category": category, "intents": [intent], "intensity": intensity,
                "baseWeight": 0.58 if category == "hero" else 0.82 if category == "world_thread" else 1.0,
                "threadId": thread["id"] if thread else None,
                "heroId": hero["id"] if hero else None, "heroName": hero["name"] if hero else None,
                "locationRelevance": THREAD_RELEVANCE.get(thread["id"], {}).get(location_id, "high") if thread else "high",
            },
        }

    def generate_pool(self, state: dict[str, Any], location_id: str) -> list[dict[str, Any]]:
        if location_id not in self.config["locations"]:
            raise ValueError("这个地点尚未配置动态事件组件")
        seed = self._seed(state, location_id)
        tension = state.get("directorState", {}).get("tension", 22)
        ambient_intents = ["environmental", "rumor", "clue", "opportunity", "personal", "npc_report"]
        if tension >= 55:
            ambient_intents.extend(["investigation", "encounter", "conflict"])
        pool = []
        for slot in range(9):
            intent = "conflict" if tension >= 55 and slot == 8 else self._pick(ambient_intents, seed, f"intent:{slot}")
            category = "personal" if intent == "personal" or (slot % 5 == 3) else "environment"
            pool.append(self._compose(state, location_id, seed, slot, category=category, intent=intent))
        slot = 20
        for thread in state.get("worldState", {}).get("activeThreads", []):
            relevance = THREAD_RELEVANCE.get(thread["id"], {}).get(location_id, "none")
            if relevance == "none":
                continue
            intent = "aftermath" if thread.get("resolved") else THREAD_INTENTS[min(thread["stage"], len(THREAD_INTENTS) - 1)]
            pool.append(self._compose(state, location_id, seed, slot, category="world_thread", intent=intent, thread=thread))
            slot += 1
        heroes = self.config["heroByLocation"].get(location_id, [])
        if heroes:
            hero = self._pick(heroes, seed, "hero")
            pool.append(self._compose(state, location_id, seed, 30, category="hero", intent="hero_overlap", hero=hero))
        return pool
