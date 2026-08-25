from __future__ import annotations

import copy
from difflib import SequenceMatcher
import hashlib
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

    def _remote_context_audit(
        self, content: dict[str, Any], context: dict[str, Any], *, phase: str,
    ) -> tuple[dict[str, Any] | None, str | None]:
        """Ask AI for semantic continuity only; the program still owns acceptance and state."""
        if os.getenv("RUNETERRA_DISABLE_REMOTE_AI") == "1" or not self.remote.configured:
            return None, None
        try:
            response = self.remote.generate(
                system=(
                    "你是互动RPG的独立上下文审核员，不续写剧情、不决定规则、不修改世界状态。"
                    "比较candidate与context，检查是否承接最新事实、是否重复已经解决的问题、行动是否引用现场实体、"
                    "选项是否只是同义改写、是否与历史行动重复。严格输出JSON对象："
                    "verdict只能是PASS或REPAIR；issues为数组，每项包含field、type、reason、repairInstruction。"
                    "只有明确影响连续性或玩家决策的问题才判REPAIR；不要因为文风偏好否决内容。"
                ),
                prompt=json.dumps({
                    "phase": phase,
                    "context": context,
                    "candidate": content,
                    "outputSchema": {
                        "verdict": "PASS | REPAIR",
                        "issues": [{"field": "字段路径", "type": "问题类型", "reason": "依据", "repairInstruction": "局部修复要求"}],
                    },
                }, ensure_ascii=False),
                temperature=0.1,
                max_tokens=500,
            )
            audit = self._parse_json(response["text"])
            if audit.get("verdict") not in {"PASS", "REPAIR"} or not isinstance(audit.get("issues", []), list):
                raise ValueError("上下文审核返回格式无效")
            return {"verdict": audit["verdict"], "issues": audit.get("issues", [])}, response["text"]
        except (DeepSeekError, json.JSONDecodeError, TypeError, KeyError, ValueError) as exc:
            return None, str(exc)

    @staticmethod
    def _audit_feedback(audit: dict[str, Any] | None) -> list[str]:
        if not audit or audit.get("verdict") != "REPAIR":
            return []
        feedback = []
        for issue in audit.get("issues", []):
            if not isinstance(issue, dict):
                continue
            instruction = str(issue.get("repairInstruction") or issue.get("reason") or "").strip()
            if instruction:
                feedback.append(f"{issue.get('field', 'content')}：{instruction}")
        return feedback[:6]

    @staticmethod
    def _dynamic_action_proposals(
        *, actors: list[Any], objects: list[Any], focus: str, location: str,
        previous_actions: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        """Compose grounded emergency actions from live entities, never from story phrase lists."""
        actor = str(next((item for item in actors if str(item).strip()), "在场的见证人"))
        obj = str(next((item for item in objects if str(item).strip()), focus or "现场的异常"))
        focus = str(focus or obj).strip()
        location = str(location or "当前地点").strip()
        seed = int(hashlib.sha256(f"{location}|{focus}|{actor}|{obj}".encode("utf-8")).hexdigest()[:8], 16)
        observe_verbs = ("核对", "辨认", "复查", "比对")
        social_verbs = ("请", "向", "让", "同")
        move_verbs = ("绕到", "退到", "借助", "贴近")
        proposals = [
            {
                "semanticAction": f"{observe_verbs[seed % len(observe_verbs)]}{obj}与{focus}之间的细节",
                "goal": f"确认{focus}究竟说明了什么",
                "approach": f"从{obj}上可见的新旧差异逐项判断",
                "expectedRiskType": "中", "target": obj,
            },
            {
                "semanticAction": f"{social_verbs[(seed >> 2) % len(social_verbs)]}{actor}说明他刚才亲眼看见的经过",
                "goal": f"验证关于{focus}的现场说法",
                "approach": f"把证词与{obj}的状态当场核对",
                "expectedRiskType": "低", "target": actor,
            },
            {
                "semanticAction": f"{move_verbs[(seed >> 4) % len(move_verbs)]}{focus}不易察觉的位置继续观察",
                "goal": f"在不惊动现场变化的情况下确认{focus}",
                "approach": f"利用{location}的遮挡与视线空隙改变观察角度",
                "expectedRiskType": "高", "target": focus,
            },
            {
                "semanticAction": f"保留对{obj}的记录并退出{location}现场",
                "goal": f"停止承担围绕{focus}继续扩大的风险",
                "approach": "确认退路后主动结束本次介入",
                "expectedRiskType": "低", "target": obj,
            },
        ]
        previous_text = " ".join(str(item.get("text", "")) for item in previous_actions or [])
        return [item for item in proposals if item["semanticAction"] not in previous_text]

    @staticmethod
    def _synthesize_scene(template: dict[str, Any], envelope: dict[str, Any]) -> dict[str, Any]:
        components = template.get("components", {})
        actor = components.get("actor", "附近的旅人")
        obj = components.get("object", "一处异常痕迹")
        setting = components.get("setting", envelope["location"]["name"])
        pressure = components.get("pressure", "留给判断的时间不多")
        player_intent = envelope.get("playerIntent", {})
        tracking_lead = player_intent.get("kind") == "track_lead"
        if tracking_lead:
            obj = player_intent.get("title", obj)
            pressure = f"与“{player_intent.get('title')}”有关的痕迹正在被风和来往脚步覆盖"
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
        if tracking_lead:
            paragraph_two = (
                f"你不是漫无目的来到{setting}。循着“{player_intent.get('title')}”的说法核对林缘后，"
                f"你在{obj}附近看见了被落叶遮住的新痕；{actor}正守在那里，试图分清它与旧兽道的先后。"
                f"每一次风动都在抹平边缘，{pressure}。"
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
        actions = NarrativeAuthorityService._dynamic_action_proposals(
            actors=[actor], objects=[obj], focus=pressure,
            location=envelope["location"]["name"],
        )
        return {
            "sceneTitle": template.get("title", "眼前的异样"), "sceneSummary": scene,
            "localActors": [actor] + ([hero_name] if hero and encounter.get("level", 0) >= 4 else []),
            "localObjects": [obj], "immediateProblem": pressure,
            "playerObservableFacts": [f"{obj}就在{setting}", pressure] + ([hero_line] if hero_line else []),
            "suggestedActions": actions,
        }

    def _repair_scene_fields(
        self, proposal: dict[str, Any], template: dict[str, Any], envelope: dict[str, Any],
    ) -> dict[str, Any]:
        """Preserve usable AI fields and repair only missing/structurally unusable parts."""
        baseline = self._synthesize_scene(template, envelope)
        repaired = copy.deepcopy(baseline)
        title = str(proposal.get("sceneTitle", "")).strip()
        if title:
            repaired["sceneTitle"] = title
        summary = str(proposal.get("sceneSummary", "")).strip()
        paragraphs = [item.strip() for item in re.split(r"\n\s*\n", summary) if item.strip()]
        if len(re.sub(r"\s", "", summary)) >= 220 and len(paragraphs) >= 4:
            repaired["sceneSummary"] = summary
        for key in ("localActors", "localObjects", "playerObservableFacts"):
            value = proposal.get(key)
            if isinstance(value, list) and any(str(item).strip() for item in value):
                repaired[key] = [str(item).strip() for item in value if str(item).strip()]
        problem = str(proposal.get("immediateProblem", "")).strip()
        if problem:
            repaired["immediateProblem"] = problem
        actions = proposal.get("suggestedActions")
        if isinstance(actions, list):
            usable = [item for item in actions if isinstance(item, dict)]
            if usable:
                repaired["suggestedActions"] = (usable + baseline["suggestedActions"])[:max(2, min(5, len(usable) + 1))]
        return repaired

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

    @staticmethod
    def _normalized_action(text: Any) -> str:
        value = re.sub(r"[，。！？、：；\s]", "", str(text or "")).lower()
        for filler in ("继续", "再次", "再度", "重新", "仍然", "试着", "尝试"):
            value = value.replace(filler, "")
        return value

    def _repeats_previous_action(
        self, proposal: dict[str, Any], previous_actions: list[dict[str, Any]], current_focus: str,
    ) -> bool:
        """Minimal semantic guard: same action family, same target and near-identical wording."""
        if not previous_actions:
            return False
        ability, requires_check, _reason = self._map_ability(proposal)
        action_tags = set(self._action_tags(proposal, ability, requires_check))
        target = self._normalized_action(proposal.get("target"))
        semantic = self._normalized_action(proposal.get("semanticAction"))
        focus = self._normalized_action(current_focus)
        for previous in previous_actions:
            previous_tags = set(previous.get("actionTags", []))
            previous_targets = {self._normalized_action(item) for item in previous.get("targetTags", []) if item}
            previous_semantic = self._normalized_action(previous.get("text") or previous.get("semanticAction"))
            same_action = bool(action_tags & previous_tags) or not action_tags or not previous_tags
            same_target = bool(target and target in previous_targets)
            close_semantic = SequenceMatcher(None, semantic, previous_semantic).ratio() >= 0.68
            new_focus_target = bool(focus and focus not in previous_semantic and (focus in semantic or focus in target))
            if same_action and same_target and close_semantic and not new_focus_target:
                return True
        return False

    def map_actions(
        self, proposals: list[dict[str, Any]], envelope: dict[str, Any], difficulty: int,
        fallback: list[dict[str, Any]], *, previous_actions: list[dict[str, Any]] | None = None,
        current_focus: str = "", current_round: int = 1,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        accepted: list[dict[str, Any]] = []
        rejected: list[dict[str, Any]] = []
        normalized: set[str] = set()
        pool = list(proposals) + list(fallback)
        desired_count = min(4, max(2, len(proposals)))
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
            if self._repeats_previous_action(proposal, previous_actions or [], current_focus):
                rejected.append({"proposal": proposal, "reason": "与已经完成的行动在行为、目标和语义上重复"})
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
                "id": f"scene-action-{current_round}-{index}", "semanticAction": semantic, "goal": proposal["goal"], "approach": proposal["approach"],
                "requiresCheck": requires_check, "risk": risk, "possibleOutcomeClass": "local_change",
                "requirements": [],
                "text": semantic, "hint": "", "result": result,
                "abilityMappingReason": mapping_reason,
                "actionTags": self._action_tags(proposal, ability, requires_check),
                "targetTags": self._target_tags(proposal),
            }
            if requires_check:
                risk_delta = {"低": -1, "中": 0, "高": 1, "致命": 2}[risk]
                choice.update({"attribute": ability, "requiredAbility": ability, "difficulty": max(5, min(12, difficulty + risk_delta))})
            accepted.append(choice)
            normalized.add(key)
            if len(accepted) == desired_count:
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
        attempts: list[dict[str, Any]] = []
        previous_actions = copy.deepcopy(scene.get("previousActions", []))
        current_focus = str(scene.get("currentFocus") or (scene.get("questions") or ["当前变化"])[0])
        if os.getenv("RUNETERRA_DISABLE_REMOTE_AI") != "1" and self.remote.configured:
            revision_feedback: list[str] = []
            for _attempt in range(2):
                try:
                    response = self.remote.generate(
                        system=(
                            "你是互动RPG当前现场的行动导演。这是一个已经进行中的Scene，世界已因上一轮行动发生变化。"
                            "根据最新Facts、Questions和Current Focus，只提出2到4条玩家此刻真正可做且决策空间不同的行为。"
                            "不要重新介绍事件，不要重复Previous Actions；只有新事实赋予同类行为新的明确目标时才可再次使用。"
                            "行动主要围绕Current Focus。只输出JSON对象，唯一字段为actions；每条只含semanticAction、goal、"
                            "approach、expectedRiskType、target。不得写属性、成功率、奖励、线索、状态或预定结果。"
                        ),
                        prompt=json.dumps({
                            "sceneState": {key: scene.get(key) for key in ("round", "actors", "objects", "facts", "questions", "lastAction", "lastResult")},
                            "previousActions": previous_actions,
                            "currentFocus": current_focus,
                            "hardFacts": envelope.get("hardFacts", []),
                            "forbiddenChanges": envelope.get("forbiddenChanges", []),
                            "revisionFeedback": revision_feedback,
                        }, ensure_ascii=False),
                        temperature=0.72,
                        max_tokens=650,
                    )
                    raw = response["text"]
                    parsed = self._parse_json(raw)
                    proposals = parsed.get("actions", []) if isinstance(parsed.get("actions"), list) else []
                    choices, debug = self.map_actions(
                        proposals, envelope, difficulty, [], previous_actions=previous_actions,
                        current_focus=current_focus, current_round=int(scene.get("round", 1)),
                    )
                    attempts.append({"raw": raw, "rejectedActions": copy.deepcopy(debug["rejectedActions"])})
                    audit_context = {
                        "sceneState": {key: scene.get(key) for key in ("round", "actors", "objects", "facts", "questions", "lastAction", "lastResult")},
                        "previousActions": previous_actions, "currentFocus": current_focus,
                    }
                    audit, audit_raw = self._remote_context_audit({"actions": proposals}, audit_context, phase="next_actions")
                    attempts[-1]["contextAudit"] = {"result": audit, "raw": audit_raw}
                    audit_feedback = self._audit_feedback(audit)
                    if audit_feedback and _attempt == 0:
                        revision_feedback = audit_feedback
                        continue
                    return choices, {
                        "source": "ai", "rawAIOutput": raw, "attempts": attempts,
                        "previousActions": previous_actions, "currentFocus": current_focus,
                        "generatedNextActions": [item["semanticAction"] for item in choices], **debug,
                    }
                except (DeepSeekError, json.JSONDecodeError, TypeError, KeyError, ValueError) as exc:
                    raw = str(exc)
                    revision_feedback = ["上一批行动重复、缺失或不足两条，请围绕最新Focus彻底重写。", raw]
                    attempts.append({"raw": raw, "error": str(exc)})
        proposals = self._dynamic_action_proposals(
            actors=scene.get("actors", []), objects=scene.get("objects", []), focus=current_focus,
            location=envelope.get("location", {}).get("name", "当前地点"), previous_actions=previous_actions,
        )
        choices, debug = self.map_actions(
            proposals, envelope, difficulty, template.get("choices", []), previous_actions=previous_actions,
            current_focus=current_focus, current_round=int(scene.get("round", 1)),
        )
        return choices, {
            "source": "dynamic_synthesis", "rawAIOutput": raw, "attempts": attempts,
            "previousActions": previous_actions, "currentFocus": current_focus,
            "generatedNextActions": [item["semanticAction"] for item in choices], **debug,
        }

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
            elif retry_proposal is not None and not retry_validation["rejectedSceneFacts"]:
                repaired = self._repair_scene_fields(retry_proposal, template, envelope)
                repaired_valid, repaired_validation = self.validate_scene(repaired, envelope)
                if repaired_valid is not None:
                    proposal, validation, raw, source = repaired_valid, repaired_validation, retry_raw, "ai_repaired"
        if proposal is None:
            proposal = self._synthesize_scene(template, envelope)
            source = "dynamic_synthesis"
            fallback_valid, fallback_debug = self.validate_scene(proposal, envelope)
            if fallback_valid is None:
                raise ValueError("本地叙事保底未通过边界验证")
            validation["validatorReasons"].extend(fallback_debug["validatorReasons"])
        elif source == "ai":
            audit_context = {
                "narrativeEnvelope": envelope,
                "activeLead": envelope.get("playerIntent"),
                "history": envelope.get("leadHistory", []),
            }
            audit, audit_raw = self._remote_context_audit(proposal, audit_context, phase="initial_scene")
            attempts[-1]["contextAudit"] = {"result": audit, "raw": audit_raw}
            feedback = self._audit_feedback(audit)
            if feedback:
                retry_proposal, retry_raw = self._remote_scene(envelope, revision_feedback=feedback)
                retry_valid, retry_validation = self.validate_scene(retry_proposal, envelope)
                attempts.append({"raw": retry_raw, "validation": copy.deepcopy(retry_validation), "reason": "context_audit_repair"})
                if retry_valid is not None:
                    proposal, validation, raw, source = retry_valid, retry_validation, retry_raw, "ai_context_repaired"
        intensity = envelope.get("directorIntent", {}).get("intensity", "medium")
        difficulty = {"low": 6, "medium": 8, "high": 10, "climax": 11}.get(intensity, 8)
        dynamic_actions = self._dynamic_action_proposals(
            actors=proposal.get("localActors", []), objects=proposal.get("localObjects", []),
            focus=proposal.get("immediateProblem", ""), location=envelope["location"]["name"],
        )
        choices, action_debug = self.map_actions(proposal["suggestedActions"], envelope, difficulty, dynamic_actions)
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
