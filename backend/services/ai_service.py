import json
import os
import random
import re
from pathlib import Path
from collections.abc import Iterator
from typing import Any

from backend.services.deepseek_service import DeepSeekError, DeepSeekService
from backend.services.lore_service import LoreService
from backend.services.check_engine import CheckEngine, CheckRequest, Modifier
from backend.services.narrator_contract import NarratorContract


class AIService:
    """Mock-first narrative service. Its public methods can be backed by an API later."""

    names = ["砚青", "岚生", "阿澈", "闻溪", "宿弦", "青禾", "黎照", "朔羽"]

    trait_checks = {
        "peace": ("social", "交涉"), "power": ("martial", "武艺"),
        "freedom": ("agility", "机敏"), "spirit": ("perception", "灵觉"),
        "destiny": ("willpower", "心志"),
    }
    opposing_traits = {"peace": "power", "power": "peace", "freedom": "destiny", "destiny": "freedom", "spirit": "power"}

    def __init__(self) -> None:
        self.remote_ai = DeepSeekService()
        self.lore = LoreService()
        self.check_engine = CheckEngine()
        self.narrator_contract = NarratorContract()
        style_path = Path(__file__).resolve().parents[2] / "game-data" / "narrative_style.json"
        self.narrative_style = json.loads(style_path.read_text(encoding="utf-8"))

    def _style_prompt(
        self,
        *,
        kind: str,
        event_type: str | None = None,
        location_id: str | None = None,
        chapter_phase: str = "journey",
        npc_id: str | None = None,
    ) -> str:
        style = self.narrative_style
        rules = ["《无名者：符文之地》统一叙事规则：", *style["global"]]
        chapter = style["chapter_styles"].get(chapter_phase)
        location = style["location_styles"].get(location_id or "")
        event = style["event_styles"].get(event_type or "")
        voice = style["npc_voices"].get(npc_id or "")
        format_rules = style["formats"].get(kind, [])
        if chapter:
            rules.append(chapter)
        if location:
            rules.append(location)
        if event:
            rules.append(event)
        if voice:
            rules.append(voice)
        rules.extend(format_rules)
        rules.append("只输出最终正文，不输出标题、选项、JSON、规则复述或创作解释。")
        return "\n".join(f"{index}. {rule}" for index, rule in enumerate(rules, 1))

    @staticmethod
    def _normalize_perspective(text: str, player_name: str | None = None) -> str | None:
        """Keep the narrator locked to '你'; quoted NPC dialogue may still use '我'."""
        normalized = text.strip().replace("玩家", "你").replace("主角", "你")
        if player_name:
            normalized = normalized.replace(player_name, "你")
        normalized = re.sub(r"你{2,}", "你", normalized)
        # Reject obvious first-person narration and fall back to authored local prose.
        outside_quotes = re.sub(r"[“『「][^”』」]*[”』」]", "", normalized)
        if re.search(r"(^|[\n。！？])\s*我(?:们|的|在|看|听|感|想|走|向|把|将|被|从|与|却|仍|已经|没有|必须|能|不能)", outside_quotes):
            return None
        if "你" not in normalized:
            return None
        return normalized

    def _narrate(
        self,
        *,
        kind: str,
        facts: dict[str, Any],
        event_type: str | None = None,
        location_id: str | None = None,
        chapter_phase: str = "journey",
        npc_id: str | None = None,
        player_name: str | None = None,
        temperature: float = 0.62,
        max_tokens: int = 700,
    ) -> str | None:
        """Ask the active backend node for prose only; gameplay numbers remain local and authoritative."""
        if os.getenv("RUNETERRA_DISABLE_REMOTE_AI") == "1" or not self.remote_ai.configured:
            return None
        try:
            result = self.remote_ai.generate(
                system=self._style_prompt(
                    kind=kind,
                    event_type=event_type,
                    location_id=location_id,
                    chapter_phase=chapter_phase,
                    npc_id=npc_id,
                ),
                prompt=json.dumps(facts, ensure_ascii=False),
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return self._normalize_perspective(result["text"], player_name)
        except DeepSeekError:
            return None

    def _contract_narrate(
        self, *, kind: str, facts: dict[str, Any], game: dict[str, Any], fallback: str,
        event_type: str, location_id: str, temperature: float, max_tokens: int, remote: bool = True,
    ) -> str:
        """Request and validate the four-field narrator protocol; fall back atomically."""
        contract_input = {
            "eventContext": facts.get("eventContext"),
            "fixedFacts": facts,
            "outputSchema": {"narrative": "string", "choicePresentation": [], "npcDialogue": [], "flavorTags": []},
        }
        debug = {"phase": kind, "input": contract_input, "source": "local", "rawOutput": None}
        if remote and os.getenv("RUNETERRA_DISABLE_REMOTE_AI") != "1" and self.remote_ai.configured:
            try:
                result = self.remote_ai.generate(
                    system=self._style_prompt(
                        kind=kind, event_type=event_type, location_id=location_id,
                        chapter_phase=game.get("chapter_phase", "journey"),
                    ) + "\n最终输出必须是严格JSON对象，且只能含 narrative、choicePresentation、npcDialogue、flavorTags 四个字段。",
                    prompt=json.dumps(contract_input, ensure_ascii=False), temperature=temperature, max_tokens=max_tokens,
                )
                debug["rawOutput"] = result["text"]
                validation = self.narrator_contract.validate(result["text"])
                debug["validation"] = validation
                if validation["valid"]:
                    normalized = self._normalize_perspective(validation["output"]["narrative"], game["player"]["name"])
                    if normalized:
                        debug["source"] = "ai_validated"
                        game["aiNarratorDebug"] = debug
                        return normalized
                    validation["valid"] = False
                    validation["errors"].append("叙事视角不是第二人称")
            except DeepSeekError as exc:
                debug["validation"] = {"valid": False, "errors": [str(exc)]}
        else:
            local_raw = json.dumps({"narrative": fallback, "choicePresentation": [], "npcDialogue": [], "flavorTags": []}, ensure_ascii=False)
            debug["rawOutput"] = local_raw
            debug["validation"] = self.narrator_contract.validate(local_raw)
        game["aiNarratorDebug"] = debug
        return fallback

    def _check_request(self, event: dict[str, Any], choice: dict[str, Any], game: dict[str, Any], choice_index: int) -> CheckRequest:
        personality_effects = choice.get("result", {}).get("personality", {})
        primary_trait = max(personality_effects, key=personality_effects.get) if personality_effects else "destiny"
        attribute, _ = self.trait_checks[primary_trait]
        player = game["player"]
        selected_attribute = choice.get("attribute", attribute)
        difficulty = choice.get("difficulty", {"日常": 6, "NPC": 7, "成长": 8, "探索": 8, "命运": 9, "战斗": 9}.get(event["type"], 8))
        if event.get("chapter_only"):
            difficulty = 11
        modifiers: list[Modifier] = []
        # Personality describes preferred behavior; it never substitutes for capability.
        body = player.get("bodyCondition", {})
        body_bonus = body.get("modifiers", {}).get(selected_attribute, 0)
        if body_bonus:
            modifiers.append(Modifier("body_condition", body.get("label", "伤势"), body_bonus))
        for trait in player.get("traits", []):
            bonus = trait.get("modifiers", {}).get(selected_attribute, 0)
            if bonus:
                modifiers.append(Modifier("trait", trait.get("name", trait["id"]), bonus))
        action_text = " ".join(str(choice.get(key, "")) for key in ("semanticAction", "text", "goal", "approach"))
        action_tags = set(choice.get("actionTags", []))
        inferred_actions = {
            "withdraw": ("离开", "撤离", "不介入"), "record": ("记下", "记录"),
            "social": ("询问", "交涉", "说服", "安抚"), "stealth": ("藏", "潜", "隐蔽", "绕到"),
            "investigate": ("观察", "检查", "辨认", "痕迹", "调查", "核对"),
            "combat": ("拔剑", "武器", "攻击", "迎战", "格挡"), "protect": ("保护", "顶住", "承受", "挡在"),
            "spirit": ("灵息", "灵体", "异变", "感受", "震颤"),
        }
        action_tags.update(tag for tag, terms in inferred_actions.items() if any(term in action_text for term in terms))
        target_tags = set(choice.get("targetTags", []))
        for term in ("铜钟", "钟座", "灵体", "灵息", "诺克萨斯", "斥候", "山道", "竹林", "井水", "古井", "爆裂符", "木箱", "药箱", "石碑", "林灵", "森林", "遗迹"):
            if term in action_text:
                target_tags.add(term)
        faction_tags = {"noxian"} if any(term in action_text for term in ("诺克萨斯", "血旗", "斥候")) else set()
        thread_id = (event.get("director") or {}).get("threadId")
        location_id = game.get("location")
        for item in player.get("inventory", []):
            bonus = item.get("check_bonuses", {}).get(selected_attribute, 0)
            item_action_tags = set(item.get("actionTags", []))
            item_target_tags = set(item.get("targetTags", []))
            if bonus and ((item_action_tags & action_tags) or (item_target_tags & target_tags)):
                modifiers.append(Modifier("equipment", item["name"], bonus))
        for status in player.get("statuses", []):
            bonus = status.get("modifiers", {}).get(selected_attribute, status.get("modifiers", {}).get("all", 0))
            if bonus:
                modifiers.append(Modifier("status", status["name"], bonus))
        applicable_clues: list[tuple[int, int, str, dict[str, Any]]] = []
        for clue in player.get("clues", []):
            bonus = int(clue.get("bonus", clue.get("modifiers", {}).get(selected_attribute, clue.get("modifiers", {}).get("all", 0))))
            if not bonus or clue.get("ability") not in (None, selected_attribute):
                continue
            score = 0
            if thread_id and clue.get("threadId") == thread_id:
                score += 5
            if set(clue.get("targetTags", [])) & target_tags:
                score += 4
            if set(clue.get("actionTags", [])) & action_tags:
                score += 3
            if event["id"] in clue.get("events", []):
                score += 5
            weak = int(bool(location_id and location_id in clue.get("locationTags", []))) + int(bool(set(clue.get("factionTags", [])) & faction_tags))
            if score == 0 and weak >= 2:
                score = 2
            if score <= 0:
                continue
            duplicate_key = clue.get("dedupeKey") or "|".join(filter(None, [
                str(clue.get("threadId") or ""), str(clue.get("ability") or ""),
                *sorted(str(item) for item in clue.get("targetTags", [])),
            ])) or clue.get("name")
            applicable_clues.append((score, bonus, duplicate_key, clue))
        best_by_type: dict[str, tuple[int, int, str, dict[str, Any]]] = {}
        for candidate in applicable_clues:
            key = candidate[2]
            if key not in best_by_type or candidate[:2] > best_by_type[key][:2]:
                best_by_type[key] = candidate
        for _score, bonus, _key, clue in sorted(best_by_type.values(), key=lambda item: (item[0], item[1]), reverse=True)[:2]:
            modifiers.append(Modifier("clue", clue["name"], bonus))
        for npc_id in choice.get("result", {}).get("relations", {}):
            score = game.get("relationships", {}).get(npc_id, {}).get("score", 0)
            if score >= 10:
                modifiers.append(Modifier("relationship", f"{npc_id} 的信任", min(15, score // 2)))
        context = choice.get("modifiers", [])
        modifiers.extend(Modifier(item.get("source", "context"), item["label"], item["value"], item.get("mode", "percent")) for item in context)
        return CheckRequest(
            event_id=event["id"], event_seed=event.get("event_seed", event["id"]),
            choice_id=choice.get("id", f"choice-{choice_index}"), attribute=selected_attribute,
            ability=player["coreAbilities"][selected_attribute], difficulty=difficulty,
            player_state_version=str(game.get("check_state_version") or game.get("player_state_version", 1)),
            modifiers=modifiers, automatic=choice.get("automatic"),
        )

    def assess_choice(self, event: dict[str, Any], choice: dict[str, Any], game: dict[str, Any], choice_index: int) -> dict[str, Any]:
        """Return an informed, repeatable risk forecast before the player commits."""
        if choice.get("requiresCheck") is False:
            return {
                "requires_check": False, "attribute": None, "attribute_label": "无需检定", "ability": None,
                "difficulty": None, "base_probability": 100, "final_probability": 100,
                "applied_modifiers": [], "primary_trait": max(choice.get("result", {}).get("personality", {"destiny": 1}), key=choice.get("result", {}).get("personality", {"destiny": 1}).get),
                "stat": None, "check": "无需检定", "risk": choice.get("risk", "低"), "forecast": "结果明确",
            }
        request = self._check_request(event, choice, game, choice_index)
        preview = self.check_engine.preview(request)
        chance = preview["final_probability"]
        risk = "低" if request.difficulty <= 6 else "中" if request.difficulty <= 8 else "高" if request.difficulty <= 10 else "致命"
        forecast = "胜算很高" if chance >= 75 else "胜算较高" if chance >= 60 else "成败难料" if chance >= 42 else "胜算较低"
        return {**preview, "primary_trait": max(choice.get("result", {}).get("personality", {"destiny": 1}), key=choice.get("result", {}).get("personality", {"destiny": 1}).get), "stat": request.attribute, "check": preview["attribute_label"], "risk": risk, "forecast": forecast}

    def evaluate_event_outcome(self, event: dict[str, Any], choice: dict[str, Any], game: dict[str, Any], choice_index: int) -> dict[str, Any]:
        """AI-facing structured outcome: reward scale, credible costs, and narrative facts."""
        assessment = self.assess_choice(event, choice, game, choice_index)
        if choice.get("requiresCheck") is False:
            primary = assessment["primary_trait"]
            return {
                **assessment, "code": "success", "label": "自然结果", "tier": "automatic", "roll": None,
                "seed": None, "reward_multiplier": 1.0, "hp_loss": 0, "relationship_factor": 1.0,
                "tradeoff_trait": self.opposing_traits[primary], "tradeoff_loss": 0, "fate_setback": 0,
                "grants_items": True, "setback_text": "",
            }
        checked = self.check_engine.execute(self._check_request(event, choice, game, choice_index))
        roll, code, label, multiplier = checked["roll"], checked["code"], checked["label"], checked["reward_multiplier"]

        damage_table = {
            "日常": {"partial": 2, "failure": 5},
            "NPC": {"partial": 0, "failure": 0},
            "成长": {"partial": 5, "failure": 9},
            "探索": {"partial": 7, "failure": 13},
            "命运": {"partial": 8, "failure": 15},
            "战斗": {"partial": 10, "failure": 18},
        }
        hp_loss = damage_table.get(event["type"], {}).get(code, 0)
        relationship_factor = 1.3 if code == "critical" else 1.0 if code == "success" else 0.35 if code == "partial" else -0.5
        primary = assessment["primary_trait"]
        tradeoff = self.opposing_traits[primary]
        tradeoff_loss = 0 if code == "failure" else 1 if code in {"success", "partial"} else 2
        setback_lines = {
            "partial": "你达成了最初的目的，却没能全身而退。局势留下的伤口提醒你：正确的方向同样可能索取代价。",
            "failure": "现实没有按照你的意图让路。判断中的迟疑与能力上的缺口同时暴露，你只能先承受这个结果。",
        }
        return {
            **assessment, **checked,
            "roll": roll,
            "code": code,
            "label": label,
            "reward_multiplier": multiplier,
            "hp_loss": hp_loss,
            "relationship_factor": relationship_factor,
            "tradeoff_trait": tradeoff,
            "tradeoff_loss": tradeoff_loss,
            "fate_setback": 3 if code == "failure" else 0,
            "grants_items": code in {"critical", "success", "partial"},
            "setback_text": setback_lines.get(code, ""),
        }

    def generate_birth(self, personality: dict[str, int]) -> dict[str, Any]:
        dominant = max(personality, key=personality.get)
        profiles = {
            "peace": ("药草商的孩子", "帕拉斯", "止戈者", "你记得母亲总把最后一碗药留给陌生人。"),
            "power": ("守林人的遗孤", "断风森林边缘", "不屈", "幼时的一场兽潮，让你明白力量也可以用来守护。"),
            "freedom": ("行脚商队的孩子", "艾欧尼亚东部商道", "逐风者", "你的童年没有固定屋檐，只有不断后退的地平线。"),
            "spirit": ("寺庙抄经人的养子", "山间寺庙", "灵息亲和", "你常在梦中听见古树用雨声说话。"),
            "destiny": ("战争难民之后", "战争遗迹附近", "寻命者", "一枚没有文字的旧徽章，是家人留给你的全部线索。"),
        }
        family, region, tag, memory = profiles[dominant]
        name = random.choice(self.names)
        age = random.choice([16, 17, 18])
        story = (
            f"你叫{name}，今年{age}岁。你在{region}长大，是{family}。"
            f"{memory}战争的阴影已远去多年，可土地仍会在夜里低语。"
            "今天清晨，一只白羽鸟停在窗沿，衔来一段刻着陌生纹路的青木枝。"
            "你尚不知道，普通而漫长的一生，正从这一刻偏离旧路。"
        )
        return {"name": name, "age": age, "family": family, "birthplace": region, "childhood": memory, "tags": [tag, "无名者"], "story": story}

    def generate_event(self, template: dict[str, Any], game: dict[str, Any], location: dict[str, Any], *, narrate: bool = True) -> dict[str, Any]:
        event = {**template, "choices": [{**choice} for choice in template["choices"]]}
        authored_scene = template.get("sceneProposal")
        event["title"] = template["title"] if authored_scene else template["title"].format(location=location["name"])
        opening = template["text"] if authored_scene else template["text"].format(name=game["player"]["name"], location=location["name"])
        director = template.get("director", {})
        director_prelude = template.get("directorPrelude", "")
        atmospheres = {
            "pallas": [
                "薄雾还没有从青瓦之间散去，炊烟裹着药草与湿木的气味，沿石路缓慢铺开。",
                "远处的打铁声隔着几重院墙传来，惊起屋檐上的白羽鸟，也让这个寻常早晨多了一丝不安。",
            ],
            "windbreak": [
                "树冠遮住大半天光，苔藓吸走了脚步声。偶尔有幽蓝微光在根系间亮起，像某种生灵半睁的眼睛。",
                "这里的风没有声音，枝叶却在同一时刻偏向更深处。空气里有雨水、树脂，以及一缕不属于森林的铁锈味。",
            ],
            "war_ruins": [
                "断墙把日光切成狭长的碎片，灰尘在其中缓慢浮沉。锈蚀兵刃半埋在野草下，仿佛战争只是短暂睡去。",
                "风穿过空洞箭窗，带来低沉呜咽。每踩碎一片瓦砾，回声都要过很久才肯彻底消失。",
            ],
            "mountain_temple": [
                "云气漫过石阶，檐角铜铃却没有响。松针上的水珠坠入苔痕，让寺院的寂静显得格外清晰。",
                "暮钟的余韵还停在山谷里，香烟从半开的木门逸出，与潮湿的云雾缠在一起。",
            ],
        }
        dominant = max(game["player"]["personality"], key=game["player"]["personality"].get)
        reactions = {
            "peace": "你先留意到的不是危险，而是谁可能因此受伤。这个念头让你没有立刻转身离开。",
            "power": "你下意识调整站姿，确认双脚都踩在可以发力的位置。直觉提醒你，犹豫会让局面落入别人手中。",
            "freedom": "你厌恶被局面推着走，于是先寻找第三条道路——那些没有被任何人说出口的可能。",
            "spirit": "青木枝隔着衣料传来微弱暖意。周围灵息并不平静，像是在等待你给出回应。",
            "destiny": "一种似曾相识的感觉掠过心头。你从未见过眼前这一幕，却隐约觉得它早已在某处等待你。",
        }
        memory_line = ""
        if game["player"].get("memories"):
            memory_line = " 过往的经历在此刻闪回，你明白今天的选择也会成为往后无法抹去的一笔。"
        if authored_scene:
            # NarrativeAuthority has already produced and validated display-ready prose.
            # Observable facts remain structured context and must not be appended again.
            event["text"] = opening
        else:
            event["text"] = "\n\n".join([
                random.choice(atmospheres.get(location["id"], atmospheres["pallas"])),
                director_prelude,
                opening,
                reactions[dominant] + memory_line,
                "没有人替你催促，但局势正在悄然改变。你必须决定，自己愿意为怎样的结果承担代价。",
            ])
        for index, choice in enumerate(event["choices"]):
            choice["assessment"] = self.assess_choice(event, choice, game, index)
        event_temperatures = {"日常": 0.60, "NPC": 0.60, "成长": 0.58, "探索": 0.64, "命运": 0.70, "战斗": 0.55}
        is_boss = bool(event.get("chapter_only"))
        facts = {
                "eventContext": template.get("eventContext"),
                "事件标题": event["title"],
                "事件类型": event["type"],
                "地点": location["name"],
                "当前时间": game.get("season", "未知"),
                "主角称谓": "你",
                "基础事件": opening,
                "Director结构化约束": {
                    "category": director.get("category"), "thread": director.get("threadId"),
                    "stage": director.get("threadStage"), "stageFact": director.get("threadStageLabel"),
                    "intent": director.get("intent"), "intensity": director.get("intensity"),
                    "localConstraint": director_prelude,
                },
                "玩家性格": game["player"]["personality"],
                "已有记忆": game["player"].get("memories", [])[-3:],
                "可选行动": [choice["text"] for choice in event["choices"]],
                "AI现场提案": template.get("sceneProposal"),
                "官方世界观检索": self.lore.context_for_event(location["id"], event["type"], opening),
                "硬性边界": "程序已经决定Thread、Stage、Location、Intent与强度。只扩写这次局部现场，不修改选项，不替你行动，不推进世界阶段，不创造重大世界结果，不提前结算，不描述主角获得、收起或带走任何新物品与线索。",
            }
        if authored_scene:
            game["aiNarratorDebug"] = {
                "phase": "event", "source": template.get("narrativeAuthoritySource", "fallback"),
                "validation": {"valid": True, "errors": []},
                "note": "结构化场景已经是最终正文，未进行第二次事件润色调用。",
            }
        elif narrate:
            event["text"] = self._contract_narrate(
                kind="boss_event" if is_boss else "event", facts=facts, game=game, fallback=event["text"],
                event_type=event["type"], location_id=location["id"],
                temperature=event_temperatures.get(event["type"], 0.62), max_tokens=820 if is_boss else 700,
            )
        else:
            self._contract_narrate(
                kind="event", facts=facts, game=game, fallback=event["text"], event_type=event["type"],
                location_id=location["id"], temperature=0.0, max_tokens=64, remote=False,
            )
        event["narrative_source"] = game.get("aiNarratorDebug", {}).get("source", "local")
        event["eventContext"] = template.get("eventContext")
        return event

    def narrate_event(self, template: dict[str, Any], game: dict[str, Any], location: dict[str, Any]) -> str:
        """Narrate an already-decided event without allowing the model to change facts."""
        return self.generate_event(template, game, location, narrate=True)["text"]

    def stream_event(self, template: dict[str, Any], game: dict[str, Any], location: dict[str, Any]) -> Iterator[str]:
        """Return validated prose; program-owned choices remain outside the model output."""
        if template.get("chapter_only"):
            yield template["text"]
            return
        yield self.generate_event(template, game, location, narrate=True)["text"]

    @staticmethod
    def _json_object(text: str) -> dict[str, Any]:
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned, flags=re.I)
        value = json.loads(cleaned)
        if not isinstance(value, dict):
            raise TypeError("AI结果不是JSON对象")
        return value

    def generate_scene_result(
        self,
        scene: dict[str, Any],
        event: dict[str, Any],
        choice: dict[str, Any],
        game: dict[str, Any],
        location: dict[str, Any],
        outcome: dict[str, Any],
        *,
        revision_feedback: list[str] | None = None,
    ) -> tuple[dict[str, Any] | None, str | None]:
        """Let AI create the concrete local consequence after CheckEngine has ruled."""
        if os.getenv("RUNETERRA_DISABLE_REMOTE_AI") == "1" or not self.remote_ai.configured:
            return None, None
        tier_rules = {
            "critical": "必须产生明显超出预期但仍局限于现场的具体进展。",
            "success": "必须产生能回答玩家目标的有效、具体进展。",
            "partial": "必须同时产生具体进展与一个已经发生的代价或新风险。",
            "failure": "不能达成核心目标，但必须产生一个具体的新情况；不得把失败伪装成成功。",
        }
        schema = {
            "narrative": "第二人称、只写本轮实际发生的具体后果",
            "factsAdded": ["本轮确认并可在下一轮引用的现场事实"],
            "questionsAdded": ["由结果自然产生的新问题"],
            "questionsResolved": ["从当前questions中被本轮明确回答的问题原文"],
            "npcReactions": ["仅限在场人物的具体反应"],
            "actorsAdded": ["可选；仅限由现场已有行动自然确认的在场普通人物"],
            "objectsAdded": ["可选；仅限现场已有事物自然暴露的具体物件或痕迹"],
            "sceneDecision": {
                "continueScene": True,
                "reason": "只供Debug：是否仍有必须现在处理且能产生新决策的问题",
                "nextFocus": "继续时必填；下一轮真正围绕的即时对象或问题",
            },
            "suggestedClue": {"name": "可选；只有具体发现值得长期保留时提出", "ability": "可选能力", "bonus": 5, "targetTags": [], "actionTags": []},
            "suggestedLead": {"title": "可选；由本轮事实自然指向的下一件可追踪事项", "summary": "具体已知信息", "relatedLocations": ["war_ruins"], "threadId": "相关现有WorldThread"},
        }
        try:
            response = self.remote_ai.generate(
                system=(
                    "你是互动RPG的现场结果导演。程序已经完成检定，你只负责决定这个结果在当前现场具体造成了什么。"
                    "严格输出一个JSON对象，不得输出成功率、掷骰、数值变化、Thread Stage、物品奖励或未授权英雄。"
                    "必须引用SceneState中的具体人物、物件、事实与问题；禁止空泛总结、人生感悟和万能套话。"
                    "questionsResolved只能逐字引用输入中的questions。suggestedClue与suggestedLead都只是建议，程序会验证WorldThread、地点和现场关联后决定是否写入。"
                    "每轮必须返回sceneDecision。不要按轮数决定是否继续；只判断当前是否还有必须现在处理且能产生不同决策的问题。"
                    "长期线索不必延长Scene；核心问题已解决且没有即时后果时必须结束。继续时nextFocus必须具体。"
                    "新问题只能来自现场已有的人物、物件、行为、地点或相关World Context的自然后果，不得凭空加入陌生神秘人、组织、神器、敌人、英雄或世界危机。"
                    "若loopGuard.stagnantRounds已经大于0，除非本轮真实产生新的事实或即时问题，否则必须依据现有事实自然收束，不得再制造扩展问题。"
                ),
                prompt=json.dumps({
                    "sceneState": {key: scene.get(key) for key in ("id", "round", "actors", "objects", "facts", "questions", "lastAction", "lastResult", "previousActions", "currentFocus", "loopGuard")},
                    "playerAction": {key: choice.get(key) for key in ("semanticAction", "goal", "approach", "actionTags", "targetTags")},
                    "checkResult": {key: outcome.get(key) for key in ("code", "label", "attribute_label", "risk")},
                    "tierRule": tier_rules[outcome["code"]],
                    "hardFacts": (event.get("eventContext") or {}).get("hardFacts", []),
                    "forbiddenChanges": (event.get("eventContext") or {}).get("forbiddenChanges", []) + [
                        "不得修改世界线程阶段、关系数值、能力值、伤势数值或物品归属",
                        "不得让未在SceneState.actors中的英雄突然出现",
                        "不得杀死受保护角色",
                    ],
                    "revisionFeedback": revision_feedback or [],
                    "outputSchema": schema,
                    "location": location["name"],
                    "playerName": game["player"]["name"],
                    "decisionQuestion": "当前这件事情还有没有一个必须现在处理，并且能够产生新决策的问题？",
                    "safetyClosureRequested": int(scene.get("round", 1)) >= int(scene.get("maxRounds", 4)),
                }, ensure_ascii=False),
                temperature=0.7,
                max_tokens=900,
            )
            return self._json_object(response["text"]), response["text"]
        except (DeepSeekError, json.JSONDecodeError, TypeError, KeyError) as exc:
            return None, str(exc)

    @staticmethod
    def fallback_scene_result(
        scene: dict[str, Any], choice: dict[str, Any], outcome: dict[str, Any], location: dict[str, Any],
    ) -> dict[str, Any]:
        """Concrete offline result whose continuation follows the latest scene reality, not a round target."""
        action = choice.get("semanticAction", choice.get("text", "处理现场"))
        goal = choice.get("goal", "弄清眼前的变化")
        target = (choice.get("targetTags") or scene.get("objects") or ["现场的关键处"])[0]
        actor = (scene.get("actors") or ["在场的人"])[0]
        question = (scene.get("questions") or [f"{target}为何会出现这种变化？"])[0]
        leaving = any(term in action for term in ("离开", "撤离", "不介入", "保持距离"))
        facts_added: list[str] = []
        questions_added: list[str] = []
        questions_resolved: list[str] = []
        reactions: list[str] = []
        actors_added: list[str] = []
        objects_added: list[str] = []
        suggested_clue = None

        if leaving:
            narrative = f"你没有再靠近{target}，而是沿{location['name']}的来路退开。{actor}留在原处，现场的声响很快被距离压低；你保留了已经确认的事实，也明确放弃了此刻继续追查的机会。"
            return {
                "narrative": narrative, "factsAdded": [], "questionsAdded": [], "questionsResolved": [],
                "npcReactions": [f"{actor}没有阻拦你离开。"], "actorsAdded": [], "objectsAdded": [],
                "sceneDecision": {"continueScene": False, "reason": "玩家明确离开现场，当前介入已经结束。", "nextFocus": ""},
                "continueScene": False, "suggestedClue": None,
                "suggestedLead": None,
            }

        current_focus = str(scene.get("currentFocus") or question)
        simple_resolution = any(term in f"{question}{goal}{target}" for term in ("遗失", "布包", "送还", "倒下的货物"))
        trace_action = any(term in f"{action}{goal}" for term in ("痕迹", "脚印", "足迹"))
        approaching_focus = any(term in current_focus for term in ("接近", "来者", "脚步", "现身"))
        footprint_focus = any(term in current_focus for term in ("新鲜脚印", "足迹", "步幅", "脚印的来源"))
        gap_focus = any(term in current_focus for term in ("缝隙", "地下", "裂缝", "冷气"))

        if simple_resolution:
            discovery = f"{actor}认出{target}属于刚刚折返寻找失物的药童，物主与遗失经过已经核实"
            next_question = ""
        elif approaching_focus:
            discovery = "来者只是另一名猎人，他赶来提醒附近山道有危险，并没有追捕在场任何人"
            next_question = ""
        elif gap_focus:
            discovery = "钟座下方的缝隙只通向一条废弃排水槽，冷气来自积水深处，没有东西正在向外逼近"
            next_question = ""
        elif footprint_focus:
            discovery = "新鲜脚印在林缘突然折返，紧接着有一串脚步正沿同一路线向现场靠近"
            next_question = "正在接近的人是谁？"
        elif trace_action:
            discovery = "铜铃附近出现一组新鲜脚印，方向与周围较旧的痕迹相反"
            next_question = "是谁留下了这组方向相反的新鲜脚印？"
        elif "铜钟" in target or "钟座" in target or any("铜钟" in fact for fact in scene.get("facts", [])):
            discovery = "铜钟的震动来自钟座下方一道持续渗出冷气的狭窄缝隙"
            next_question = "钟座下方的缝隙通向什么地方？"
        elif any(term in f"{target}{action}{question}" for term in ("脚步", "竹林", "斥候")):
            discovery = "靠近的两人穿着普通旅衣，但短刃制式与行进间距表明他们是诺克萨斯斥候"
            next_question = "两名斥候正在沿山道寻找什么？"
        else:
            discovery = f"{target}靠近地面的一侧留着一组新鲜痕迹，方向与周围较旧的痕迹相反"
            next_question = "是谁留下了这组方向相反的新鲜脚印？"

        code = outcome["code"]
        if code in {"critical", "success", "partial"}:
            facts_added.append(discovery)
            questions_resolved.append(question)
            if next_question:
                questions_added.append(next_question)
            if footprint_focus:
                objects_added.append("从林缘折返的新鲜脚印")
            if approaching_focus:
                actors_added.append("赶来的猎人")
            suggested_clue = {
                "name": f"关于{target}的新发现", "ability": choice.get("attribute", "perception"), "bonus": 5,
                "targetTags": list(dict.fromkeys(choice.get("targetTags", []) + [target])),
                "actionTags": choice.get("actionTags", []),
            }
        if code == "critical":
            second = f"{actor}确认这些痕迹刚刚出现，并指出了它们继续延伸的方向"
            facts_added.append(second)
            reactions.append(second)
            narrative = f"你沿着{target}逐寸核对，很快排除了旧痕与雨水造成的误差。{discovery}。{actor}顺着你指出的位置重新查看，立即确认了痕迹延伸的方向。"
        elif code == "success":
            reactions.append(f"{actor}按你的判断重新查看{target}，确认这不是原先就有的痕迹。")
            narrative = f"你围绕“{goal}”检查{target}，把新旧痕迹逐一分开。{discovery}。{actor}随后亲自核对了你指出的位置，现场第一次有了可以继续追查的明确方向。"
        elif code == "partial":
            risk = f"{actor}核对时碰落一块碎片，声响惊动了附近尚未现身的人"
            reactions.append(risk)
            questions_added.append("正在接近的人是谁？")
            narrative = f"你确认了一个足以推进调查的事实：{discovery}。但在{actor}俯身核对时，一块碎片突然落下，清脆的声响传出很远；远处随即出现了短促而急促的脚步回应。"
        else:
            if next_question:
                questions_added.append(next_question)
            reactions.append(f"{actor}因你的动作后退一步，不再允许任何人继续靠近{target}。")
            narrative = f"你试图通过{action}来{goal}，但{target}表面的新痕被松动的泥水覆盖，最关键的位置没能看清。{actor}被突然的变化惊得后退，现场随即被隔开；原来的问题没有得到答案，继续靠近也比刚才更困难。"

        if int(scene.get("round", 1)) >= int(scene.get("maxRounds", 4)):
            continue_scene, reason, next_focus = False, "现场达到安全轮数上限，依据已有事实收束，不再引入扩展问题。", ""
        elif code == "partial":
            continue_scene, reason, next_focus = True, "本轮代价制造了正在靠近的即时风险，玩家必须现在作出不同选择。", "正在接近的人"
        elif code == "failure":
            continue_scene, reason, next_focus = False, "行动没有推进核心问题，现场也没有形成可供下一轮处理的新决策空间。", ""
        elif next_question:
            continue_scene = True
            reason = "结果自然留下了一个必须在现场立即处理、并能产生新决策的问题。"
            next_focus = "正在接近的人" if "接近" in next_question else "新鲜脚印的来源" if "脚印" in next_question else "钟座下方的缝隙"
        else:
            continue_scene, reason, next_focus = False, "核心问题已经得到解释，当前没有必须立即处理的危险或互动。", ""
        return {
            "narrative": narrative,
            "factsAdded": facts_added,
            "questionsAdded": list(dict.fromkeys(questions_added)),
            "questionsResolved": list(dict.fromkeys(questions_resolved)),
            "npcReactions": reactions,
            "actorsAdded": actors_added,
            "objectsAdded": objects_added,
            "sceneDecision": {"continueScene": continue_scene, "reason": reason, "nextFocus": next_focus},
            "continueScene": continue_scene,
            "suggestedClue": suggested_clue,
            "suggestedLead": None,
        }

    def generate_resolution(
        self,
        event: dict[str, Any],
        choice: dict[str, Any],
        game: dict[str, Any],
        location: dict[str, Any],
        battle_text: str = "",
        outcome: dict[str, Any] | None = None,
        world_feedback: dict[str, Any] | None = None,
    ) -> str:
        consequence = choice["result"]["text"]
        reflections = {
            "日常": "事情没有惊动更远处的人，可生活正是被这些无人歌颂的选择缓慢改变。",
            "探索": "你重新看向来路，熟悉的地形已经有了不同意义。未知并未减少，只是从恐惧变成了可以追索的线索。",
            "成长": "你重新完成了一遍刚才的动作，身体已经记住最容易出错的位置。",
            "NPC": "对方没有立刻说出所有想法，但停留在你身上的目光已经不同。人与人的关系，往往在话语结束后才真正开始变化。",
            "命运": "风从你身侧越过，像翻动一本看不见的书。某种尚未成形的未来因此变得更近，也有另一些道路悄然远去。",
            "战斗": "当急促的呼吸逐渐平复，你才重新听见周围的风声。胜负只是结果，身体记住的恐惧与判断才是这场交锋留下的东西。",
        }
        text = f"你选择了：{choice['text']}。"
        if outcome:
            if outcome["code"] == "critical":
                text += f"\n\n{consequence} 你的判断与行动几乎没有留下破绽，局面比预想中更彻底地向你倾斜。"
            elif outcome["code"] == "success":
                text += f"\n\n{consequence}"
            elif outcome["code"] == "partial":
                text += f"\n\n{consequence}\n\n{outcome['setback_text']}"
            else:
                failure_details = {
                    "日常": "一个看似微小的环节出了差错。周围人的沉默比责备更明显，你没能把善意变成预期的结果。",
                    "NPC": "对方从你的语气或动作里察觉了不妥。谈话提前结束，尚未建立的信任反而退得更远。",
                    "成长": "你尝试跨过尚未准备好的界限，动作在最关键的一刻失去连续性。",
                    "探索": "环境比判断中更加危险。线索从手边溜走，你不得不在局面彻底失控前撤离。",
                    "命运": "某种力量拒绝了你的回答。短暂显现的道路重新闭合，只留下难以解释的不安。",
                }
                text += f"\n\n{failure_details.get(event['type'], failure_details['探索'])}\n\n{outcome['setback_text']}"
        else:
            text += f"\n\n{consequence}"
        scene = event.get("sceneProposal") or {}
        if scene:
            actors = scene.get("localActors") or ["在场的人"]
            objects = scene.get("localObjects") or ["现场留下的痕迹"]
            actor = actors[0]
            obj = objects[0]
            immediate = scene.get("immediateProblem", "眼前的问题")
            tier = (outcome or {}).get("code", "success")
            followthrough = {
                "critical": f"{actor}顺着你指出的位置重新查看{obj}，很快确认了最关键的一处变化。原本围在旁边的人开始让出空间，{immediate}不再只是无人敢碰的僵局。",
                "success": f"{actor}依照你的判断重新处理{obj}，先前互相冲突的说法终于有了可以核对的次序。{immediate}仍未完全消失，但现场已经知道下一步该做什么。",
                "partial": f"{actor}接受了你指出的方向，却不得不先处理行动留下的代价。{obj}提供了答案的一部分，{immediate}则以另一种形式继续留在现场。",
                "failure": f"{actor}试图接住你未完成的行动，但{obj}附近最关键的变化已经错过。{immediate}没有停止，反而让在场的人更难判断接下来该相信谁。",
                "success_automatic": f"{actor}看着你主动退出眼前争执，没有追赶。{obj}仍留在原处，而{immediate}会在没有你介入的情况下继续发展。",
            }
            key = "success_automatic" if (outcome or {}).get("requires_check") is False else tier
            text += f"\n\n{followthrough.get(key, followthrough['success'])}"
        if battle_text:
            text += f" {battle_text}"
        if world_feedback and world_feedback.get("newPlayableSituation"):
            text += f"\n\n{world_feedback['newPlayableSituation']}这不是对失败的补偿，而是它真正留下、之后仍需面对的麻烦。"
        text += f"\n\n{reflections.get(event['type'], reflections['探索'])}"
        text += f" 此刻，{location['name']}里与这次行动直接相关的人和物都已经有了新的位置。"
        required_outcome = []
        if outcome:
            required_outcome.append(f"结果档位必须表现为：{outcome['label']}")
            if outcome.get("code") == "partial":
                required_outcome.append("玩家达成主要目标，但必须具体表现已经确定的局部代价")
            elif outcome.get("code") == "failure":
                required_outcome.append("玩家没有达成主要目标，并形成一个可继续处理的局部问题")
            if outcome.get("hp_loss"):
                required_outcome.append(f"必须表现身体受到伤害，但不得改变已经确定的伤害量：{outcome['hp_loss']}")
            if outcome.get("grants_items"):
                required_outcome.append("只能表现程序已明确允许获得的物品或线索，不得额外创造奖励")
        if world_feedback and world_feedback.get("newPlayableSituation"):
            required_outcome.append("必须自然形成后续问题：" + world_feedback["newPlayableSituation"])
        facts = {
                "eventContext": event.get("eventContext"),
                "事件": event["title"],
                "地点": location["name"],
                "主角称谓": "你",
                "玩家选择": choice["text"],
                "预设后果": consequence,
                "结算": outcome or {"label": "固定结果"},
                "战斗描述": battle_text,
                "程序已写回的世界反馈": world_feedback or {},
                "Hard Facts": (event.get("eventContext") or {}).get("hardFacts", []),
                "Required Outcome": required_outcome,
                "Forbidden Changes": (event.get("eventContext") or {}).get("forbiddenChanges", []) + [
                    "不得改写结果档位、奖励、关系数值、伤势、物品归属或英雄重大状态",
                    "普通结果不得导致亚索死亡、永久残废、改变阵营或泄露全部秘密",
                ],
                "Creative Freedom": [
                    "自由决定行动过程中的具体动作、声音、对白和空间细节",
                    "自由决定部分成功的代价如何在现场具体发生",
                    "自由决定失败如何演化成符合Required Outcome的局部问题",
                    "自由表现NPC与亚索符合角色卡的反应，但不得越过规则结果",
                ],
                "本地保底叙事": text,
                "官方世界观检索": self.lore.context_for_event(
                    location["id"], event["type"], f"{event['title']} {consequence} {battle_text}"
                ),
                "硬性边界": "必须保持结算方向和代价，不新增补偿，不改变任何数值或物品；除程序事实明确列出外，不描述主角获得、收起或带走任何新物品与线索。",
            }
        return self._contract_narrate(
            kind="resolution", facts=facts, game=game, fallback=text, event_type=event["type"],
            location_id=location["id"], temperature=0.54 if event["type"] == "战斗" else 0.58, max_tokens=620,
        )

    def generate_dialogue(self, npc: dict[str, Any], relationship: dict[str, Any]) -> str:
        score = relationship.get("score", 0)
        memory = relationship.get("memories", [])
        if memory:
            return f"“我记得你。{memory[-1]}”{npc['name']}的语气比上次柔和了些。"
        if score > 10:
            return f"{npc['name']}向你点头：“风把可信的人带回来了。”"
        return f"{npc['name']}打量着你：“陌生人，你想从{npc['job']}这里知道什么？”"

    def generate_battle_text(self, player: dict[str, Any], victory: bool, choice: int) -> str:
        if victory:
            endings = [
                "你没有追击。对手退入雾中，只留下一道被剑风劈开的草痕。",
                "你抓住呼吸之间的空隙，借势卸开兵刃。胜负已经分明。",
                "灵息沿着脚下的根系回应你。下一击落下时，对手失去了战意。",
            ]
        else:
            endings = [
                "你的攻击无法突破敌人的防御。长时间的缠斗让你的脚步渐沉，只能暂时撤离。",
                "敌人的力量超过了你的承受能力。你借倒塌的石墙掩护，才从锋芒下脱身。",
                "你的技巧连续性不足，对手抓住了换气的间隙。好在林雾替你遮住了退路。",
            ]
        return endings[choice % len(endings)]
        return failures[choice]
