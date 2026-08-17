from __future__ import annotations

import copy
import hashlib
import json
import random
from pathlib import Path
from typing import Any


DATA_DIR = Path(__file__).resolve().parents[2] / "game-data"


class HeroActorService:
    """Deterministic V1 simulation for Yasuo. It never decides player outcomes."""

    def __init__(self) -> None:
        config = json.loads((DATA_DIR / "hero_actors.json").read_text(encoding="utf-8"))
        self.templates = {item["id"]: item for item in config["actors"]}

    def initial_state(self) -> dict[str, Any]:
        template = self.templates["yasuo"]
        return {
            "yasuo": {
                "heroId": "yasuo", "status": "active", "protectedCanonHero": True,
                "currentRegion": template["currentRegion"], "currentLocation": template["initialLocation"],
                "lastLocation": None, "activityZones": copy.deepcopy(template["activityZones"]),
                "currentGoal": copy.deepcopy(template["currentGoal"]), "goalProgress": 0,
                "activeThreads": list(template["activeThreads"]), "availability": "available",
                "actionPoints": 1, "lastAction": None, "lastEncounterTime": None,
                "playerRelation": {"recognition": 0, "trust": 0, "respect": 0, "alignment": 0},
                "importantMemories": [], "lastEncounterLevel": 0,
            }
        }

    def normalize(self, state: dict[str, Any]) -> bool:
        changed = False
        if "heroActors" not in state:
            state["heroActors"] = self.initial_state()
            changed = True
        initial = self.initial_state()["yasuo"]
        runtime = state["heroActors"].setdefault("yasuo", copy.deepcopy(initial))
        for key, value in initial.items():
            if key not in runtime:
                runtime[key] = copy.deepcopy(value)
                changed = True
        if "heroActionLog" not in state:
            state["heroActionLog"] = []
            changed = True
        legacy = state.get("heroRelationships", {}).get("yasuo")
        if legacy and not any(runtime["playerRelation"].values()):
            score = int(legacy.get("score", 0))
            runtime["playerRelation"].update({"recognition": max(0, min(100, score * 2)), "trust": score, "respect": max(0, score), "alignment": 0})
            changed = True
        return changed

    @staticmethod
    def _thread(state: dict[str, Any], thread_id: str) -> dict[str, Any] | None:
        return next((item for item in state.get("worldState", {}).get("activeThreads", []) if item["id"] == thread_id), None)

    def _goal_weights(self, runtime: dict[str, Any], thread: dict[str, Any] | None) -> dict[str, int]:
        weights = dict(self.templates["yasuo"]["activityZones"])
        if thread and not thread.get("resolved"):
            if thread.get("stage", 0) >= 3:
                weights.update({"war_ruins": 70, "pallas": 20, "windbreak": 5, "mountain_temple": 5})
            elif thread.get("stage", 0) >= 1:
                weights.update({"war_ruins": 45, "pallas": 25, "windbreak": 20, "mountain_temple": 10})
        elif thread and thread.get("resolved"):
            weights.update({"pallas": 40, "windbreak": 30, "mountain_temple": 20, "war_ruins": 10})
        return weights

    @staticmethod
    def _weighted_pick(weights: dict[str, int], seed: str) -> str:
        rng = random.Random(int(hashlib.sha256(seed.encode()).hexdigest()[:16], 16))
        threshold = rng.random() * sum(weights.values())
        cursor = 0.0
        for location, weight in weights.items():
            cursor += weight
            if threshold <= cursor:
                return location
        return next(reversed(weights))

    def tick(self, state: dict[str, Any]) -> dict[str, Any]:
        """Spend one Hero AP after a WorldThread tick; stages remain program-owned elsewhere."""
        self.normalize(state)
        runtime = state["heroActors"]["yasuo"]
        world_time = int(state.get("worldState", {}).get("worldTime", state.get("time", {}).get("total_actions", 0)))
        runtime["actionPoints"] = 1
        if runtime["availability"] in {"departed", "injured", "hidden"}:
            action = {"type": "unavailable", "worldTime": world_time, "location": runtime["currentLocation"], "summary": "亚索暂时没有公开行踪。"}
        else:
            thread = self._thread(state, runtime["currentGoal"]["threadId"])
            runtime["activityZones"] = self._goal_weights(runtime, thread)
            allowed = self.templates["yasuo"]["routeGraph"].get(runtime["currentLocation"], [runtime["currentLocation"]])
            possible = {location: runtime["activityZones"].get(location, 1) for location in allowed}
            target = self._weighted_pick(possible, f"{state.get('id')}:{world_time}:yasuo:{runtime['currentGoal']['id']}")
            previous = runtime["currentLocation"]
            runtime["lastLocation"] = previous
            runtime["currentLocation"] = target
            if target != previous:
                action = {"type": "move_toward_goal", "worldTime": world_time, "from": previous, "location": target, "summary": f"亚索沿着诺克萨斯活动留下的方向前往{target}。", "publicTrace": "路边留下了一道被风削平的断枝，切口干净得不像寻常刀刃。"}
                runtime["goalProgress"] = min(100, runtime["goalProgress"] + 3)
            else:
                action = {"type": "investigate_noxus", "worldTime": world_time, "location": target, "summary": "亚索独自调查附近的诺克萨斯活动痕迹。", "publicTrace": "一串陌生脚印在乱石前突然中断，旁边只有一道极利落的剑痕。", "publicRumor": "有人说，昨天有个背剑的浪人在附近问过诺克萨斯斥候的去向。"}
                runtime["goalProgress"] = min(100, runtime["goalProgress"] + (7 if target == "war_ruins" else 4))
                if thread and not thread.get("resolved") and target in {"war_ruins", "pallas"}:
                    thread["urgency"] = max(0, thread["urgency"] - 1)
                    action["limitedThreadEffect"] = {"threadId": thread["id"], "urgencyDelta": -1, "stageDelta": 0}
        runtime["actionPoints"] = 0
        runtime["lastAction"] = action
        state["heroActionLog"] = (state.get("heroActionLog", []) + [copy.deepcopy(action)])[-30:]
        return action

    def encounter(self, state: dict[str, Any], location: str, *, force_level: int | None = None) -> dict[str, Any]:
        self.normalize(state)
        runtime = state["heroActors"]["yasuo"]
        relation = runtime["playerRelation"]
        world_time = int(state.get("worldState", {}).get("worldTime", 0))
        same_region = runtime["currentRegion"] == "ionia_east"
        same_location = runtime["currentLocation"] == location
        recent_action_here = (runtime.get("lastAction") or {}).get("location") == location
        recent_gap = 99 if runtime.get("lastEncounterTime") is None else world_time - runtime["lastEncounterTime"]
        overlap = 1.0 if same_location else 0.42 if recent_action_here else 0.0
        goal_relevance = runtime.get("activityZones", {}).get(location, 0) / 100
        thread = self._thread(state, runtime["currentGoal"]["threadId"])
        thread_relevance = 1.35 if thread and not thread.get("resolved") and location in {"pallas", "war_ruins"} else 0.85
        availability = 1.0 if runtime["availability"] == "available" else 0.0
        relationship = 1 + max(-0.4, min(0.8, (relation["recognition"] + relation["trust"] + relation["respect"]) / 180))
        recency = 0.22 if recent_gap <= 1 else 0.55 if recent_gap <= 3 else 1.0
        director_modifier = 0.75 if state.get("directorState", {}).get("narrativeBudget", {}).get("heroUsed", 0) >= 1 else 1.0
        random_factor = 0.85 + (int(hashlib.sha256(f"{state.get('id')}:{world_time}:{location}:encounter".encode()).hexdigest()[:8], 16) % 31) / 100
        weight = 0.32 * overlap * max(0.15, goal_relevance) * thread_relevance * availability * relationship * recency * director_modifier * random_factor if same_region else 0.0
        if force_level is not None:
            level = force_level
        elif not same_region or (not same_location and not recent_action_here):
            level = 0
        elif not same_location:
            level = 2 if runtime.get("lastAction", {}).get("publicRumor") else 1
        elif relation["trust"] >= 20 and relation["recognition"] >= 30:
            level = 5
        elif relation["recognition"] >= 10:
            level = 4
        elif recent_gap <= 1:
            level = 3
        else:
            roll = int(hashlib.sha256(f"{state.get('id')}:{world_time}:{location}:level".encode()).hexdigest()[:8], 16) % 100
            level = 4 if roll < min(45, int(weight * 100)) else 3 if roll < 70 else 2 if runtime.get("lastAction", {}).get("publicRumor") else 1
        trace = (runtime.get("lastAction") or {}).get("publicTrace")
        rumor = (runtime.get("lastAction") or {}).get("publicRumor")
        labels = {0: "none", 1: "trace", 2: "rumor", 3: "glimpse", 4: "interaction", 5: "cooperation"}
        result = {
            "heroId": "yasuo", "level": level, "levelName": labels[level],
            "trace": trace if level == 1 else None, "rumor": rumor if level == 2 else None,
            "currentLocation": runtime["currentLocation"] if level >= 3 else None,
            "weight": round(weight, 6),
            "weightDebug": {
                "locationOverlap": overlap, "goalRelevance": round(goal_relevance, 4),
                "threadRelevance": thread_relevance, "availabilityModifier": availability,
                "relationshipModifier": round(relationship, 4), "recentHeroModifier": recency,
                "directorModifier": director_modifier, "randomFactor": random_factor,
            },
        }
        runtime["lastEncounterLevel"] = level
        return result

    def record_encounter(self, state: dict[str, Any], level: int) -> None:
        """Record an encounter only after the selected scene actually exposes Yasuo."""
        if level < 3:
            return
        runtime = state["heroActors"]["yasuo"]
        runtime["lastEncounterLevel"] = level
        runtime["lastEncounterTime"] = int(state.get("worldState", {}).get("worldTime", 0))

    def canon_prompt(self, lore_service: Any, state: dict[str, Any]) -> dict[str, Any]:
        profile = lore_service.champion("yasuo") or {}
        runtime = state.get("heroActors", {}).get("yasuo", {})
        template = self.templates["yasuo"]
        return {
            "canon": {
                "name": profile.get("name", "亚索"), "title": profile.get("title"),
                "profile": profile.get("profile"), "personality": profile.get("personality", []),
                "abilities": profile.get("abilities", []), "motivation": profile.get("motivation"),
                "status": profile.get("status"), "relationships": profile.get("relationship_edges", []),
                "voice": "寡言、克制、带自嘲；不轻易承诺，也不会因一次成功交涉倾吐所有秘密。",
                "behaviorBoundaries": template["narrativePowerBoundary"],
            },
            "runtime": copy.deepcopy(runtime),
        }
