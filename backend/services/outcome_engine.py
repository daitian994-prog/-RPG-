from __future__ import annotations

import copy
import json
import re
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

    @staticmethod
    def validate_ai_result(
        proposal: dict[str, Any] | None,
        scene: dict[str, Any],
        outcome: dict[str, Any],
        choice: dict[str, Any],
        director: dict[str, Any],
        state: dict[str, Any],
    ) -> tuple[dict[str, Any] | None, dict[str, Any]]:
        """Validate only the hard boundaries needed before local AI facts become scene facts."""
        errors: list[str] = []
        if not isinstance(proposal, dict):
            return None, {"valid": False, "errors": ["AIResult不是对象"]}
        required = ("narrative", "factsAdded", "questionsAdded", "questionsResolved", "npcReactions", "sceneDecision")
        missing = [key for key in required if key not in proposal]
        if missing:
            errors.append("缺少字段：" + "、".join(missing))
        for key in ("factsAdded", "questionsAdded", "questionsResolved", "npcReactions", "actorsAdded", "objectsAdded"):
            if key in proposal and not isinstance(proposal[key], list):
                errors.append(f"{key}必须是数组")
        if not isinstance(proposal.get("narrative"), str) or len(proposal.get("narrative", "").strip()) < 40:
            errors.append("narrative过短，未说明具体发生了什么")
        decision = proposal.get("sceneDecision")
        if not isinstance(decision, dict):
            errors.append("sceneDecision必须是对象")
        else:
            if not isinstance(decision.get("continueScene"), bool):
                errors.append("sceneDecision.continueScene必须是布尔值")
            if not isinstance(decision.get("reason"), str) or not decision.get("reason", "").strip():
                errors.append("sceneDecision.reason不能为空")
            if decision.get("continueScene") and not str(decision.get("nextFocus", "")).strip():
                errors.append("Scene继续时必须给出nextFocus")
        if errors:
            return None, {"valid": False, "errors": errors}

        result = copy.deepcopy(proposal)
        for key in ("factsAdded", "questionsAdded", "questionsResolved", "npcReactions", "actorsAdded", "objectsAdded"):
            result.setdefault(key, [])
            result[key] = list(dict.fromkeys(str(item).strip() for item in result[key] if str(item).strip()))[:8]
        result["narrative"] = result["narrative"].strip()
        result["sceneDecision"] = {
            "continueScene": bool(result["sceneDecision"]["continueScene"]),
            "reason": str(result["sceneDecision"]["reason"]).strip(),
            "nextFocus": str(result["sceneDecision"].get("nextFocus", "")).strip(),
        }
        result["continueScene"] = result["sceneDecision"]["continueScene"]
        result["leadDisposition"] = str(result.get("leadDisposition", "KEEP_ACTIVE")).upper()
        result["leadResolutionSummary"] = str(result.get("leadResolutionSummary", "")).strip()[:240]
        current_questions = set(scene.get("questions", []))
        invalid_resolved = [item for item in result["questionsResolved"] if item not in current_questions]
        if invalid_resolved:
            result["questionsResolved"] = [item for item in result["questionsResolved"] if item in current_questions]
        remaining_questions = (current_questions - set(result["questionsResolved"])) | set(result["questionsAdded"])
        if result["sceneDecision"]["continueScene"] and not remaining_questions:
            result["sceneDecision"] = {
                "continueScene": False,
                "reason": "程序复验发现没有尚待立即处理的问题，当前Scene自然收束。",
                "nextFocus": "",
            }
            result["continueScene"] = False

        tier = outcome["code"]
        progress = bool(result["factsAdded"] or result["questionsResolved"])
        leaving = any(term in str(choice.get("semanticAction", choice.get("text", ""))) for term in ("离开", "撤离", "不介入", "保持距离"))
        if tier in {"critical", "success"} and not progress and not leaving:
            errors.append("成功结果没有产生具体事实或解决现场问题")
        if tier == "partial" and (not progress or not (result["questionsAdded"] or result["npcReactions"])):
            errors.append("部分成功必须同时包含具体进展与代价或新风险")
        if tier == "failure" and current_questions and current_questions.issubset(result["questionsResolved"]):
            errors.append("失败结果不能解决全部核心问题")

        serialized = json.dumps(result, ensure_ascii=False)
        scene_context = json.dumps({
            "actors": scene.get("actors", []), "objects": scene.get("objects", []),
            "facts": scene.get("facts", []), "questions": scene.get("questions", []),
            "action": choice.get("semanticAction", choice.get("text", "")),
        }, ensure_ascii=False)
        unrelated_expansions = ("新组织", "陌生组织", "神器", "世界毁灭", "世界危机", "远古魔王")
        if any(term in serialized and term not in scene_context for term in unrelated_expansions):
            errors.append("AIResult为延长Scene引入了与当前现场无关的新扩展")
        if result.get("actorsAdded") and not any(
            term in f"{scene_context}{serialized}" for term in ("接近", "来者", "脚步", "人影", "呼喊", "在场")
        ):
            result["actorsAdded"] = []
        if re.search(r"(?:线程|Thread).{0,8}(?:阶段|Stage).{0,8}(?:推进|提升|变为|改为)", serialized, re.I):
            errors.append("AIResult试图修改Thread Stage")
        if re.search(r"(?:关系|能力|生命|伤势|紧迫度|认知度).{0,8}[+＋\-－]\s*\d+", serialized):
            errors.append("AIResult试图修改程序数值")
        protected = ("亚索", "慎", "阿卡丽", "劫", "易", "艾瑞莉娅", "艾翁", "韦鲁斯")
        if any(re.search(fr"{name}.{{0,6}}(?:死亡|死去|被杀|永久残废)", serialized) for name in protected):
            errors.append("AIResult试图杀死或永久伤害受保护角色")
        allowed_actors = " ".join(str(item) for item in scene.get("actors", []))
        for name in protected:
            if name in serialized and name not in allowed_actors:
                errors.append(f"不在现场的英雄{name}突然出现")
                break
        authorized_items = set(choice.get("result", {}).get("items", []))
        for item in state.get("player", {}).get("inventory", []):
            name = item.get("name", "")
            if name and name not in authorized_items and re.search(fr"(?:获得|捡起|收起|带走).{{0,4}}{re.escape(name)}", serialized):
                errors.append("AIResult试图擅自改变物品归属")
                break

        normalized_existing = {re.sub(r"[\s，。！？、]", "", item) for item in scene.get("facts", [])}
        for fact in result["factsAdded"]:
            normalized = re.sub(r"[\s，。！？、]", "", fact)
            opposite = normalized.removeprefix("没有").removeprefix("不是")
            if normalized.startswith(("没有", "不是")) and any(opposite and opposite in existing for existing in normalized_existing):
                errors.append("AIResult与既有Scene Facts直接冲突")
                break

        clue = result.get("suggestedClue")
        if clue is not None:
            if not isinstance(clue, dict) or not str(clue.get("name", "")).strip():
                result["suggestedClue"] = None
            else:
                clue["bonus"] = max(1, min(10, int(clue.get("bonus", 5))))
                if clue.get("ability") not in {"martial", "physique", "perception", "willpower", "agility", "social", None}:
                    clue["ability"] = choice.get("attribute")
                clue["targetTags"] = list(dict.fromkeys(str(item).strip() for item in clue.get("targetTags", []) if str(item).strip()))[:8]
                clue["actionTags"] = list(dict.fromkeys(str(item).strip() for item in clue.get("actionTags", []) if str(item).strip()))[:8]
                clue["threadId"] = director.get("threadId")
                clue["locationTags"] = [state.get("location")] if state.get("location") else []
        lead = result.get("suggestedLead")
        if lead is not None:
            if not isinstance(lead, dict) or not str(lead.get("title", "")).strip() or not str(lead.get("summary", "")).strip():
                result["suggestedLead"] = None
                lead = None
            else:
                allowed_locations = {"pallas", "windbreak", "war_ruins", "mountain_temple"}
                locations = list(dict.fromkeys(str(item) for item in lead.get("relatedLocations", []) if str(item) in allowed_locations))
                active_threads = {item.get("id") for item in state.get("worldState", {}).get("activeThreads", [])}
                intent = state.get("playerIntent", {})
                related_thread = lead.get("threadId") or director.get("threadId") or intent.get("threadId")
                if not locations:
                    result["suggestedLead"] = None
                    lead = None
                elif related_thread not in active_threads:
                    result["suggestedLead"] = None
                    lead = None
                elif related_thread not in {director.get("threadId"), intent.get("threadId")}:
                    result["suggestedLead"] = None
                    lead = None
                else:
                    lead["title"] = str(lead["title"]).strip()[:80]
                    lead["summary"] = str(lead["summary"]).strip()[:240]
                    lead["relatedLocations"] = locations
                    lead["threadId"] = related_thread
        disposition = result["leadDisposition"]
        if disposition not in {"KEEP_ACTIVE", "RESOLVED", "SUPERSEDED"}:
            result["leadDisposition"] = "KEEP_ACTIVE"
            disposition = "KEEP_ACTIVE"
        if disposition != "KEEP_ACTIVE":
            intent = state.get("playerIntent", {})
            current_lead = next((item for item in state.get("journal", []) if item.get("id") == intent.get("leadId") and item.get("trackable") and item.get("status") == "active"), None)
            if intent.get("kind") != "track_lead" or current_lead is None:
                errors.append("没有可由本Scene关闭的active Lead")
            elif result["sceneDecision"]["continueScene"]:
                errors.append("Scene尚未结束，不能关闭当前Lead")
            elif not (result["factsAdded"] or result["questionsResolved"]):
                errors.append("关闭当前Lead缺少已确认事实或已回答问题")
            elif disposition == "SUPERSEDED":
                if lead is None:
                    errors.append("SUPERSEDED必须提供接替当前目标的新Lead")
                elif str(lead.get("title", "")).strip() == str(current_lead.get("title", "")).strip():
                    errors.append("SUPERSEDED的新Lead不能只是重复当前目标")
        if errors:
            return None, {"valid": False, "errors": errors}
        return result, {"valid": True, "errors": []}

    @staticmethod
    def update_scene_state(
        scene: dict[str, Any], result: dict[str, Any], choice: dict[str, Any], outcome: dict[str, Any],
        validator: dict[str, Any], *, player_disabled: bool = False,
    ) -> bool:
        """Apply AIResult, expire old actions, and honor the per-round natural SceneDecision."""
        facts_before = list(scene.setdefault("facts", []))
        questions_before = list(scene.setdefault("questions", []))
        focus_before = str(scene.get("currentFocus", ""))
        previous_actions = scene.setdefault("previousActions", [])
        scene["actions"] = []
        for fact in result["factsAdded"]:
            if fact not in scene["facts"]:
                scene["facts"].append(fact)
        resolved = set(result["questionsResolved"])
        scene["questions"] = [item for item in scene.setdefault("questions", []) if item not in resolved]
        for question in result["questionsAdded"]:
            if question not in scene["questions"]:
                scene["questions"].append(question)
        for actor in result.get("actorsAdded", []):
            if actor not in scene.setdefault("actors", []):
                scene["actors"].append(actor)
        for obj in result.get("objectsAdded", []):
            if obj not in scene.setdefault("objects", []):
                scene["objects"].append(obj)
        current_round = int(scene.get("round", 1))
        scene["lastAction"] = {
            "round": current_round, "id": choice.get("id"), "text": choice.get("semanticAction", choice.get("text")),
            "goal": choice.get("goal"), "actionTags": choice.get("actionTags", []), "targetTags": choice.get("targetTags", []),
        }
        scene["lastResult"] = {
            "round": current_round,
            "checkResult": {key: outcome.get(key) for key in ("code", "label", "roll", "final_probability", "attribute_label")},
            "aiResult": copy.deepcopy(result),
            "validatorResult": copy.deepcopy(validator),
        }
        previous_semantics = [re.sub(r"[，。！？、：；\s]|继续|再次|重新", "", str(item.get("text", ""))) for item in previous_actions]
        current_semantic = re.sub(r"[，。！？、：；\s]|继续|再次|重新", "", str(scene["lastAction"]["text"]))
        repeated_action = any(
            old and current_semantic and (old == current_semantic or old in current_semantic or current_semantic in old)
            for old in previous_semantics
        )
        previous_actions.append(copy.deepcopy(scene["lastAction"]))
        scene["previousActions"] = previous_actions[-12:]

        decision = copy.deepcopy(result["sceneDecision"])
        scene["currentFocus"] = decision.get("nextFocus", "") if decision["continueScene"] else ""
        normalized_before_focus = re.sub(r"[，。！？、：；\s]", "", focus_before)
        normalized_after_focus = re.sub(r"[，。！？、：；\s]", "", scene["currentFocus"])
        focus_same = bool(normalized_before_focus and normalized_before_focus == normalized_after_focus)
        no_fact_progress = scene["facts"] == facts_before
        questions_same = scene["questions"] == questions_before
        stagnant = focus_same and no_fact_progress and questions_same and repeated_action
        loop_guard = scene.setdefault("loopGuard", {"stagnantRounds": 0, "forcedClosure": False})
        loop_guard["stagnantRounds"] = int(loop_guard.get("stagnantRounds", 0)) + 1 if stagnant else 0
        loop_guard["forcedClosure"] = loop_guard["stagnantRounds"] >= 2

        leaving = any(term in str(scene["lastAction"]["text"]) for term in ("离开", "撤离", "不介入", "保持距离"))
        main_resolved = not scene["questions"]
        at_limit = current_round >= int(scene.get("maxRounds", 4))
        if loop_guard["forcedClosure"]:
            decision = {
                "continueScene": False,
                "reason": "连续两轮没有新增事实、问题或焦点变化，且行动语义重复；防循环保护要求依据现有事实收束。",
                "nextFocus": "",
            }
            scene["currentFocus"] = ""
        elif at_limit and decision["continueScene"]:
            decision = {
                "continueScene": False,
                "reason": "达到普通Scene最大安全轮数，依据已有事实强制收束。",
                "nextFocus": "",
            }
            scene["currentFocus"] = ""
        ended = leaving or player_disabled or main_resolved or at_limit or loop_guard["forcedClosure"] or not decision["continueScene"]
        scene["sceneDecision"] = decision
        scene["lastResult"]["sceneDecision"] = copy.deepcopy(decision)
        scene["ended"] = ended
        scene["continueScene"] = not ended
        if not ended:
            scene["round"] = current_round + 1
        return ended

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
