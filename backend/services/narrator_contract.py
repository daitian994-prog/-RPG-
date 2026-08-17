from __future__ import annotations

import json
import re
from typing import Any


class NarratorContract:
    """Validate AI prose without granting the model gameplay authority."""

    ALLOWED_KEYS = {"narrative", "choicePresentation", "npcDialogue", "flavorTags"}
    FORBIDDEN_KEYS = {
        "probability", "successProbability", "roll", "tier", "stage", "threadStage",
        "rewards", "reward", "items", "attributes", "relations", "worldVariables",
        "worldState", "stateChanges", "outcome",
    }

    @staticmethod
    def _decode(raw: str) -> dict[str, Any]:
        text = raw.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
            text = re.sub(r"\s*```$", "", text)
        value = json.loads(text)
        if not isinstance(value, dict):
            raise ValueError("AI输出必须是JSON对象")
        return value

    def validate(self, raw: str) -> dict[str, Any]:
        errors: list[str] = []
        try:
            value = self._decode(raw)
        except (json.JSONDecodeError, ValueError) as exc:
            return {"valid": False, "errors": [str(exc)], "output": None}
        unknown = sorted(set(value) - self.ALLOWED_KEYS)
        forbidden = sorted(set(value) & self.FORBIDDEN_KEYS)
        if unknown:
            errors.append(f"存在未授权字段：{', '.join(unknown)}")
        if forbidden:
            errors.append(f"AI试图写入规则字段：{', '.join(forbidden)}")
        narrative = value.get("narrative")
        if not isinstance(narrative, str) or not narrative.strip():
            errors.append("narrative必须是非空字符串")
        elif re.search(r"收进(?:怀里|行囊)|收入行囊|带回(?:村|住处)|获得了|得到(?:了|一)|交给你|递给你|塞给你", narrative):
            errors.append("叙事声称获得了程序未确认的物品或线索")
        for key in ("choicePresentation", "npcDialogue", "flavorTags"):
            if key in value and not isinstance(value[key], list):
                errors.append(f"{key}必须是数组")
        normalized = {
            "narrative": narrative.strip() if isinstance(narrative, str) else "",
            "choicePresentation": value.get("choicePresentation", []),
            "npcDialogue": value.get("npcDialogue", []),
            "flavorTags": value.get("flavorTags", []),
        }
        return {"valid": not errors, "errors": errors, "output": normalized if not errors else None}
