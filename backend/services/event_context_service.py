from __future__ import annotations

import json
from pathlib import Path
from typing import Any


DATA_DIR = Path(__file__).resolve().parents[2] / "game-data"


class EventContextService:
    """Build the single structured hand-off shared by selector, UI and narrator."""

    def __init__(self) -> None:
        champions = json.loads((DATA_DIR / "lore" / "champions.json").read_text(encoding="utf-8"))
        self.champions = {item["id"]: item for item in champions}

    @staticmethod
    def _thread_summary(thread: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": thread["id"], "title": thread["title"], "stage": thread["stage"],
            "stageFact": thread["stages"][thread["stage"]], "urgency": thread["urgency"],
            "awareness": thread["awareness"], "interventionWindow": thread["interventionWindow"],
            "resolved": thread["resolved"],
        }

    def build(self, state: dict[str, Any], location: dict[str, Any], selection: dict[str, Any], template: dict[str, Any]) -> dict[str, Any]:
        player = state["player"]
        active = [self._thread_summary(item) for item in state.get("worldState", {}).get("activeThreads", [])]
        candidate = {
            key: selection.get(key) for key in (
                "candidateId", "templateId", "eventId", "category", "threadId", "intent",
                "intensity", "heroId", "heroName", "threadStage", "threadStageLabel",
                "worldEffects", "followUpHooks", "seed", "compositionKey", "dynamicComponents",
            ) if selection.get(key) is not None
        }
        hero = None
        hero_id = selection.get("heroId")
        if hero_id and hero_id in self.champions:
            profile = self.champions[hero_id]
            relation = state.get("heroRelationships", {}).get(hero_id, {"score": 0, "stage": "stranger", "history": []})
            hero = {
                "id": hero_id, "name": profile["name"], "title": profile.get("title"),
                "personality": profile.get("personality", []), "currentGoal": profile.get("motivation"),
                "currentStatus": profile.get("status"), "relationship": relation,
            }
        hard_facts = [
            f"地点固定为{location['name']}", f"时间固定为{state.get('season', '未知')}",
            f"事件类型固定为{template['type']}", f"事件意图固定为{selection.get('intent', 'environmental')}",
        ]
        if selection.get("threadId"):
            hard_facts.append(f"世界线程阶段固定为{selection.get('threadStage')}：{selection.get('threadStageLabel')}")
        if hero:
            hard_facts.append(f"本次允许登场英雄仅限{hero['name']}，其目标固定为：{hero['currentGoal']}")
        return {
            "location": {"id": location["id"], "name": location["name"]},
            "time": state.get("time", {}),
            "playerSummary": {
                "name": player["name"], "coreAbilities": player.get("coreAbilities", {}),
                "bodyCondition": player.get("bodyCondition", {}), "personality": player.get("personality", {}),
            },
            "statuses": player.get("statuses", []), "traits": player.get("traits", []),
            "clues": player.get("clues", []), "activeThreadsSummary": active,
            "directorIntent": {
                "category": selection.get("category"), "intent": selection.get("intent"),
                "intensity": selection.get("intensity"), "localConstraint": selection.get("directorContext", ""),
            },
            "selectedCandidate": candidate, "eventIntent": selection.get("intent"), "heroContext": hero,
            "hardFacts": hard_facts,
            "forbiddenChanges": [
                "不得修改成功率、检定值、随机数或结果档位", "不得新增、删除或改写程序选项",
                "不得改变WorldThread阶段、紧迫度或结局", "不得决定奖励、物品、关系数值、伤势或状态",
                "不得创造未被selectedCandidate允许的英雄登场", "不得替玩家作出选择",
            ],
        }
