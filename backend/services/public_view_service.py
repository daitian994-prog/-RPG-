from __future__ import annotations

from copy import deepcopy
from typing import Any


class PublicViewService:
    """Project authoritative game data into a player-facing API contract."""

    @staticmethod
    def _known_threads(game: dict[str, Any]) -> list[dict[str, Any]]:
        threads = []
        for thread in game.get("worldState", {}).get("activeThreads", []):
            awareness = thread.get("awareness", 0)
            if awareness < 20 and not thread.get("resolved"):
                continue
            known_signal = next(
                (item.get("text") for item in reversed(thread.get("awarenessSignals", [])) if item.get("stage", 0) <= thread.get("stage", 0)),
                "你只听到一些尚无法确认的说法。",
            )
            status = "模糊传闻" if awareness < 40 else "确认存在" if awareness < 60 else "了解危机" if awareness < 80 else "迫在眉睫"
            resolved = bool(thread.get("resolved"))
            threads.append({
                "id": thread["id"], "title": thread["title"], "resolved": resolved,
                "statusLabel": "已形成世界结果" if resolved else status,
                "knownText": thread.get("resolvedOutcome", {}).get("label", known_signal) if resolved else known_signal,
                "interventionWindow": thread.get("interventionWindow", "OPEN"),
                "canInvestigate": not resolved and thread.get("interventionWindow") != "CLOSED",
                "canIntervene": not resolved and awareness >= 40 and thread.get("interventionWindow") != "CLOSED",
                "worldEffects": thread.get("worldEffects", []) if resolved or thread.get("stage", 0) >= 4 else [],
            })
        return threads

    @staticmethod
    def _player(player: dict[str, Any]) -> dict[str, Any]:
        result = deepcopy(player)
        for key in ("legacyCombatStats", "attributes", "core_attributes", "fate_weights", "injurySeverity", "relations"):
            result.pop(key, None)
        for key in ("inventory", "clues", "traits", "statuses"):
            for item in result.get(key, []):
                item.pop("check_bonuses", None)
                item.pop("modifiers", None)
                item.pop("events", None)
                for internal in ("ability", "bonus", "threadId", "targetTags", "actionTags", "locationTags", "factionTags", "dedupeKey"):
                    item.pop(internal, None)
        result.get("bodyCondition", {}).pop("modifiers", None)
        return result

    def game(self, game: dict[str, Any], *, debug: bool = False) -> dict[str, Any]:
        if debug:
            return game
        result = deepcopy(game)
        result["player"] = self._player(game["player"])
        result["knownWorldThreads"] = self._known_threads(game)
        result["focusedWorldTopics"] = list(game.get("directorState", {}).get("focus", []))
        for key in (
            "worldState", "directorState", "pendingEvent", "chapterFinale", "aiNarratorDebug", "stateChangeLog",
            "check_state_version", "heroActors", "heroActionLog", "heroEncounter",
            "narrativeAuthorityDebug", "scene",
        ):
            result.pop(key, None)
        if result.get("last_resolution"):
            result["last_resolution"] = self.resolution(result["last_resolution"], debug=False)
        return result

    @staticmethod
    def _assessment(value: dict[str, Any]) -> dict[str, Any]:
        result = {
            key: deepcopy(value[key]) for key in (
                "requires_check", "attribute_label", "base_probability", "final_probability",
                "risk", "forecast",
            ) if key in value
        }
        result["applied_modifiers"] = [
            {key: deepcopy(modifier[key]) for key in ("label", "value", "mode") if key in modifier}
            for modifier in value.get("applied_modifiers", [])
        ]
        return result

    def event(self, event: dict[str, Any], *, debug: bool = False) -> dict[str, Any]:
        if debug:
            return event
        allowed = {"id", "type", "title", "text", "boss", "chapter_finale", "finale_stage", "lockChoicesUntilComplete", "streaming", "paragraphs", "round", "sceneActive"}
        result = {key: deepcopy(value) for key, value in event.items() if key in allowed}
        result["choices"] = []
        for choice in event.get("choices", []):
            public_choice = {key: deepcopy(choice[key]) for key in (
                "id", "text", "hint", "requiresCheck", "risk", "requirements", "lethal",
            ) if key in choice}
            public_choice["assessment"] = self._assessment(choice.get("assessment", {}))
            result["choices"].append(public_choice)
        return result

    def resolution(self, resolution: dict[str, Any], *, debug: bool = False) -> dict[str, Any]:
        if debug:
            return resolution
        result = deepcopy(resolution)
        result.pop("stateChangeLog", None)
        result.pop("nextEvent", None)
        result.pop("aiResult", None)
        result.pop("validatorResult", None)
        result.pop("aiResultAttempts", None)
        for bucket in ("changes", "costs"):
            if bucket in result:
                result[bucket] = {key: value for key, value in result[bucket].items() if key in {"personality", "fate", "relations"}}
        result["items"] = [self._player({"inventory": [item]})["inventory"][0] for item in resolution.get("items", [])]
        result["clues"] = [self._player({"clues": [item]})["clues"][0] for item in resolution.get("clues", [])]
        result["statuses"] = [self._player({"statuses": [item]})["statuses"][0] for item in resolution.get("statuses", [])]
        outcome = resolution.get("outcome")
        if outcome:
            safe = self._assessment(outcome)
            for key in ("code", "label", "check", "setback_text"):
                if key in outcome:
                    safe[key] = deepcopy(outcome[key])
            result["outcome"] = safe
        feedback = resolution.get("worldFeedback", {})
        result["worldFeedback"] = {
            "newPlayableSituation": feedback.get("newPlayableSituation"),
            "worldChanged": bool(feedback.get("thread")),
            "heroChanged": bool(feedback.get("hero")),
        }
        return result
