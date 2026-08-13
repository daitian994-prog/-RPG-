from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass, field
from typing import Any


PROBABILITY_CURVE = {-4: 10, -3: 18, -2: 28, -1: 39, 0: 50, 1: 61, 2: 72, 3: 82, 4: 90}
ATTRIBUTE_LABELS = {
    "martial": "武艺", "physique": "体魄", "perception": "灵觉",
    "willpower": "心志", "agility": "机敏", "social": "交涉",
}


@dataclass(frozen=True)
class Modifier:
    source: str
    label: str
    value: int
    mode: str = "percent"

    def as_dict(self) -> dict[str, Any]:
        return {"source": self.source, "label": self.label, "value": self.value, "mode": self.mode}


@dataclass(frozen=True)
class CheckRequest:
    event_id: str
    event_seed: str
    choice_id: str
    attribute: str
    ability: int
    difficulty: int
    player_state_version: str
    modifiers: list[Modifier] = field(default_factory=list)
    automatic: str | None = None


class CheckEngine:
    """The sole authority for probability, seeded rolls and outcome tiers."""

    @staticmethod
    def curve(delta: int) -> int:
        if delta <= -5:
            return 5
        if delta >= 5:
            return 95
        return PROBABILITY_CURVE[delta]

    @staticmethod
    def seed_for(request: CheckRequest) -> str:
        material = f"{request.event_seed}:{request.event_id}:{request.choice_id}:{request.player_state_version}"
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    def preview(self, request: CheckRequest) -> dict[str, Any]:
        ability_delta = sum(item.value for item in request.modifiers if item.mode == "ability")
        percent_delta = sum(item.value for item in request.modifiers if item.mode == "percent")
        effective = request.ability + ability_delta
        base = self.curve(effective - request.difficulty)
        final = 100 if request.automatic == "success" else 0 if request.automatic == "failure" else max(5, min(95, base + percent_delta))
        return {
            "attribute": request.attribute,
            "attribute_label": ATTRIBUTE_LABELS[request.attribute],
            "ability": request.ability,
            "effective_ability": effective,
            "difficulty": request.difficulty,
            "delta": effective - request.difficulty,
            "base_probability": base,
            "final_probability": final,
            "chance": final,
            "applied_modifiers": [item.as_dict() for item in request.modifiers],
            "automatic": request.automatic,
            "seed": self.seed_for(request)[:16],
        }

    def execute(self, request: CheckRequest) -> dict[str, Any]:
        result = self.preview(request)
        roll = random.Random(self.seed_for(request)).randint(1, 100)
        chance = result["final_probability"]
        if request.automatic == "success" or roll <= max(5, chance // 5):
            code, label, multiplier = "critical", "大成功", 1.5
        elif roll <= chance:
            code, label, multiplier = "success", "成功", 1.0
        elif request.automatic != "failure" and roll <= min(100, chance + 25):
            code, label, multiplier = "partial", "部分成功", 0.6
        else:
            code, label, multiplier = "failure", "失败", 0.25
        return {**result, "roll": roll, "tier": code, "code": code, "label": label, "reward_multiplier": multiplier}
