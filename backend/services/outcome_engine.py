from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import Any


class OutcomeEngine:
    """Write already-decided outcomes back to the world and produce an audit trail."""

    LIMIT = 50
    AWARENESS_GAIN = {"critical": 12, "success": 8, "partial": 4, "failure": 2}
    HERO_RELATION = {"critical": 6, "success": 4, "partial": 1, "failure": -2}

    @staticmethod
    def snapshot(state: dict[str, Any]) -> dict[str, Any]:
        return copy.deepcopy({
            "location": state.get("location"), "time": state.get("time"), "action_points": state.get("action_points"),
            "player": {
                "coreAbilities": state.get("player", {}).get("coreAbilities", {}),
                "personality": state.get("player", {}).get("personality", {}),
                "injurySeverity": state.get("player", {}).get("injurySeverity"),
                "statuses": state.get("player", {}).get("statuses", []),
                "clues": state.get("player", {}).get("clues", []),
                "traits": state.get("player", {}).get("traits", []),
                "inventory": state.get("player", {}).get("inventory", []),
            },
            "relationships": state.get("relationships", {}), "heroRelationships": state.get("heroRelationships", {}),
            "heroActors": state.get("heroActors", {}),
            "worldState": state.get("worldState", {}), "directorState": state.get("directorState", {}),
            "aiNarratorDebug": state.get("aiNarratorDebug", {}),
        })

    @classmethod
    def _diff(cls, before: Any, after: Any, path: str = "") -> list[dict[str, Any]]:
        if before == after:
            return []
        if isinstance(before, dict) and isinstance(after, dict):
            result: list[dict[str, Any]] = []
            for key in sorted(set(before) | set(after)):
                child = f"{path}.{key}" if path else key
                if key not in before:
                    result.append({"path": child, "before": None, "after": after[key]})
                elif key not in after:
                    result.append({"path": child, "before": before[key], "after": None})
                else:
                    result.extend(cls._diff(before[key], after[key], child))
            return result
        return [{"path": path, "before": before, "after": after}]

    def record(self, state: dict[str, Any], action: str, before: dict[str, Any], *, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        entry = {
            "sequence": (state.setdefault("stateChangeLog", [])[-1]["sequence"] + 1) if state["stateChangeLog"] else 1,
            "at": datetime.now(timezone.utc).isoformat(), "worldTime": state.get("time", {}).get("total_actions", 0),
            "action": action, "metadata": metadata or {}, "changes": self._diff(before, self.snapshot(state)),
        }
        state["stateChangeLog"] = (state["stateChangeLog"] + [entry])[-self.LIMIT:]
        return entry

    @staticmethod
    def _relation_stage(value: int) -> str:
        return "close" if value >= 40 else "trusted" if value >= 20 else "recognized" if value >= 5 else "hostile" if value <= -20 else "wary" if value < 0 else "stranger"

    def apply_world_feedback(self, state: dict[str, Any], director: dict[str, Any], outcome: dict[str, Any], choice: dict[str, Any]) -> dict[str, Any]:
        feedback = {"thread": None, "hero": None, "newPlayableSituation": None}
        tier = outcome["code"]
        thread_id = director.get("threadId")
        if thread_id:
            thread = next((item for item in state.get("worldState", {}).get("activeThreads", []) if item["id"] == thread_id), None)
            if thread:
                before = {"stage": thread["stage"], "urgency": thread["urgency"], "awareness": thread["awareness"]}
                thread["awareness"] = min(100, thread["awareness"] + self.AWARENESS_GAIN[tier])
                if tier in {"critical", "success"} and director.get("intent") in {"investigation", "conflict", "encounter", "clue"}:
                    thread["urgency"] = max(0, thread["urgency"] - (6 if tier == "critical" else 3))
                thread["playerInterventions"].append({
                    "worldTime": state["time"]["total_actions"], "strategy": "event_choice",
                    "eventId": director.get("eventId"), "choice": choice.get("id", choice.get("text")), "tier": tier,
                })
                if tier == "failure":
                    hook = f"{thread['title']}留下了新的困难：你需要处理这次失败暴露的风险。"
                    if hook not in state["worldState"]["followUpHooks"]:
                        state["worldState"]["followUpHooks"].append(hook)
                    feedback["newPlayableSituation"] = hook
                feedback["thread"] = {"id": thread_id, "before": before, "after": {"stage": thread["stage"], "urgency": thread["urgency"], "awareness": thread["awareness"]}}
        hero_id = director.get("heroId")
        if hero_id:
            relation = state.setdefault("heroRelationships", {}).setdefault(hero_id, {"score": 0, "stage": "stranger", "history": []})
            delta = self.HERO_RELATION[tier]
            relation["score"] += delta
            relation["stage"] = self._relation_stage(relation["score"])
            relation["history"].append({"worldTime": state["time"]["total_actions"], "eventId": director.get("eventId"), "tier": tier, "delta": delta})
            relation["history"] = relation["history"][-12:]
            runtime = state.get("heroActors", {}).get(hero_id)
            memory = None
            if runtime:
                actor_relation = runtime.setdefault("playerRelation", {"recognition": 0, "trust": 0, "respect": 0, "alignment": 0})
                actor_relation["recognition"] = min(100, max(actor_relation["recognition"], 12) + (8 if tier in {"critical", "success"} else 3))
                actor_relation["trust"] = max(-100, min(100, actor_relation["trust"] + delta))
                actor_relation["respect"] = max(-100, min(100, actor_relation["respect"] + (5 if tier == "critical" else 3 if tier == "success" else 1 if tier == "partial" else -1)))
                personality = choice.get("result", {}).get("personality", {})
                alignment_delta = personality.get("peace", 0) + personality.get("freedom", 0) - personality.get("power", 0)
                actor_relation["alignment"] = max(-100, min(100, actor_relation["alignment"] + max(-3, min(3, alignment_delta))))
                if tier in {"critical", "success", "failure"}:
                    importance = 4 if tier == "critical" else 3
                    memory = {
                        "id": f"{director.get('eventId', 'event')}:{choice.get('id', 'choice')}",
                        "type": "shared_action" if tier != "failure" else "failed_commitment",
                        "summary": f"玩家在{director.get('eventId', '一次相逢')}中选择“{choice.get('semanticAction', choice.get('text'))}”，结果为{outcome['label']}。",
                        "importance": importance, "worldTime": state.get("worldState", {}).get("worldTime", 0),
                        "relatedThread": director.get("threadId"),
                    }
                    memories = runtime.setdefault("importantMemories", [])
                    if memory["id"] not in {item.get("id") for item in memories}:
                        memories.append(memory)
                        runtime["importantMemories"] = memories[-12:]
                if tier in {"critical", "success"} and director.get("threadId") in runtime.get("activeThreads", []):
                    runtime["goalProgress"] = min(100, runtime.get("goalProgress", 0) + (4 if tier == "critical" else 2))
            feedback["hero"] = {"id": hero_id, "delta": delta, "score": relation["score"], "stage": relation["stage"], "runtimeRelation": copy.deepcopy(runtime.get("playerRelation")) if runtime else None, "importantMemory": memory}
        return feedback
