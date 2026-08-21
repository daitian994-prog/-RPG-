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

    def _remote_scene(self, envelope: dict[str, Any], *, revision_feedback: list[str] | None = None) -> tuple[dict[str, Any] | None, str | None]:
        if os.getenv("RUNETERRA_DISABLE_REMOTE_AI") == "1" or not self.remote.configured:
            return None, None
        schema = {
            "sceneTitle": "具体且只描述世界内现场的标题",
            "sceneSummary": "300至450个中文字符、分为4段的第二人称完整事件正文",
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
                    "sceneSummary必须是可直接展示的完整事件：四段分别写感官环境、事件动作与矛盾、玩家可见判断、迫近风险。"
                    "不得把playerObservableFacts或immediateProblem逐句复述进正文，不得使用系统播报和创作说明。"
                    "必须遵守hardFacts、requiredElements和forbiddenChanges；creativeFreedom内的内容由你自由创造。"
                ),
                prompt=json.dumps({
                    "narrativeEnvelope": envelope, "outputSchema": schema,
                    "revisionFeedback": revision_feedback or [],
                    "minimumQuality": {"sceneSummaryCharacters": 300, "paragraphs": 4, "noRepeatedFacts": True},
                }, ensure_ascii=False),
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
        location_id = envelope["location"]["id"]
        atmosphere = {
            "pallas": "风沿着帕拉斯的青石路穿过药田，带来湿土、草叶和灶火混在一起的气味。屋檐滴水落进浅沟，原本寻常的村声却在前方突然低了下去。",
            "windbreak": "断风森林的雾贴着树根缓慢移动，潮湿苔藓吸走脚步声，只有叶尖积水不时坠下。更深处的鸟鸣停了，近处枝条却仍在轻轻摇晃。",
            "war_ruins": "风穿过战争遗迹破裂的箭窗，把灰尘和铁锈味推入断墙之间。半埋的瓦片在鞋底轻响，回声沿空洞军帐传得比平时更远。",
            "mountain_temple": "云气越过山间寺庙的石阶，松针上的水珠落进苔痕，檐角铜铃却没有随风作响。香烟从半开的门缝逸出，又在回廊前突然散开。",
        }.get(location_id, f"风从{envelope['location']['name']}近处掠过，周围熟悉的声音忽然出现了细微变化。")
        actor_motion = {
            "日常": "反复打量", "NPC": "压低声音守着", "成长": "犹豫着触碰",
            "探索": "俯身检查", "命运": "沉默地注视", "战斗": "紧握手边武器挡在",
        }.get(template.get("type"), "谨慎地守在")
        object_suffix = "前" if template.get("type") == "战斗" else ""
        paragraph_two = (
            f"你循着动静走到{setting}，看见{actor}正{actor_motion}{obj}{object_suffix}。"
            f"眼前的异常并没有安静留在原处：周围新留下的痕迹与在场人的说法互相矛盾，每当有人靠近，{pressure}。"
            f"{actor}几次想开口，又都先望向来路，显然还有一部分经过没有说出来。"
        )
        personality = envelope.get("playerSummary", {}).get("personality", {})
        dominant = max(personality, key=personality.get) if personality else "peace"
        player_reaction = {
            "peace": "你先确认附近有没有人已经受伤，才重新看向异常本身。",
            "power": "你调整站位，让自己随时能够截住最先爆发的危险。",
            "freedom": "你先寻找没有被人群堵住的退路，也留意是否还有第三种处理方式。",
            "spirit": "你察觉周围灵息并不平稳，皮肤也因那阵细微变化泛起凉意。",
            "destiny": "某种熟悉的不安从记忆边缘掠过，提醒你别把眼前变化当成偶然。",
        }[dominant]
        paragraph_three = (
            f"{player_reaction}{obj}附近的泥土、气味和细小声响都指向同一个事实：这不是一句传闻就能解释的插曲。"
            f"围观者彼此催促，却没有人愿意先承担判断错误的后果。{hero_line}"
        )
        paragraph_four = (
            f"变化仍在继续，留给你的时间正被一点点压缩。若现在靠近，你可能查清发生了什么，也可能让隐藏的危险转向自己；"
            f"若退开，现场和关键说法都可能随人群散去。你必须先决定，要从哪一处入手，以及愿意为这个判断承担什么。"
        )
        scene = "\n\n".join((atmosphere, paragraph_two, paragraph_three, paragraph_four))
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
        summary = str(proposal.get("sceneSummary", "")).strip()
        paragraphs = [item.strip() for item in re.split(r"\n\s*\n", summary) if item.strip()]
        visible_length = len(re.sub(r"\s", "", summary))
        if visible_length < 220 or len(paragraphs) < 4:
            debug["validatorReasons"].append(f"事件正文过短或结构不足：{visible_length}字、{len(paragraphs)}段")
            return None, debug
        normalized_paragraphs = [re.sub(r"[\W_]+", "", item) for item in paragraphs]
        if len(normalized_paragraphs) != len(set(normalized_paragraphs)):
            debug["validatorReasons"].append("事件正文存在重复段落")
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

    @staticmethod
    def _contextual_consequence(action: dict[str, Any], ability: str | None, requires_check: bool) -> str:
        semantic = str(action.get("semanticAction", "处理现场"))
        goal = str(action.get("goal", "控制眼前变化"))
        target = str(action.get("target") or "眼前的关键处")
        if not requires_check:
            return f"你依照自己的判断{semantic}。这没有立刻改变危险本身，却让“{goal}”成为一个明确选择，也使你主动承担了放弃眼前机会的后果。"
        consequences = {
            "perception": f"你从{target}最容易被忽略的细节开始核对，让零散痕迹逐渐指向同一段经过，也终于能够判断怎样才能{goal}。",
            "social": f"你没有急着下结论，而是让在场者分别说清自己看见的部分。前后矛盾在追问中显露，众人的态度也因“{goal}”出现了变化。",
            "agility": f"你借地形与人群视线的空隙完成了{semantic}，避开最直接的阻拦，并为“{goal}”抢到一个短暂位置。",
            "martial": f"你以清楚而克制的动作完成了{semantic}，迫使眼前威胁暂时停下，也把“{goal}”的代价带到了自己面前。",
            "physique": f"你把身体挡在最危险的一环，咬紧牙关完成了{semantic}，让其他人获得处理时间，也让“{goal}”不再只是一句打算。",
            "willpower": f"你稳住呼吸，没有让现场的异样扰乱判断。随着{semantic}，原本混乱的感受出现边界，“{goal}”终于有了可以落实的方向。",
        }
        return consequences.get(ability, f"你完成了{semantic}，现场随之出现了足以推动“{goal}”的具体变化。")

    @staticmethod
    def _action_tags(action: dict[str, Any], ability: str | None, requires_check: bool) -> list[str]:
        text = " ".join(str(action.get(key, "")) for key in ("semanticAction", "goal", "approach", "target"))
        groups = (
            ("withdraw", ("离开", "撤离", "不介入", "保持距离")),
            ("record", ("记下", "记录")),
            ("social", ("询问", "交涉", "说服", "安抚", "核对说法")),
            ("stealth", ("藏", "潜", "悄悄", "绕到", "隐蔽")),
            ("investigate", ("观察", "检查", "辨认", "痕迹", "倾听", "调查", "判断", "核对")),
            ("combat", ("拔剑", "武器", "攻击", "迎战", "压制", "格挡", "威慑")),
            ("protect", ("保护", "搬", "抬", "顶住", "承受", "拖开", "挡在")),
            ("spirit", ("灵息", "灵体", "异变", "意识", "感受", "抵抗", "震颤")),
        )
        tags = [tag for tag, terms in groups if any(term in text for term in terms)]
        if not requires_check and not tags:
            tags.append("deliberate")
        return list(dict.fromkeys(tags))

    @staticmethod
    def _target_tags(action: dict[str, Any]) -> list[str]:
        text = " ".join(str(action.get(key, "")) for key in ("semanticAction", "goal", "approach", "target"))
        known = (
            "铜钟", "钟座", "灵体", "灵息", "诺克萨斯", "斥候", "山道", "竹林", "井水", "古井",
            "爆裂符", "木箱", "药箱", "石碑", "林灵", "森林", "遗迹", "旅人", "药师", "短剑",
        )
        tags = [term for term in known if term in text]
        target = re.sub(r"[，。！？、\s]", "", str(action.get("target", "")))
        if 1 < len(target) <= 16:
            tags.insert(0, target)
        return list(dict.fromkeys(tags))

    def map_actions(self, proposals: list[dict[str, Any]], envelope: dict[str, Any], difficulty: int, fallback: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        accepted: list[dict[str, Any]] = []
        rejected: list[dict[str, Any]] = []
        normalized: set[str] = set()
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
            # AI actions describe intent only. They must never inherit rewards, clues,
            # statuses or relationship packages from an unrelated fallback choice.
            result: dict[str, Any] = {
                "text": self._contextual_consequence(proposal, ability, requires_check),
                "personality": {trait: 1 if not requires_check else 3},
            }
            choice = {
                "id": f"ai-action-{index}", "semanticAction": semantic, "goal": proposal["goal"], "approach": proposal["approach"],
                "requiresCheck": requires_check, "risk": risk, "possibleOutcomeClass": "local_change",
                "requirements": [],
                "text": semantic, "hint": f"目标：{proposal['goal']}；代价可能来自{risk}风险", "result": result,
                "abilityMappingReason": mapping_reason,
                "actionTags": self._action_tags(proposal, ability, requires_check),
                "targetTags": self._target_tags(proposal),
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

    def next_actions(
        self, scene: dict[str, Any], envelope: dict[str, Any], template: dict[str, Any], difficulty: int,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """Create the next round's actions from the persisted scene, with a local fallback."""
        proposals: list[dict[str, Any]] = []
        raw: str | None = None
        remote_valid = False
        if os.getenv("RUNETERRA_DISABLE_REMOTE_AI") != "1" and self.remote.configured:
            try:
                response = self.remote.generate(
                    system=(
                        "你是互动RPG当前现场的行动导演。根据SceneState提出2到5条此刻真正可做、语义不同的行为。"
                        "只输出JSON对象，唯一字段为actions。每条只含semanticAction、goal、approach、expectedRiskType、target。"
                        "不写属性、成功率、奖励、线索、状态或结果。行动必须承接已有facts与尚未解决的questions。"
                    ),
                    prompt=json.dumps({
                        "sceneState": {key: scene.get(key) for key in ("round", "actors", "objects", "facts", "questions", "lastAction", "lastResult")},
                        "hardFacts": envelope.get("hardFacts", []),
                        "forbiddenChanges": envelope.get("forbiddenChanges", []),
                    }, ensure_ascii=False),
                    temperature=0.72,
                    max_tokens=650,
                )
                raw = response["text"]
                parsed = self._parse_json(raw)
                if isinstance(parsed.get("actions"), list):
                    proposals = parsed["actions"]
                    remote_valid = len(proposals) >= 2
            except (DeepSeekError, json.JSONDecodeError, TypeError, KeyError) as exc:
                raw = str(exc)
        if len(proposals) < 2:
            target = (scene.get("objects") or ["现场的关键痕迹"])[0]
            actor = (scene.get("actors") or ["在场的人"])[0]
            question = (scene.get("questions") or [f"{target}为何出现异常"])[0]
            proposals = [
                {"semanticAction": f"继续检查{target}最容易被忽略的部分", "goal": f"回答：{question}", "approach": "核对新旧痕迹", "expectedRiskType": "中", "target": target},
                {"semanticAction": f"询问{actor}刚才发生的细节", "goal": f"回答：{question}", "approach": "让说法与现场事实互相印证", "expectedRiskType": "低", "target": actor},
                {"semanticAction": "记住已经确认的事实并离开现场", "goal": "停止承担眼前风险", "approach": "主动结束介入", "expectedRiskType": "低", "target": target},
            ]
        choices, debug = self.map_actions(proposals, envelope, difficulty, template.get("choices", []))
        return choices, {"source": "ai" if remote_valid else "fallback", "rawAIOutput": raw, **debug}

    def materialize(self, envelope: dict[str, Any], template: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
        remote_proposal, raw = self._remote_scene(envelope)
        proposal, validation = self.validate_scene(remote_proposal, envelope)
        attempts = [{"raw": raw, "validation": copy.deepcopy(validation)}]
        source = "ai"
        if proposal is None and remote_proposal is not None:
            retry_proposal, retry_raw = self._remote_scene(envelope, revision_feedback=validation["validatorReasons"])
            retry_valid, retry_validation = self.validate_scene(retry_proposal, envelope)
            attempts.append({"raw": retry_raw, "validation": copy.deepcopy(retry_validation)})
            if retry_valid is not None:
                proposal, validation, raw = retry_valid, retry_validation, retry_raw
            elif retry_proposal is not None and not retry_validation["rejectedSceneFacts"] and retry_validation["validatorReasons"] and all(reason.startswith("事件正文过短或结构不足") for reason in retry_validation["validatorReasons"]):
                actors = retry_proposal.get("localActors") or [template.get("components", {}).get("actor", "附近的旅人")]
                objects = retry_proposal.get("localObjects") or [template.get("components", {}).get("object", "一处异常痕迹")]
                repair_template = {
                    **template, "title": retry_proposal.get("sceneTitle", template.get("title", "眼前的变化")),
                    "components": {
                        **template.get("components", {}), "actor": actors[0], "object": objects[0],
                        "pressure": retry_proposal.get("immediateProblem", template.get("components", {}).get("pressure", "局势正在变化")),
                    },
                }
                repaired = self._fallback_scene(repair_template, envelope)
                repaired.update({
                    "sceneTitle": retry_proposal.get("sceneTitle", repaired["sceneTitle"]),
                    "localActors": actors, "localObjects": objects,
                    "immediateProblem": retry_proposal.get("immediateProblem", repaired["immediateProblem"]),
                    "playerObservableFacts": retry_proposal.get("playerObservableFacts", repaired["playerObservableFacts"]),
                    "suggestedActions": retry_proposal.get("suggestedActions", repaired["suggestedActions"]),
                })
                repaired_valid, repaired_validation = self.validate_scene(repaired, envelope)
                if repaired_valid is not None:
                    proposal, validation, raw, source = repaired_valid, repaired_validation, retry_raw, "ai_repaired"
        if proposal is None:
            proposal = self._fallback_scene(template, envelope)
            source = "fallback"
            fallback_valid, fallback_debug = self.validate_scene(proposal, envelope)
            if fallback_valid is None:
                raise ValueError("本地叙事保底未通过边界验证")
            validation["validatorReasons"].extend(fallback_debug["validatorReasons"])
        intensity = envelope.get("directorIntent", {}).get("intensity", "medium")
        difficulty = {"low": 6, "medium": 8, "high": 10, "climax": 11}.get(intensity, 8)
        choices, action_debug = self.map_actions(proposal["suggestedActions"], envelope, difficulty, template.get("choices", []))
        debug = {
            "narrativeEnvelope": envelope, "source": source, "rawAIOutput": raw,
            "aiAttempts": attempts,
            "aiSceneProposal": proposal, "aiActionProposals": proposal["suggestedActions"],
            **validation, **action_debug,
        }
        event = {
            **template, "title": proposal["sceneTitle"], "text": proposal["sceneSummary"], "choices": choices,
            "sceneProposal": {key: proposal[key] for key in ("localActors", "localObjects", "immediateProblem", "playerObservableFacts")},
            "narrativeAuthoritySource": source, "narrativeAuthorityDebug": debug,
        }
        return event, debug
