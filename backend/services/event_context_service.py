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

    def build(
        self, state: dict[str, Any], location: dict[str, Any], selection: dict[str, Any], template: dict[str, Any],
        *, hero_context: dict[str, Any] | None = None, hero_encounter: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        player = state["player"]
        active = [self._thread_summary(item) for item in state.get("worldState", {}).get("activeThreads", [])]
        candidate = {
            key: selection.get(key) for key in (
                "candidateId", "templateId", "eventId", "category", "threadId", "intent",
                "intensity", "heroId", "heroName", "threadStage", "threadStageLabel",
                "worldEffects", "followUpHooks", "seed", "compositionKey", "dynamicComponents",
            ) if selection.get(key) is not None
        }
        hero = hero_context
        hero_id = selection.get("heroId")
        if hero is None and hero_id and hero_id in self.champions:
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
            hero_name = hero.get("name") or hero.get("canon", {}).get("name", "亚索")
            hero_goal = hero.get("currentGoal") or hero.get("runtime", {}).get("currentGoal", {}).get("summary")
            hard_facts.append(f"本次允许涉及的原生英雄仅限{hero_name}，其当前目标固定为：{hero_goal}")
        required_elements: list[str] = []
        encounter = hero_encounter or {"level": 0, "levelName": "none"}
        if encounter.get("level") == 1 and encounter.get("trace"):
            required_elements.append("现场必须自然出现这条英雄活动痕迹：" + encounter["trace"])
        elif encounter.get("level") == 2 and encounter.get("rumor"):
            required_elements.append("普通NPC必须自然提及这条传闻：" + encounter["rumor"])
        elif encounter.get("level") == 3:
            required_elements.append("玩家只能远远看见亚索，不发生直接交流")
        elif encounter.get("level") == 4:
            required_elements.append("亚索可以与玩家进行克制的直接交流，但不会倾吐所有秘密")
        elif encounter.get("level") == 5:
            required_elements.append("亚索可与玩家共同处理局部问题，但不能替玩家完成关键决定")
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
            "heroEncounter": encounter,
            "hardFacts": hard_facts,
            "requiredElements": required_elements,
            "forbiddenChanges": [
                "不得修改成功率、检定值、随机数或结果档位",
                "不得改变WorldThread阶段、紧迫度或结局", "不得决定奖励、物品、关系数值、伤势或状态",
                "不得创造叙事边界未允许的英雄登场", "不得替玩家作出选择",
                "不得令亚索死亡、永久残废、改变阵营或被普通杂兵轻易击败",
            ],
            "creativeFreedom": [
                "创造具体场景、普通NPC、局部物件与现场问题", "提出2到5条语义不同的合理行动",
                "决定普通NPC的现场行为和对白", "在不改变规则结果的前提下表现气氛与节奏",
            ],
            "programAuthority": [
                "世界时间与WorldThread", "Director选择与张力", "能力映射与是否检定",
                "Difficulty、Seed、Roll与Tier", "奖励、伤势、关系数值、物品归属与英雄Runtime写回",
            ],
        }
