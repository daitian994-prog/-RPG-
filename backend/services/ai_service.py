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
        difficulty = choice.get("difficulty", {"日常": 6, "NPC": 7, "成长": 8, "探索": 8, "命运": 9, "战斗": 9}.get(event["type"], 8))
        if event.get("chapter_only"):
            difficulty = 11
        modifiers: list[Modifier] = []
        # Personality describes preferred behavior; it never substitutes for capability.
        body = player.get("bodyCondition", {})
        body_bonus = body.get("modifiers", {}).get(choice.get("attribute", attribute), 0)
        if body_bonus:
            modifiers.append(Modifier("body_condition", body.get("label", "伤势"), body_bonus))
        for trait in player.get("traits", []):
            bonus = trait.get("modifiers", {}).get(choice.get("attribute", attribute), 0)
            if bonus:
                modifiers.append(Modifier("trait", trait.get("name", trait["id"]), bonus))
        for item in player.get("inventory", []):
            bonus = item.get("check_bonuses", {}).get(attribute, 0)
            if bonus:
                modifiers.append(Modifier("equipment", item["name"], bonus))
        for status in player.get("statuses", []):
            bonus = status.get("modifiers", {}).get(attribute, status.get("modifiers", {}).get("all", 0))
            if bonus:
                modifiers.append(Modifier("status", status["name"], bonus))
        for clue in player.get("clues", []):
            bonus = clue.get("modifiers", {}).get(attribute, clue.get("modifiers", {}).get("all", 0))
            if bonus and (not clue.get("events") or event["id"] in clue["events"]):
                modifiers.append(Modifier("clue", clue["name"], bonus))
        for npc_id in choice.get("result", {}).get("relations", {}):
            score = game.get("relationships", {}).get(npc_id, {}).get("score", 0)
            if score >= 10:
                modifiers.append(Modifier("relationship", f"{npc_id} 的信任", min(15, score // 2)))
        context = choice.get("modifiers", [])
        modifiers.extend(Modifier(item.get("source", "context"), item["label"], item["value"], item.get("mode", "percent")) for item in context)
        return CheckRequest(
            event_id=event["id"], event_seed=event.get("event_seed", event["id"]),
            choice_id=choice.get("id", f"choice-{choice_index}"), attribute=choice.get("attribute", attribute),
            ability=player["coreAbilities"][choice.get("attribute", attribute)], difficulty=difficulty,
            player_state_version=str(game.get("check_state_version") or game.get("player_state_version", 1)),
            modifiers=modifiers, automatic=choice.get("automatic"),
        )

    def assess_choice(self, event: dict[str, Any], choice: dict[str, Any], game: dict[str, Any], choice_index: int) -> dict[str, Any]:
        """Return an informed, repeatable risk forecast before the player commits."""
        request = self._check_request(event, choice, game, choice_index)
        preview = self.check_engine.preview(request)
        chance = preview["final_probability"]
        risk = "低" if request.difficulty <= 6 else "中" if request.difficulty <= 8 else "高" if request.difficulty <= 10 else "致命"
        forecast = "胜算很高" if chance >= 75 else "胜算较高" if chance >= 60 else "成败难料" if chance >= 42 else "胜算较低"
        return {**preview, "primary_trait": max(choice.get("result", {}).get("personality", {"destiny": 1}), key=choice.get("result", {}).get("personality", {"destiny": 1}).get), "stat": request.attribute, "check": preview["attribute_label"], "risk": risk, "forecast": forecast}

    def evaluate_event_outcome(self, event: dict[str, Any], choice: dict[str, Any], game: dict[str, Any], choice_index: int) -> dict[str, Any]:
        """AI-facing structured outcome: reward scale, credible costs, and narrative facts."""
        assessment = self.assess_choice(event, choice, game, choice_index)
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
        event["title"] = template["title"].format(location=location["name"])
        opening = template["text"].format(name=game["player"]["name"], location=location["name"])
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
                "官方世界观检索": self.lore.context_for_event(location["id"], event["type"], opening),
                "硬性边界": "程序已经决定Thread、Stage、Location、Intent与强度。只扩写这次局部现场，不修改选项，不替你行动，不推进世界阶段，不创造重大世界结果，不提前结算，不描述主角获得、收起或带走任何新物品与线索。",
            }
        if narrate:
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
        yield self.generate_event(template, game, location, narrate=True)["text"]

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
            "成长": "改变并不剧烈，却真实地留在呼吸与动作之间。下一次面对相似局面时，你知道自己不会再是原来的自己。",
            "NPC": "对方没有立刻说出所有想法，但停留在你身上的目光已经不同。人与人的关系，往往在话语结束后才真正开始变化。",
            "命运": "风从你身侧越过，像翻动一本看不见的书。某种尚未成形的未来因此变得更近，也有另一些道路悄然远去。",
            "战斗": "当急促的呼吸逐渐平复，你才重新听见周围的风声。胜负只是结果，身体记住的恐惧与判断才是这场交锋留下的东西。",
        }
        text = f"你选择了：{choice['text']}。"
        if outcome:
            if outcome["code"] == "critical":
                text += f"\n\n{consequence} 你的判断与行动几乎没有留下破绽，局面比预想中更彻底地向你倾斜。"
            elif outcome["code"] == "success":
                text += f"\n\n{consequence} 过程并不轻松，但结果回应了你的判断。"
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
        if battle_text:
            text += f" {battle_text}"
        text += f"\n\n{reflections.get(event['type'], reflections['探索'])}"
        text += f" 此刻的{location['name']}看起来与片刻前没有区别，但你的道路已经留下新的偏转。"
        text += " 你把当时的声音、气味与每一个迟疑都记了下来，因为未来的某次相逢，或许会要求你再次回答今天的问题。"
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
            return endings[choice]
        failures = [
            "你的攻击无法突破敌人的防御。长时间的缠斗让你的脚步渐沉，只能暂时撤离。",
            "敌人的力量超过了你的承受能力。你借倒塌的石墙掩护，才从锋芒下脱身。",
            "你的技巧连续性不足，对手抓住了换气的间隙。好在林雾替你遮住了退路。",
        ]
        return failures[choice]
