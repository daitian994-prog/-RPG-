from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


DATA_DIR = Path(__file__).resolve().parents[2] / "game-data"
ABILITY_KEYS = ("martial", "physique", "perception", "willpower", "agility", "social")
ABILITY_LABELS = {"martial": "武艺", "physique": "体魄", "perception": "灵觉", "willpower": "心志", "agility": "机敏", "social": "交涉"}
THREAD_RELEVANCE = {
    "noxian_remnants": {"pallas": "medium", "windbreak": "high", "war_ruins": "low", "mountain_temple": "medium"},
    "spirit_anomaly": {"pallas": "low", "windbreak": "high", "war_ruins": "medium", "mountain_temple": "high"},
}
THREAD_INTENTS = ("rumor", "rumor", "clue", "investigation", "encounter", "conflict", "aftermath")


class DynamicEventService:
    """Compose deterministic event mechanics from independent world components."""

    def __init__(self) -> None:
        self.config = json.loads((DATA_DIR / "dynamic_event_components.json").read_text(encoding="utf-8"))

    @staticmethod
    def _seed(state: dict[str, Any], location_id: str) -> str:
        material = {
            "game": state.get("id", "simulation"), "location": location_id,
            "worldTime": state.get("worldState", {}).get("worldTime", state.get("time", {}).get("total_actions", 0)),
            "threads": [(item["id"], item["stage"], item["urgency"], item["awareness"], item["resolved"]) for item in state.get("worldState", {}).get("activeThreads", [])],
            "condition": state.get("player", {}).get("bodyCondition", {}).get("state", "healthy"),
            "abilities": state.get("player", {}).get("coreAbilities", {}),
            "focus": state.get("directorState", {}).get("focus", []),
        }
        return hashlib.sha256(json.dumps(material, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()

    @staticmethod
    def _pick(values: list[Any], seed: str, salt: str) -> Any:
        digest = hashlib.sha256(f"{seed}:{salt}".encode()).hexdigest()
        return values[int(digest[:12], 16) % len(values)]

    @staticmethod
    def _action_catalog(setting: str, actor: str, subject: str, intent: str) -> list[dict[str, Any]]:
        """Describe meaningful actions first. Ability mapping happens only afterwards."""
        actions = [
            {"id": "trace", "semanticAction": f"检查{subject}与周围痕迹的联系", "goal": "弄清异常来源", "approach": "仔细辨认现场留下的细节", "ability": "perception", "risk": "中", "outcome": "information", "trait": "spirit", "duplicateGroup": "investigate", "text": f"先检查{subject}周围的痕迹，判断它为何出现在这里", "hint": "可能查明真相，但靠近异常也会暴露自己"},
            {"id": "question", "semanticAction": f"向{actor}核对{subject}的来历", "goal": "取得可信说法", "approach": "让在场者交叉印证", "ability": "social", "risk": "低", "outcome": "relationship", "trait": "peace", "duplicateGroup": "communicate", "text": f"留下来询问{actor}，核对{subject}的来历", "hint": "可能得到帮助，也可能让对方提高戒心"},
            {"id": "contain", "semanticAction": f"阻止{subject}继续威胁现场", "goal": "立刻控制危险", "approach": "正面夺回局势主动", "ability": "martial", "risk": "高", "outcome": "safety", "trait": "power", "duplicateGroup": "confront", "text": f"抽出武器，挡在众人与{subject}之间", "hint": "最快压住危险，但你会成为首要目标"},
            {"id": "carry", "semanticAction": f"把{subject}移到安全处", "goal": "保护附近的人", "approach": "承受最重的一环", "ability": "physique", "risk": "高", "outcome": "safety", "trait": "peace", "duplicateGroup": "protect", "text": f"顶住风险，把{subject}移到不会伤人的地方", "hint": "能保护旁人，但可能留下劳损"},
            {"id": "flank", "semanticAction": f"借{setting}的遮蔽绕到侧面", "goal": "从安全角度接近目标", "approach": "利用地形避开正面危险", "ability": "agility", "risk": "中", "outcome": "position", "trait": "freedom", "duplicateGroup": "maneuver", "text": f"借{setting}的遮蔽绕到侧面，再靠近{subject}", "hint": "避免硬碰，但错过时机会被截断退路"},
            {"id": "attune", "semanticAction": f"感受{subject}传来的异样", "goal": "辨别灵性影响", "approach": "稳住意识并回应异变", "ability": "willpower", "risk": "中", "outcome": "spiritual", "trait": "destiny", "duplicateGroup": "attune", "text": f"稳住呼吸，直接感受{subject}传来的异样", "hint": "可能理解异变，也可能受到它的影响"},
            {"id": "record", "semanticAction": f"记下{subject}的细节而不介入", "goal": "保存线索", "approach": "保持距离并记录", "requiresCheck": False, "risk": "低", "outcome": "information", "trait": "destiny", "duplicateGroup": "observe", "text": f"把{subject}的细节记下来，暂时不惊动{actor}", "hint": "不会立即涉险，但现场机会可能就此过去"},
            {"id": "leave", "semanticAction": "记住地点并离开现场", "goal": "避免当前风险", "approach": "主动放弃眼前机会", "requiresCheck": False, "risk": "低", "outcome": "withdrawal", "trait": "freedom", "duplicateGroup": "withdraw", "text": "记住这里的位置，暂时离开现场", "hint": "能够安全离开，但无法得到眼前的答案"},
        ]
        preferred = {
            "environmental": ["trace", "attune", "record", "leave", "carry", "contain"],
            "rumor": ["question", "record", "trace", "leave"],
            "clue": ["trace", "record", "question", "flank"],
            "investigation": ["trace", "flank", "question", "record", "attune"],
            "encounter": ["flank", "contain", "carry", "question", "leave"],
            "conflict": ["contain", "carry", "flank", "question", "leave"],
            "aftermath": ["trace", "attune", "record", "question"],
            "npc_report": ["question", "trace", "record", "leave", "carry"],
            "opportunity": ["trace", "flank", "question", "record", "carry", "contain"],
            "personal": ["attune", "trace", "record", "leave", "flank"],
            "hero_overlap": ["question", "trace", "flank", "leave"],
        }.get(intent, ["trace", "question", "record"])
        by_id = {action["id"]: action for action in actions}
        return [by_id[action_id] for action_id in preferred]

    def _choices(self, state: dict[str, Any], seed: str, slot: int, difficulty: int, setting: str, actor: str, subject: str, intent: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        candidates = self._action_catalog(setting, actor, subject, intent)
        player = state.get("player", {})
        if player.get("clues"):
            clue = player["clues"][0]
            candidates.insert(0, {"id": "use-clue", "semanticAction": f"用已有线索“{clue['name']}”核对现场", "goal": "验证已知信息", "approach": "以线索缩小判断范围", "ability": "perception", "risk": "低", "outcome": "information", "trait": "spirit", "duplicateGroup": "clue", "requirement": {"kind": "clue", "id": clue.get("id"), "name": clue["name"]}, "text": f"用“{clue['name']}”核对{subject}的细节", "hint": "已有线索会让判断更有根据"})
        if player.get("traits"):
            trait = player["traits"][0]
            candidates.insert(1, {"id": "use-trait", "semanticAction": f"凭借“{trait['name']}”稳定现场", "goal": "为他人争取时间", "approach": "发挥已经形成的个人特质", "ability": "willpower", "risk": "中", "outcome": "safety", "trait": "peace", "duplicateGroup": "trait", "requirement": {"kind": "trait", "id": trait["id"], "name": trait["name"]}, "text": f"凭借“{trait['name']}”稳住局面，再处理{subject}", "hint": "你的经历让这条行动成为可能"})

        rejected: list[dict[str, str]] = []
        valid: list[dict[str, Any]] = []
        groups: set[str] = set()
        for action in candidates:
            reason = None
            if not action.get("semanticAction") or not action.get("goal") or not action.get("approach"):
                reason = "缺少行动语义"
            elif action.get("requiresCheck", True) and action.get("ability") not in ABILITY_KEYS:
                reason = "无法映射核心能力"
            elif action["duplicateGroup"] in groups:
                reason = "与已接受行动策略重复"
            if reason:
                rejected.append({"id": action.get("id", "unknown"), "reason": reason})
                continue
            groups.add(action["duplicateGroup"])
            valid.append(action)

        count = 2 + int(hashlib.sha256(f"{seed}:choice-count:{slot}".encode()).hexdigest()[:8], 16) % 3
        ordered = sorted(valid, key=lambda item: hashlib.sha256(f"{seed}:action-order:{slot}:{item['id']}".encode()).hexdigest())
        selected = ordered[:count]
        if selected and all(item.get("requiresCheck", True) is False for item in selected):
            checked = next(item for item in ordered[count:] if item.get("requiresCheck", True))
            selected[-1] = checked
        selected_abilities = {item.get("ability") for item in selected if item.get("ability")}
        if len(selected_abilities) < min(2, count):
            replacement = next((item for item in ordered if item not in selected and item.get("ability") not in selected_abilities and item.get("requiresCheck", True)), None)
            if replacement:
                replace_at = next((index for index in range(len(selected) - 1, -1, -1) if not selected[index].get("ability")), -1)
                if replace_at < 0:
                    replace_at = next((index for index in range(len(selected) - 1, -1, -1) if sum(item.get("ability") == selected[index].get("ability") for item in selected) > 1), len(selected) - 1)
                selected[replace_at] = replacement
        if intent in {"encounter", "conflict"}:
            selected.sort(key=lambda item: item.get("requiresCheck", True) is False)
        choices: list[dict[str, Any]] = []
        mapping: list[dict[str, str]] = []
        for index, action in enumerate(selected):
            requires_check = action.get("requiresCheck", True)
            ability = action.get("ability") if requires_check else None
            result: dict[str, Any] = {"text": f"{action['semanticAction']}。你的决定让局势沿着“{action['goal']}”的方向发展。", "personality": {action["trait"]: 3 if requires_check else 1}}
            if action["outcome"] == "information":
                result["clues"] = [{"name": f"关于{subject}的可靠线索", "source": "现场发现", "modifiers": {"perception": 5}, "events": []}]
            if action["id"] == "carry":
                result["statuses"] = [{"id": "dynamic_strain", "name": "劳损", "source": subject, "duration": 1, "modifiers": {"physique": -5}, "on": "partial"}]
            choice = {
                "id": f"{action['id']}-{index}", "semanticAction": action["semanticAction"], "goal": action["goal"],
                "approach": action["approach"], "requiresCheck": requires_check, "risk": action["risk"],
                "possibleOutcomeClass": action["outcome"], "requirements": [action["requirement"]] if action.get("requirement") else [],
                "text": action["text"], "hint": action["hint"], "result": result,
            }
            if requires_check:
                choice.update({"attribute": ability, "requiredAbility": ability, "difficulty": max(5, min(12, difficulty + index - 1))})
                mapping.append({"candidate": action["id"], "ability": ability, "abilityLabel": ABILITY_LABELS[ability], "reason": action["approach"]})
            choices.append(choice)
        return choices, {"candidates": candidates, "accepted": [item["id"] for item in selected], "rejected": rejected, "abilityMapping": mapping, "duplicateGroups": sorted(groups)}

    def _compose(
        self, state: dict[str, Any], location_id: str, seed: str, slot: int, *, category: str,
        intent: str, thread: dict[str, Any] | None = None, hero: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        loc = self.config["locations"][location_id]
        setting = self._pick(loc["settings"], seed, f"setting:{slot}")
        actor = hero["name"] if hero else self._pick(loc["actors"], seed, f"actor:{slot}")
        obj = self._pick(loc["objects"], seed, f"object:{slot}")
        pressure = self._pick(loc["pressures"], seed, f"pressure:{slot}")
        profile = self.config["intents"][intent]
        title_pattern = self._pick(profile["titles"], seed, f"title:{slot}")
        title = title_pattern.format(object=obj, setting=setting, actor=actor)
        stage_fact = thread["stages"][thread["stage"]] if thread else None
        thread_line = f"这并非孤立事故，近期关于{thread['title']}的迹象也指向这里。" if thread else "附近人的争论与不断逼近的异样表明，这件事已经无法再被当作寻常插曲。"
        hero_line = f"{actor}没有表明完整身份，只在现场短暂停步，很快还会继续自己的路。" if hero else ""
        text = f"{setting}，{actor}正在查看{obj}。{pressure}。{thread_line}{hero_line}"
        intensity = "climax" if thread and not thread.get("resolved") and thread["stage"] >= thread["maxStage"] - 1 else profile["intensity"]
        difficulty = 6 if intensity == "low" else 8 if intensity == "medium" else 10 if intensity == "high" else 11
        composition = f"{location_id}|{category}|{intent}|{setting}|{actor}|{obj}|{pressure}|{stage_fact or '-'}"
        event_id = "dyn-" + hashlib.sha256(f"{seed}:{slot}:{composition}".encode()).hexdigest()[:16]
        choices, action_debug = self._choices(state, seed, slot, difficulty, setting, actor, obj, intent)
        return {
            "id": event_id, "type": profile["type"], "locations": [location_id], "title": title, "text": text,
            "choices": choices,
            "dynamic": True, "compositionKey": hashlib.sha256(composition.encode()).hexdigest()[:12],
            "components": {"setting": setting, "actor": actor, "object": obj, "pressure": pressure, "stageFact": stage_fact},
            "actionDebug": action_debug,
            "directorProfile": {
                "category": category, "intents": [intent], "intensity": intensity,
                "baseWeight": 0.58 if category == "hero" else 0.82 if category == "world_thread" else 1.0,
                "threadId": thread["id"] if thread else None,
                "heroId": hero["id"] if hero else None, "heroName": hero["name"] if hero else None,
                "locationRelevance": THREAD_RELEVANCE.get(thread["id"], {}).get(location_id, "high") if thread else "high",
            },
        }

    def generate_pool(self, state: dict[str, Any], location_id: str) -> list[dict[str, Any]]:
        if location_id not in self.config["locations"]:
            raise ValueError("这个地点尚未配置动态事件组件")
        seed = self._seed(state, location_id)
        tension = state.get("directorState", {}).get("tension", 22)
        ambient_intents = ["environmental", "rumor", "clue", "opportunity", "personal", "npc_report"]
        if tension >= 55:
            ambient_intents.extend(["investigation", "encounter", "conflict"])
        pool = []
        for slot in range(9):
            intent = "conflict" if tension >= 55 and slot == 8 else self._pick(ambient_intents, seed, f"intent:{slot}")
            category = "personal" if intent == "personal" or (slot % 5 == 3) else "environment"
            pool.append(self._compose(state, location_id, seed, slot, category=category, intent=intent))
        slot = 20
        for thread in state.get("worldState", {}).get("activeThreads", []):
            relevance = THREAD_RELEVANCE.get(thread["id"], {}).get(location_id, "none")
            if relevance == "none":
                continue
            intent = "aftermath" if thread.get("resolved") else THREAD_INTENTS[min(thread["stage"], len(THREAD_INTENTS) - 1)]
            pool.append(self._compose(state, location_id, seed, slot, category="world_thread", intent=intent, thread=thread))
            slot += 1
        # Stage 5 V1: only the persistent Yasuo actor may create a full hero candidate.
        # Other canon champions remain knowledge-base records and are never sampled here.
        yasuo = state.get("heroActors", {}).get("yasuo", {})
        encounter = state.get("heroEncounter", {})
        if (
            yasuo.get("currentRegion") == "ionia_east"
            and yasuo.get("currentLocation") == location_id
            and yasuo.get("availability") == "available"
            and encounter.get("level", 0) >= 3
        ):
            pool.append(self._compose(state, location_id, seed, 30, category="hero", intent="hero_overlap", hero={"id": "yasuo", "name": "亚索"}))
        return pool
