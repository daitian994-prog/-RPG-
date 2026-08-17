from __future__ import annotations

import copy
import hashlib
import json
import random
from pathlib import Path
from typing import Any


DATA_DIR = Path(__file__).resolve().parents[2] / "game-data"
CATEGORY_LABELS = {
    "environment": "环境事件",
    "world_thread": "世界线程事件",
    "personal": "玩家个人事件",
    "hero": "英雄 / 特殊事件",
}
RELEVANCE = {"high": 1.65, "medium": 1.20, "low": 0.68, "none": 0.10}
INTENSITY_SCORE = {"low": 20, "medium": 48, "high": 72, "climax": 92}


class EventDirectorService:
    """Seeded event selection. It reads WorldThread facts but never advances them."""

    def __init__(self) -> None:
        self.config = json.loads((DATA_DIR / "event_director.json").read_text(encoding="utf-8"))

    def initial_state(self) -> dict[str, Any]:
        return {
            "tension": 22,
            "recentEvents": [],
            "narrativeBudget": {"window": 5, "majorUsed": 0, "heroUsed": 0},
            "recentHeroes": [],
            "focus": [],
            "lastSelection": None,
        }

    def normalize(self, state: dict[str, Any]) -> bool:
        if "directorState" not in state:
            state["directorState"] = self.initial_state()
            return True
        changed = False
        defaults = self.initial_state()
        for key, value in defaults.items():
            if key not in state["directorState"]:
                state["directorState"][key] = copy.deepcopy(value)
                changed = True
        director = state["directorState"]
        director["tension"] = max(0, min(100, int(director.get("tension", 22))))
        director["recentEvents"] = list(director.get("recentEvents", []))[-10:]
        director["recentHeroes"] = list(director.get("recentHeroes", []))[-6:]
        director["focus"] = list(dict.fromkeys(director.get("focus", [])))
        self._update_budget(director)
        return changed

    @staticmethod
    def _stable_seed(state: dict[str, Any], location: str) -> str:
        snapshot = {
            "game": state.get("id", "simulation"),
            "worldTime": state.get("worldState", {}).get("worldTime", state.get("time", {}).get("total_actions", 0)),
            "location": location,
            "history": [item.get("candidateId") for item in state.get("directorState", {}).get("recentEvents", [])[-5:]],
            "focus": state.get("directorState", {}).get("focus", []),
        }
        return hashlib.sha256(json.dumps(snapshot, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()

    @staticmethod
    def _intent(profile: dict[str, Any], seed: str) -> str:
        intents = profile.get("intents", ["environmental"])
        return intents[int(seed[:8], 16) % len(intents)]

    def _base_candidates(self, state: dict[str, Any], events: list[dict[str, Any]], location: str, seed: str) -> list[dict[str, Any]]:
        result = []
        for event in events:
            if event.get("chapter_only") or location not in event.get("locations", []):
                continue
            profile = event.get("directorProfile", {"category": "environment", "intents": ["environmental"], "intensity": "low", "baseWeight": 1.0})
            candidate = {
                "candidateId": f"dynamic:{event['id']}", "templateId": event["id"],
                "compositionKey": event.get("compositionKey", event["id"]),
                "category": profile["category"], "threadId": profile.get("threadId"),
                "intent": self._intent(profile, hashlib.sha256(f"{seed}:{event['id']}".encode()).hexdigest()),
                "intensity": profile["intensity"], "baseWeight": float(profile["baseWeight"]),
                "heroId": profile.get("heroId"), "heroName": profile.get("heroName"),
                "locationRelevance": profile.get("locationRelevance", "high"),
                "dynamicComponents": event.get("components", {}),
            }
            if candidate["threadId"]:
                thread = next((item for item in state.get("worldState", {}).get("activeThreads", []) if item["id"] == candidate["threadId"]), None)
                if not thread:
                    continue
                stage = thread["stage"]
                candidate.update({
                    "threadTitle": thread["title"], "threadStage": stage, "threadStageLabel": thread["stages"][stage],
                    "threadUrgency": int(thread.get("urgency", 0)), "threadAwareness": int(thread.get("awareness", 0)),
                    "threadResolved": bool(thread.get("resolved")),
                    "worldEffects": list(thread.get("worldEffects", [])) if stage >= 4 or thread.get("resolved") else [],
                    "followUpHooks": list(thread.get("resolvedOutcome", {}).get("followUpHooks", [])) if thread.get("resolved") else [],
                })
            result.append(candidate)
        return result

    @staticmethod
    def _tension_modifier(tension: int, intensity: str) -> float:
        distance = abs(tension - INTENSITY_SCORE[intensity])
        return max(0.42, 1.48 - distance / 72)

    @staticmethod
    def _recent_modifier(candidate: dict[str, Any], recent: list[dict[str, Any]]) -> float:
        same_template = sum(item.get("compositionKey", item.get("templateId")) == candidate.get("compositionKey", candidate["templateId"]) for item in recent[-5:])
        same_category = sum(item.get("category") == candidate["category"] for item in recent[-4:])
        same_thread = candidate.get("threadId") and sum(item.get("threadId") == candidate.get("threadId") for item in recent[-4:])
        return 1 / (1 + same_template * 0.72 + same_category * 0.16 + int(same_thread or 0) * 0.22)

    @staticmethod
    def _budget_modifier(candidate: dict[str, Any], recent: list[dict[str, Any]]) -> float:
        window = recent[-5:]
        major = sum(item.get("intensity") in {"high", "climax"} for item in window)
        heroes = sum(item.get("category") == "hero" for item in window)
        if candidate["category"] == "hero":
            return 1 / (1 + heroes * 1.8 + major * 0.22)
        if candidate["intensity"] in {"high", "climax"}:
            return 1 / (1 + major * 0.58)
        return 1.0 + min(0.25, major * 0.05)

    def _score(self, candidate: dict[str, Any], state: dict[str, Any], seed: str) -> dict[str, Any]:
        director = state["directorState"]
        recent = director["recentEvents"]
        thread_stage = 1.0
        urgency = 1.0
        if candidate.get("threadId"):
            thread_stage = 0.72 + candidate.get("threadStage", 0) * 0.13
            urgency = 0.80 + candidate.get("threadUrgency", 0) / 125
            if candidate.get("threadResolved"):
                urgency *= 0.55
        focus = 1.25 if candidate.get("threadId") in director.get("focus", []) else 1.0
        relevance = RELEVANCE.get(candidate.get("locationRelevance", "medium"), 1.0)
        tension = self._tension_modifier(director["tension"], candidate["intensity"])
        recent_factor = self._recent_modifier(candidate, recent)
        budget = self._budget_modifier(candidate, recent)
        random_seed = hashlib.sha256(f"{seed}:{candidate['candidateId']}".encode()).hexdigest()
        rng = random.Random(int(random_seed[:16], 16))
        bounds = self.config["randomFactor"]
        random_factor = rng.uniform(bounds["min"], bounds["max"])
        modifiers = {
            "threadStage": round(thread_stage, 4), "urgency": round(urgency, 4),
            "tension": round(tension, 4), "recentHistory": round(recent_factor, 4),
            "playerFocus": round(focus, 4), "worldRelevance": round(relevance, 4),
            "narrativeBudget": round(budget, 4), "randomFactor": round(random_factor, 4),
        }
        final = candidate["baseWeight"]
        for value in modifiers.values():
            final *= value
        return {**candidate, "modifiers": modifiers, "finalWeight": round(max(0.0001, final), 6)}

    def candidates(self, state: dict[str, Any], location: str, events: list[dict[str, Any]]) -> list[dict[str, Any]]:
        self.normalize(state)
        seed = self._stable_seed(state, location)
        raw = self._base_candidates(state, events, location, seed)
        return [self._score(candidate, state, seed) for candidate in raw]

    def select(self, state: dict[str, Any], location: str, events: list[dict[str, Any]]) -> dict[str, Any]:
        seed = self._stable_seed(state, location)
        candidates = self.candidates(state, location, events)
        if not candidates:
            raise ValueError("这个地点暂时没有可用事件")
        rng = random.Random(int(seed[-16:], 16))
        threshold = rng.random() * sum(item["finalWeight"] for item in candidates)
        selected = candidates[-1]
        cursor = 0.0
        for candidate in candidates:
            cursor += candidate["finalWeight"]
            if threshold <= cursor:
                selected = candidate
                break
        selection_seed = hashlib.sha256(f"{seed}:{selected['candidateId']}".encode()).hexdigest()[:20]
        occurrence = f"{selected['templateId']}@{state.get('time', {}).get('total_actions', 0)}-{selection_seed[:8]}"
        snapshot = {
            **selected,
            "eventId": occurrence,
            "seed": selection_seed,
            "categoryLabel": CATEGORY_LABELS[selected["category"]],
            "intentLabel": self.config["intentLabels"].get(selected["intent"], selected["intent"]),
            "candidateWeights": candidates,
        }
        return snapshot

    def context(self, state: dict[str, Any], selection: dict[str, Any], location_name: str) -> str:
        intent_label = selection.get("intentLabel") or self.config["intentLabels"].get(selection["intent"], selection["intent"])
        if selection["category"] == "world_thread":
            known = selection.get("threadAwareness", 0) >= 20
            subject = selection.get("threadTitle") if known else "一股尚未辨明的变化"
            effects = "附近已经能看见" + "、".join(selection.get("worldEffects", [])) + "。" if selection.get("worldEffects") else ""
            concerns = "人们仍在担心" + "、".join(selection.get("followUpHooks", [])) + "。" if selection.get("followUpHooks") else ""
            return f"关于{subject}的迹象已经来到{location_name}，眼前的人只知道自己亲眼见到的这一小部分。{effects}{concerns}"
        if selection["category"] == "hero":
            return f"一名不轻易表明身份的旅人来到{location_name}，他显然另有去处，也无意替任何人收拾眼前的麻烦。"
        if selection["category"] == "personal":
            condition = state.get("player", {}).get("bodyCondition", {}).get("label", "良好")
            return f"你近期的经历与{condition}的身体状态，让眼前这件事显得格外切身。"
        return f"{location_name}的日常并未因为你的到来停下，眼前的变化已经引起了附近人的注意。"

    def record_selection(self, state: dict[str, Any], selection: dict[str, Any]) -> None:
        director = state["directorState"]
        public = {key: value for key, value in selection.items() if key != "candidateWeights"}
        director["recentEvents"] = (director["recentEvents"] + [public])[-10:]
        if selection.get("heroId"):
            director["recentHeroes"] = (director["recentHeroes"] + [{"heroId": selection["heroId"], "worldTime": state.get("time", {}).get("total_actions", 0)}])[-6:]
        tension = director["tension"]
        intensity = selection["intensity"]
        if intensity == "climax":
            tension = max(18, tension - 46)
        elif intensity == "high":
            tension = min(100, tension + 15)
        elif intensity == "medium":
            tension = min(100, tension + 8)
        else:
            tension = max(0, tension - 14) if tension >= 46 else min(100, tension + 4)
        director["tension"] = tension
        director["lastSelection"] = copy.deepcopy(selection)
        self._update_budget(director)

    @staticmethod
    def _update_budget(director: dict[str, Any]) -> None:
        window = director.get("recentEvents", [])[-5:]
        director["narrativeBudget"] = {
            "window": 5,
            "majorUsed": sum(item.get("intensity") in {"high", "climax"} for item in window),
            "heroUsed": sum(item.get("category") == "hero" for item in window),
        }

    def set_focus(self, state: dict[str, Any], topic_id: str, focused: bool) -> dict[str, Any]:
        self.normalize(state)
        known = next((thread for thread in state.get("worldState", {}).get("activeThreads", []) if thread["id"] == topic_id and (thread.get("awareness", 0) >= 20 or thread.get("resolved"))), None)
        if not known:
            raise ValueError("只能关注旅途日志中已经知晓的事项")
        focus = state["directorState"]["focus"]
        if focused and topic_id not in focus:
            focus.append(topic_id)
        if not focused and topic_id in focus:
            focus.remove(topic_id)
        return {"topicId": topic_id, "focused": topic_id in focus, "message": "旅途日志已更新。关注只会提高相关内容出现机会，不会垄断世界。"}
