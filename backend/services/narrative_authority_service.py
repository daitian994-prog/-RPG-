from __future__ import annotations

import copy
import json
import os
import re
from typing import Any

from backend.services.deepseek_service import DeepSeekError, DeepSeekService


ABILITY_LABELS = {"martial": "武艺", "physique": "体魄", "perception": "灵觉", "willpower": "心志", "agility": "机敏", "social": "交涉"}
TRAIT_BY_ABILITY = {"martial": "power", "physique": "peace", "perception": "spirit", "willpower": "destiny", "agility": "freedom", "social": "peace"}


class NarrativeAuthorityService:
    """Give AI content authority inside a program-owned narrative envelope."""

    def __init__(self, remote: DeepSeekService | None = None) -> None:
        self.remote = remote or DeepSeekService()

    @staticmethod
    def _parse_json(text: str) -> dict[str, Any]:
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned, flags=re.I)
        return json.loads(cleaned)

    def _remote_scene(self, envelope: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
        if os.getenv("RUNETERRA_DISABLE_REMOTE_AI") == "1" or not self.remote.configured:
            return None, None
        schema = {
            "sceneTitle": "世界内标题", "sceneSummary": "第二人称具体现场正文",
            "localActors": ["普通NPC或允许的英雄"], "localObjects": ["现场物件"],
            "immediateProblem": "眼前必须处理的局部问题", "playerObservableFacts": ["玩家可直接观察的事实"],
            "suggestedActions": [{"semanticAction": "动作", "goal": "目标", "approach": "手段", "expectedRiskType": "低/中/高", "target": "可选目标"}],
        }
        try:
            response = self.remote.generate(
                system=(
                    "你是互动RPG的现场导演与NPC演员。只创造叙事内容，不决定规则。"
                    "严格输出一个JSON对象，不得输出成功率、难度、掷骰、奖励、关系数值或世界阶段变化。"
                    "suggestedActions给出2到5条在当前具体现场真正不同的合理行为，先描述行为语义，不写属性名。"
                    "必须遵守hardFacts、requiredElements和forbiddenChanges；creativeFreedom内的内容由你自由创造。"
                ),
                prompt=json.dumps({"narrativeEnvelope": envelope, "outputSchema": schema}, ensure_ascii=False),
                temperature=0.78,
                max_tokens=1100,
            )
            return self._parse_json(response["text"]), response["text"]
        except (DeepSeekError, json.JSONDecodeError, TypeError, KeyError) as exc:
            return None, str(exc)

    @staticmethod
    def _fallback_scene(template: dict[str, Any], envelope: dict[str, Any]) -> dict[str, Any]:
        components = template.get("components", {})
        actor = components.get("actor", "附近的旅人")
        obj = components.get("object", "一处异常痕迹")
        setting = components.get("setting", envelope["location"]["name"])
        pressure = components.get("pressure", "留给判断的时间不多")
        hero = envelope.get("heroContext")
        hero_name = (hero or {}).get("name") or (hero or {}).get("canon", {}).get("name", "亚索")
        encounter = envelope.get("heroEncounter", {})
        hero_line = ""
        if encounter.get("level") == 1 and encounter.get("trace"):
            hero_line = encounter["trace"]
        elif encounter.get("level") == 2 and encounter.get("rumor"):
            hero_line = f"有人压低声音说：‘{encounter['rumor']}’"
        elif encounter.get("level") == 3:
            hero_line = "远处有个背剑的身影从断墙后掠过，没有为任何人的呼喊停步。"
        elif encounter.get("level", 0) >= 4 and hero:
            hero_line = f"{hero_name}站在不远处，目光先落在现场，而不是你身上。"
        scene = f"{setting}，{actor}守在{obj}旁。{pressure}。{hero_line}".strip()
        actions = []
        for choice in template.get("choices", []):
            actions.append({
                "semanticAction": choice.get("semanticAction", choice["text"]),
                "goal": choice.get("goal", "处理眼前问题"), "approach": choice.get("approach", choice.get("hint", "谨慎行动")),
                "expectedRiskType": choice.get("risk", "中"), "target": obj,
            })
        return {
            "sceneTitle": template.get("title", "眼前的异样"), "sceneSummary": scene,
            "localActors": [actor] + ([hero_name] if hero and encounter.get("level", 0) >= 4 else []),
            "localObjects": [obj], "immediateProblem": pressure,
            "playerObservableFacts": [f"{obj}就在{setting}", pressure] + ([hero_line] if hero_line else []),
            "suggestedActions": actions,
        }

    @staticmethod
    def _forbidden_claim(text: str) -> str | None:
        terms = {
            "成功率": "AI试图决定成功率", "难度": "AI试图决定难度", "掷骰": "AI试图决定随机结果",
            "获得神器": "AI试图给予重大物品", "亚索死亡": "AI试图杀死受保护英雄",
            "亚索被杀": "AI试图杀死受保护英雄", "阶段推进": "AI试图推进世界阶段",
            "村庄毁灭": "AI试图制造未授权重大结果",
        }
        return next((reason for term, reason in terms.items() if term in text), None)

    def validate_scene(self, proposal: dict[str, Any] | None, envelope: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any]]:
        debug: dict[str, Any] = {"rejectedSceneFacts": [], "rejectedActions": [], "validatorReasons": []}
        if not isinstance(proposal, dict):
            debug["validatorReasons"].append("场景提案不是对象")
            return None, debug
        required = ("sceneTitle", "sceneSummary", "localActors", "localObjects", "immediateProblem", "playerObservableFacts", "suggestedActions")
        missing = [key for key in required if key not in proposal]
        if missing:
            debug["validatorReasons"].append("缺少字段：" + "、".join(missing))
            return None, debug
        scene_only = {key: value for key, value in proposal.items() if key != "suggestedActions"}
        whole_text = json.dumps(scene_only, ensure_ascii=False)
        reason = self._forbidden_claim(whole_text)
        if reason:
            debug["rejectedSceneFacts"].append({"text": whole_text[:240], "reason": reason})
            return None, debug
        hero_context = envelope.get("heroContext") or {}
        allowed_hero = hero_context.get("name") or hero_context.get("canon", {}).get("name")
        canon_names = ("亚索", "慎", "阿卡丽", "劫", "易", "艾瑞莉娅", "艾翁", "韦鲁斯")
        actors = [str(item).strip() for item in proposal.get("localActors", [])]
        unauthorized = next((
            name for name in canon_names
            if name != allowed_hero and (
                (name in whole_text if len(name) > 1 else any(actor == name for actor in actors))
            )
        ), None)
        if unauthorized:
            debug["rejectedSceneFacts"].append({"text": unauthorized, "reason": "出现叙事边界未允许的英雄"})
            return None, debug
        encounter = envelope.get("heroEncounter", {})
        required_hero_text = encounter.get("trace") if encounter.get("level") == 1 else encounter.get("rumor") if encounter.get("level") == 2 else "亚索" if encounter.get("level", 0) >= 4 else None
        missing_glimpse = encounter.get("level") == 3 and not any(term in whole_text for term in ("背剑", "浪人", "剑客", "亚索"))
        if missing_glimpse or (required_hero_text and required_hero_text not in whole_text):
            debug["validatorReasons"].append("场景没有落实叙事信封要求的英雄痕迹、传闻或出场层级")
            return None, debug
        actions = proposal.get("suggestedActions")
        if not isinstance(actions, list) or not 2 <= len(actions) <= 5:
            debug["validatorReasons"].append("行动提案数量必须为2到5")
            return None, debug
        return proposal, debug

    @staticmethod
    def _map_ability(action: dict[str, Any]) -> tuple[str | None, bool, str]:
        text = " ".join(str(action.get(key, "")) for key in ("semanticAction", "goal", "approach", "target"))
        if any(term in text for term in ("离开", "撤离", "记下", "记录", "等待", "不介入", "保持距离")):
            return None, False, "行动没有不确定的能力门槛，结果由选择本身决定"
        mappings = (
            ("social", ("询问", "交涉", "说服", "安抚", "套话", "组织", "沟通"), "通过语言与他人反应推进目标"),
            ("agility", ("藏", "潜", "绕", "闪避", "悄悄", "追踪", "攀", "侧面"), "依靠时机、隐蔽与移动完成行动"),
            ("perception", ("观察", "检查", "辨认", "脚印", "痕迹", "倾听", "调查", "判断"), "需要从现场细节中得出可靠判断"),
            ("martial", ("拔剑", "武器", "攻击", "迎战", "压制", "格挡", "威慑"), "依靠战斗技巧直接控制威胁"),
            ("physique", ("搬", "抬", "顶住", "承受", "保护", "拖开", "撞开"), "依靠身体力量承受或转移危险"),
            ("willpower", ("灵息", "异变", "意识", "恐惧", "稳住", "感受", "抵抗"), "需要稳定意识并承受精神影响"),
        )
        for ability, terms, reason in mappings:
            if any(term in text for term in terms):
                return ability, True, reason
        return "perception", True, "行动需要先判断现场变化，默认映射为灵觉"

    def map_actions(self, proposals: list[dict[str, Any]], envelope: dict[str, Any], difficulty: int, fallback: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        accepted: list[dict[str, Any]] = []
        rejected: list[dict[str, Any]] = []
        normalized: set[str] = set()
        used_mechanics: set[int] = set()
        pool = list(proposals) if len(proposals) >= 2 else list(proposals) + [
            {"semanticAction": item.get("semanticAction", item["text"]), "goal": item.get("goal", "处理眼前问题"), "approach": item.get("approach", item.get("hint", "谨慎行动")), "expectedRiskType": item.get("risk", "中"), "target": None}
            for item in fallback
        ]
        for proposal in pool:
            if not isinstance(proposal, dict) or not all(str(proposal.get(key, "")).strip() for key in ("semanticAction", "goal", "approach")):
                rejected.append({"proposal": proposal, "reason": "行动缺少语义、目标或手段"})
                continue
            semantic = str(proposal["semanticAction"]).strip()
            key = re.sub(r"[，。！？、\s]", "", semantic)
            if key in normalized:
                rejected.append({"proposal": proposal, "reason": "行动语义重复"})
                continue
            reason = self._forbidden_claim(json.dumps(proposal, ensure_ascii=False))
            if reason:
                rejected.append({"proposal": proposal, "reason": reason})
                continue
            ability, requires_check, mapping_reason = self._map_ability(proposal)
            risk = proposal.get("expectedRiskType", "中")
            risk = risk if risk in {"低", "中", "高", "致命"} else "中"
            index = len(accepted)
            trait = TRAIT_BY_ABILITY.get(ability, "destiny")
            mechanic_index = next((
                item_index for item_index, item in enumerate(fallback)
                if item_index not in used_mechanics and item.get("attribute") == ability
            ), None)
            if mechanic_index is None:
                mechanic_index = next((item_index for item_index in range(len(fallback)) if item_index not in used_mechanics), None)
            mechanical = fallback[mechanic_index] if mechanic_index is not None else {}
            if mechanic_index is not None:
                used_mechanics.add(mechanic_index)
            result: dict[str, Any] = copy.deepcopy(mechanical.get("result", {}))
            result["text"] = f"你尝试{semantic}，局势将按照已经确定的结果回应这个选择。"
            result["personality"] = {trait: 1 if not requires_check else 3}
            choice = {
                "id": f"ai-action-{index}", "semanticAction": semantic, "goal": proposal["goal"], "approach": proposal["approach"],
                "requiresCheck": requires_check, "risk": risk, "possibleOutcomeClass": "local_change",
                "requirements": copy.deepcopy(mechanical.get("requirements", [])),
                "text": semantic, "hint": f"目标：{proposal['goal']}；代价可能来自{risk}风险", "result": result,
                "abilityMappingReason": mapping_reason,
            }
            if requires_check:
                risk_delta = {"低": -1, "中": 0, "高": 1, "致命": 2}[risk]
                choice.update({"attribute": ability, "requiredAbility": ability, "difficulty": max(5, min(12, difficulty + risk_delta))})
            accepted.append(choice)
            normalized.add(key)
            if len(accepted) == 4:
                break
        if len(accepted) < 2:
            raise ValueError("AI与保底行动均未能提供足够合法选项")
        return accepted, {"accepted": [{"semanticAction": item["semanticAction"], "ability": item.get("attribute"), "mappingReason": item["abilityMappingReason"]} for item in accepted], "rejectedActions": rejected}

    def materialize(self, envelope: dict[str, Any], template: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
        remote_proposal, raw = self._remote_scene(envelope)
        proposal, validation = self.validate_scene(remote_proposal, envelope)
        source = "ai"
        if proposal is None:
            proposal = self._fallback_scene(template, envelope)
            source = "fallback"
            fallback_valid, fallback_debug = self.validate_scene(proposal, envelope)
            if fallback_valid is None:
                proposal = {
                    **proposal,
                    "sceneTitle": "眼前的变化",
                    "sceneSummary": f"{envelope['location']['name']}的一角出现了需要立刻处理的异常，附近的人正等待你作出回应。",
                    "immediateProblem": "眼前的局部局势仍在变化",
                    "playerObservableFacts": ["异常就在眼前", "附近的人尚未采取决定性行动"],
                }
                fallback_valid, fallback_debug = self.validate_scene(proposal, envelope)
                if fallback_valid is None:
                    raise ValueError("本地叙事保底未通过边界验证")
            validation["validatorReasons"].extend(fallback_debug["validatorReasons"])
        intensity = envelope.get("directorIntent", {}).get("intensity", "medium")
        difficulty = {"low": 6, "medium": 8, "high": 10, "climax": 11}.get(intensity, 8)
        choices, action_debug = self.map_actions(proposal["suggestedActions"], envelope, difficulty, template.get("choices", []))
        debug = {
            "narrativeEnvelope": envelope, "source": source, "rawAIOutput": raw,
            "aiSceneProposal": proposal, "aiActionProposals": proposal["suggestedActions"],
            **validation, **action_debug,
        }
        event = {
            **template, "title": proposal["sceneTitle"], "text": proposal["sceneSummary"], "choices": choices,
            "sceneProposal": {key: proposal[key] for key in ("localActors", "localObjects", "immediateProblem", "playerObservableFacts")},
            "narrativeAuthoritySource": source, "narrativeAuthorityDebug": debug,
        }
        return event, debug
