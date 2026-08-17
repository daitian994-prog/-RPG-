from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any


DATA_DIR = Path(__file__).resolve().parents[2] / "game-data"


class WorldThreadService:
    """Deterministic world progression. AI never changes stages or outcomes."""

    def __init__(self) -> None:
        self.templates = json.loads((DATA_DIR / "world_threads.json").read_text(encoding="utf-8"))
        self.template_index = {item["id"]: item for item in self.templates}

    def initial_state(self) -> dict[str, Any]:
        threads = []
        for template in self.templates:
            thread = copy.deepcopy(template)
            thread.update({
                "stage": 0,
                "progress": 0,
                "awareness": template["initialAwareness"],
                "interventionWindow": "OPEN",
                "lastProgressAt": 0,
                "resolved": False,
                "playerInterventions": [],
                "selectedOutcome": None,
            })
            threads.append(thread)
        return {"worldTime": 0, "activeThreads": threads, "globalFlags": [], "worldEffects": [], "followUpHooks": [], "recentSignals": []}

    def normalize(self, state: dict[str, Any]) -> bool:
        if "worldState" not in state:
            state["worldState"] = self.initial_state()
            state["worldState"]["worldTime"] = int(state.get("time", {}).get("total_actions", 0))
            return True
        world = state["worldState"]
        changed = False
        for key, default in {"globalFlags": [], "worldEffects": [], "followUpHooks": [], "recentSignals": []}.items():
            if key not in world:
                world[key] = copy.deepcopy(default)
                changed = True
        if world.get("worldTime") != int(state.get("time", {}).get("total_actions", 0)):
            world["worldTime"] = int(state.get("time", {}).get("total_actions", 0))
            changed = True
        existing = {thread["id"]: thread for thread in world.get("activeThreads", [])}
        for initial in self.initial_state()["activeThreads"]:
            if initial["id"] not in existing:
                world.setdefault("activeThreads", []).append(initial)
                changed = True
        return changed

    @staticmethod
    def _interval(urgency: int) -> int:
        return 1 if urgency >= 70 else 2 if urgency >= 45 else 3

    @staticmethod
    def _window(stage: int, max_stage: int, resolved: bool) -> str:
        if resolved or stage >= max_stage:
            return "CLOSED"
        if stage >= max_stage - 2:
            return "CLOSING"
        return "OPEN"

    @staticmethod
    def _append_unique(target: list[str], values: list[str]) -> None:
        for value in values:
            if value not in target:
                target.append(value)

    def _signal(self, thread: dict[str, Any], stage: int) -> dict[str, Any] | None:
        return next((item for item in thread["awarenessSignals"] if item["stage"] == stage), None)

    def advance(self, state: dict[str, Any], *, action: str, location: str) -> list[dict[str, Any]]:
        self.normalize(state)
        world = state["worldState"]
        world_time = int(state["time"]["total_actions"])
        world["worldTime"] = world_time
        emitted: list[dict[str, Any]] = []
        for thread in world["activeThreads"]:
            if thread["resolved"]:
                continue
            if world_time - thread["lastProgressAt"] < self._interval(thread["urgency"]):
                continue
            next_stage = min(thread["maxStage"], thread["stage"] + 1)
            schedule = thread.get("chapterStageSchedule", []) if state.get("chapter") == 1 and not state.get("chapter_complete") else []
            if schedule:
                stage_cap = max((item["maxStage"] for item in schedule if world_time >= item["at"]), default=0)
                if next_stage > stage_cap:
                    continue
            required_awareness = 60 if next_stage == thread["maxStage"] - 1 else 80 if next_stage == thread["maxStage"] else 0
            signal = self._signal(thread, next_stage)
            if required_awareness and thread["awareness"] < required_awareness:
                gain = max(signal.get("gain", 20) if signal else 20, required_awareness - thread["awareness"])
                thread["awareness"] = min(100, thread["awareness"] + gain)
                thread["lastProgressAt"] = world_time
                thread["interventionWindow"] = "CLOSING"
                emitted.append({"threadId": thread["id"], "title": thread["title"], "text": signal["text"] if signal else "局势已经明显恶化，留给行动的时间不多了。", "level": "urgent", "forcedOpportunity": True})
                continue
            thread["stage"] = next_stage
            thread["progress"] = next_stage
            thread["lastProgressAt"] = world_time
            thread["urgency"] = min(100, thread["urgency"] + 3)
            thread["interventionWindow"] = self._window(next_stage, thread["maxStage"], False)
            if signal:
                observed = location in signal.get("locations", [])
                if observed:
                    thread["awareness"] = min(100, thread["awareness"] + signal.get("gain", 0))
                emitted.append({"threadId": thread["id"], "title": thread["title"], "text": signal["text"], "level": "warning" if thread["interventionWindow"] == "CLOSING" else "notice", "observed": observed})
            if next_stage >= thread["maxStage"]:
                self._resolve(world, thread)
        world["recentSignals"] = (world.get("recentSignals", []) + emitted)[-8:]
        return emitted

    def finalize_for_chapter(self, state: dict[str, Any], thread_id: str, *, favorable: bool) -> dict[str, Any]:
        """Close a chapter thread at an authored finale beat without waiting for natural timing."""
        self.normalize(state)
        world = state["worldState"]
        thread = next((item for item in world["activeThreads"] if item["id"] == thread_id), None)
        if not thread:
            raise ValueError("未知的世界线程")
        if not thread.get("resolved"):
            thread["stage"] = thread["maxStage"]
            thread["progress"] = thread["maxStage"]
            thread["selectedOutcome"] = copy.deepcopy(thread["interventionOutcome"] if favorable else thread["naturalOutcome"])
            self._resolve(world, thread)
        return copy.deepcopy(thread.get("resolvedOutcome", {}))

    def _resolve(self, world: dict[str, Any], thread: dict[str, Any]) -> None:
        outcome = thread["selectedOutcome"] or thread["naturalOutcome"]
        thread["resolved"] = True
        thread["interventionWindow"] = "CLOSED"
        thread["resolvedOutcome"] = copy.deepcopy(outcome)
        self._append_unique(world["globalFlags"], outcome.get("flags", []))
        self._append_unique(world["followUpHooks"], outcome.get("followUpHooks", []))
        self._append_unique(world["worldEffects"], thread.get("worldEffects", []))
        world["recentSignals"].append({"threadId": thread["id"], "title": thread["title"], "text": outcome["label"], "level": "resolved"})

    def intervene(self, state: dict[str, Any], thread_id: str, strategy: str) -> dict[str, Any]:
        self.normalize(state)
        thread = next((item for item in state["worldState"]["activeThreads"] if item["id"] == thread_id), None)
        if not thread:
            raise ValueError("未知的世界线程")
        if thread["interventionWindow"] == "CLOSED":
            raise ValueError("主要结果已经不可逆，只能处理后续余波")
        if strategy == "investigate":
            thread["awareness"] = min(100, thread["awareness"] + 25)
            thread["urgency"] = max(0, thread["urgency"] - 5)
            label = "你主动调查了局势，掌握了更多可靠信息。"
        elif strategy == "intervene":
            if thread["awareness"] < 40:
                raise ValueError("你掌握的信息不足，暂时无法有效介入")
            thread["urgency"] = max(0, thread["urgency"] - 18)
            thread["stage"] = max(1, thread["stage"] - 1)
            thread["progress"] = thread["stage"]
            thread["selectedOutcome"] = copy.deepcopy(thread["interventionOutcome"])
            label = "你的介入改变了事情原本的发展方向。"
        else:
            raise ValueError("未知的干预方式")
        thread["playerInterventions"].append({"worldTime": state["time"]["total_actions"], "strategy": strategy})
        thread["lastProgressAt"] = state["time"]["total_actions"]
        thread["interventionWindow"] = self._window(thread["stage"], thread["maxStage"], False)
        return {"threadId": thread_id, "strategy": strategy, "message": label}
