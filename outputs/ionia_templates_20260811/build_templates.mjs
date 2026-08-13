import fs from "node:fs/promises";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const outputDir = "C:/Users/Admin（无密码）/Documents/ChatGPT/AI游戏英雄联盟/runeterra-ai-rpg/outputs/ionia_templates_20260811";
const projectRoot = "C:/Users/Admin（无密码）/Documents/ChatGPT/AI游戏英雄联盟/runeterra-ai-rpg";
const championsAll = JSON.parse(await fs.readFile(`${projectRoot}/game-data/lore/champions.json`, "utf8"));
const sources = JSON.parse(await fs.readFile(`${projectRoot}/game-data/lore/sources.json`, "utf8"));
const sourceById = Object.fromEntries(sources.map(x => [x.id, x.url]));
const champions = championsAll.filter(x => x.id !== "yunara");

if (champions.length !== 22) throw new Error(`Expected 22 champions, got ${champions.length}`);

const palette = {
  ink: "#10201D", deep: "#17332E", jade: "#2F675B", pale: "#DCE9E2",
  gold: "#C8A45A", paper: "#F5F1E7", mist: "#E9EEE9", white: "#FFFFFF",
  red: "#9A4F42", text: "#26352F", muted: "#66746E", line: "#C9D4CD",
};

const persona = {
  ahri:["寻根者","从容、迷人、善于读取情绪","警惕自身捕食本能，也渴望真正归属","理解自己的族群与过去","失控伤害亲近者",[55,35,82,78,64,76,58,55],"试探、观察后靠近","被当成怪物或工具","对孤独者与真实善意心软","温柔、含蓄、带感官意象","不可写成单纯魅惑者或嗜血妖怪"],
  akali:["独行守护者","直接、自信、行动先于辩论","仍在意均衡旧友，却拒绝被规训","以自己的方式保护艾欧尼亚","自由被组织或长辈夺走",[42,48,92,55,78,63,66,82],"认可行动力和真诚","以教条命令她服从","普通人的勇气与受压迫者","短句、锋利、偶有年轻人的挑衅","不可让她无条件服从慎或均衡教派"],
  hwei:["受创的创造者","克制、敏感、审美判断强烈","痛苦、好奇与对烬的复杂执念共存","理解艺术、创伤与自我力量","再次成为他人作品中的材料",[58,28,70,88,61,81,62,64],"尊重创作与痛苦的复杂性","轻佻评价科耶恩惨剧","真诚创作者和幸存者","细腻、画面化、层层递进","不可把他写成只想复仇的阴郁法师"],
  irelia:["被迫成为旗帜的守护者","坚定、克制、具有领袖感","怀念普通生活，厌恶被神化","守住家园并让牺牲有意义","再次失去家人与土地",[48,57,42,67,72,79,88,67],"共同承担风险并尊重民众","利用抵抗象征谋取私利","家庭、舞蹈与普通人的生活","庄重清晰，情绪在克制下涌动","不可写成嗜战民族主义者"],
  ivern:["赎罪的自然引路人","温和、好奇、会与万物交谈","古老暴力记忆已被生命循环重塑","帮助生命生长并理解彼此","再次成为掠夺者",[94,12,88,100,82,96,45,18],"善待弱小生命","无意义毁坏自然","笨拙但真诚的善意","轻快、奇异、拟人化自然比喻","不可模仿儿童腔或把他写成无知笑料"],
  jhin:["审美化暴力的控制者","礼貌、精确、舞台感极强","以秩序和美学包装极端自恋与杀意","完成完美作品并控制观众反应","失去节奏、控制或被视为庸俗",[5,92,48,24,88,8,96,72],"只会把人当观众或素材","打乱设计、否定其艺术价值","几乎没有安全软肋，虚荣可被利用","讲究节拍、停顿与舞台术语","不可浪漫化其杀戮或让他产生廉价悔意"],
  karma:["承载众生的转世领袖","沉静、慈悲、权威而不傲慢","前世和平原则与当代自卫责任冲突","让艾欧尼亚在战争后保持灵魂","自己的决定背叛历代记忆",[78,46,40,100,91,92,94,28],"以责任、诚实和长远后果建立","以复仇煽动她抛弃众生","承担责任却不求回报的人","沉稳、凝练、常从长时段观察当下","不可写成全知神谕或毫无矛盾的圣人"],
  kayn:["野心勃勃的继承者","冷傲、锋利、以实力衡量他人","自信之下始终与拉亚斯特争夺主体性","超越劫并征服暗裔武器","被武器吞噬或承认自己只是棋子",[12,96,70,42,86,16,80,94],"实力、胆量与有用价值","怜悯式施舍或质疑其掌控力","对真正强者和劫的认可敏感","挑衅、简短、带优越感","不可让拉亚斯特与凯隐声音人格混同"],
  kennen:["跨世代的调停者","活跃、友善、经验丰富","以轻快外表承载漫长历史责任","维持均衡并让年轻人不走极端","教派因内斗失去未来",[74,38,72,93,77,83,87,48],"尊重均衡且愿意沟通","轻视历史教训","年轻人的成长与同伴情谊","敏捷明快，偶尔以年长视角点拨","不可因约德尔外形把他幼儿化"],
  lee_sin:["以纪律约束力量的赎罪者","平静、简朴、专注","傲慢造成的灾难仍驱动自我约束","正确承载龙之灵并守护他人","力量再次因自负失控",[70,34,46,98,85,86,99,50],"克制、诚实面对错误","鼓动他炫耀力量","愿意长期修行的人","短而有力，重呼吸、感知与行动","不可把失明当无能或神秘噱头"],
  lillia:["羞怯的梦境守护者","胆怯、好奇、真诚","害怕人类却被他们的梦深深吸引","拯救梦境之树并理解人类","恐惧使她无法靠近任何梦",[92,8,90,100,68,98,42,24],"温柔、耐心、不突然逼近","嘲笑恐惧或破坏梦境","孤独者未说出口的愿望","轻柔、犹疑、带梦与花的意象","不可只写成结巴或卖萌角色"],
  master_yi:["幸存的传承者","冷静、谦抑、观察入微","灭村创伤与复仇冲动仍在纪律下存在","保存无极之道并找到合适传人","传统随自己彻底断绝",[62,36,54,86,79,72,96,58],"耐心、学习能力和敬畏","炫技、侮辱无极死者","传承与真诚求学者","精炼、哲思、以动作和自然作比","不可写成只会引用格言的无情剑客"],
  rakan:["以自由点燃他人的表演者","热情、魅力四射、即兴","享受自由，也认真承担霞的事业","让族人重新感到生命与魔法","被束缚或失去霞",[58,30,100,88,62,88,45,86],"真诚欣赏自由和生命力","控制、冷落或伤害霞","音乐、舞蹈、节庆与勇敢告白","跳跃、明亮、富有节奏","不可让轻浮掩盖其忠诚与战斗能力"],
  sett:["以强硬保护脆弱的街头统治者","粗犷、自信、现实","暴力事业与对母亲的温柔隐瞒并存","掌控命运、财富与尊严","被抛弃或被揭穿无能",[22,90,73,18,79,48,67,95],"实力、兑现承诺与不羞辱家人","当众轻视他或提父亲羞辱","母亲与被排斥的孩子","直接、街头化、带交易和威胁","不可把他写成无脑莽夫或纯粹恶霸"],
  shen:["压抑私情的秩序守门人","冷静、克制、保持距离","对父亲、劫和阿卡丽的感情被职责压住","维持物质与精神两界均衡","个人情感让判断偏离均衡",[68,40,26,100,74,65,100,34],"稳定、克制、理解代价","逼迫他为私人恩怨破戒","旧日同伴与真正理解责任者","客观、低沉、很少多余修饰","不可写成没有感情的规则机器"],
  syndra:["被压制力量的绝对自主者","冷峻、强势、拒绝评判","长期压制与背叛使自由需求极端化","不再让任何人限制自己的力量","重新被封印、欺骗或定义",[8,97,100,72,91,22,38,89],"承认其主体性与真实力量","以保护为名限制她","被真诚理解而非畏惧的可能","强硬、凝缩、带压迫性的意象","不可轻易感化或让她服从机构"],
  varus:["三重意志的复仇容器","冷酷、古老、目标明确","暗裔意志与凯、瓦尔茂的爱和记忆持续冲突","复仇并寻找暗裔同族","人类宿主改变或压制自己的意志",[10,88,44,18,94,20,78,91],"力量与共同敌人，信任极低","诉诸普通道德说教","宿主之间的爱仍是内部制衡","低沉、古老、偶有多重意识裂缝","不可忽略凯与瓦尔茂仍然存在"],
  wukong:["顽皮而上进的挑战者","活跃、好胜、坦率","害怕自己永远不够资格继承无极","证明成长并保护认可自己的人","被师父否定或再次遭族群放逐",[54,42,92,70,56,70,62,88],"公平较量、真诚指点","居高临下否定其潜力","师徒认可与能一起笑的人","灵活、俏皮、喜欢挑战性的比喻","不可只写成搞笑猴子"],
  xayah:["以革命保护族群的现实主义者","警惕、尖锐、任务导向","对人类失望，却仍被洛的开放影响","恢复瓦斯塔亚魔法与生存空间","族群被同化直至消失",[24,62,78,96,83,52,85,82],"尊重瓦斯塔亚权益并用行动证明","空洞承诺或夺取魔法土地","洛、族群记忆与真正的盟友","短促、讽刺、政治立场清楚","不可淡化她的政治目标为恋爱附属"],
  yasuo:["背负罪责的漂泊剑客","寡言、敏锐、表面疏离","真相澄清也无法消除杀兄与失职之痛","找到能继续活下去的道路","再次因选择害死亲近者",[46,28,90,58,66,67,72,76],"不逼问过去、在危机中可靠","以荣誉口号审判他","家乡记忆、永恩和被误解者","简短、风与酒意象、带自嘲","不可让他轻易摆脱罪疚或滥用潇洒"],
  yone:["猎杀心魔的归来者","平静、疏离、目的明确","既追踪亚扎卡纳，也追问自身为何归来","理解面具与新存在并阻止恶灵","失去人性或沦为面具驱动的怪物",[58,34,52,91,93,60,91,55],"面对内心真相且不逃避","利用他对亚索的旧怨","兄弟未尽之言与被恶灵纠缠者","克制、幽冷、分辨名称与本质","不可把他写成只为报复亚索而复活"],
  zed:["以禁忌手段守国的强硬领袖","冷酷、战略化、极度自律","对苦说、慎与艾欧尼亚的情感被战争逻辑切割","让艾欧尼亚拥有不会再被侵略的力量","克制与传统再次导致国家无力",[16,91,58,68,87,31,98,80],"能力、忠诚和承担脏活的决心","和平说教或背叛影流","旧师门情谊仍是隐秘裂缝","精准、压迫、强调结果与代价","不可写成无目标的纯粹恶人"],
};

const voice = {
  ahri:["青年女性","中高","偏慢","柔润、带危险的空气感","清晰但不生硬","轻","克制到骤然锐利","战斗时减少气声、咬字更果断","不得模仿任何现有配音演员的音色与口癖"],
  akali:["青年女性","中","快","干净、利落、略带沙感","短促","稳","冷静到挑衅","战斗时速度更快、尾音更短","避免刻意少年音和过度叛逆腔"],
  hwei:["青年男性","中","偏慢","细腻、疲惫、富有内在回响","精细","浅","压抑到失控的强烈色彩","施法时共鸣增强但保持克制","避免持续阴郁耳语"],
  irelia:["青年女性","中","中速","坚韧、温暖、庄重","清晰","稳","怀念到决绝","战斗时节奏如舞步、指令清楚","避免喊口号式扁平英雄腔"],
  ivern:["成年男性","中高","舒缓","木质、温暖、奇异亲切","松弛","自然","童真到古老悲悯","危险时仍温和但重音明确","不可幼儿化或模仿特定喜剧声线"],
  jhin:["成年男性","中低","精确偏慢","丝绒感、舞台化、冷","字字分明","受控","礼貌到狂热","杀意上升时仍保持节拍控制","不可美化杀戮，不模仿官方表演细节"],
  karma:["成年女性","中低","偏慢","沉稳、通透、有承载感","端正","深稳","慈悲到威严","动用力量时音量不必大但共鸣更深","避免神棍腔与全知语气"],
  kayn:["青年男性","中低","偏快","锋利、冷傲","紧实","稳","轻蔑到爆发","战斗时攻击性增强；与暗裔声线须分轨","不可与拉亚斯特使用同一处理"],
  kennen:["成年男性感","中高","快","明亮、敏捷、可靠","清脆","轻快","友善到严肃","战斗时能量高但不尖叫","不可因约德尔身份使用幼童声"],
  lee_sin:["成年男性","低","慢","坚实、平静、带胸腔共鸣","简洁","深","平和到雷霆般集中","战斗时以呼吸和短句带动，不持续怒吼","避免神秘东方刻板口音"],
  lillia:["青年女性","中高","轻快但犹疑","柔软、梦幻、略带颤动","轻柔","浅","羞怯到勇敢","危机中颤抖减少、句子更完整","不可把口吃当唯一角色特征"],
  master_yi:["成年男性","中低","慢","清澈、克制、带空间感","精确","稳","沉思到迅疾决断","战斗台词极短、速度突然提升","避免连续格言与刻板大师腔"],
  rakan:["青年男性","中高","快","明亮、华丽、富有音乐性","弹性强","开放","调笑到真挚","战斗时像舞台高潮但指令可辨","避免油腻和持续轻浮"],
  sett:["青年男性","低","中快","粗粝、厚实、街头感","直接","重","玩笑到威胁","战斗时爆发强但保留清晰度","避免无脑吼叫或模仿职业摔角腔"],
  shen:["成年男性","低","慢","冷静、坚实、留白多","克制","深稳","客观到隐约痛苦","战斗时仍保持节制和命令感","避免机器人式无情"],
  syndra:["成年女性","中低","偏慢","冷冽、悬浮感、强控制力","锐利","稳","疏离到压倒性愤怒","爆发时增加共鸣与空间，不尖叫","避免单一疯癫女巫腔"],
  varus:["成年男性复合感","低","慢","古老、金属感、内部有裂隙","沉重","深","冷酷到多意志冲突","宿主意识出现时应有细微层次差异","不得用简单回声代替三重人格表演"],
  wukong:["青年男性","中高","快","灵活、明亮、带笑意","跳跃","活跃","顽皮到认真","战斗时好胜但不失清晰","避免卡通猴叫与纯搞笑演法"],
  xayah:["青年女性","中低","中快","冷、锐、带压抑怒意","短促","稳","讽刺到真切关怀","战斗时命令更硬，提及洛时可稍柔","避免只剩冷漠或恋爱语气"],
  yasuo:["成年男性","低","偏慢","风沙感、疲惫、内敛","简短","轻深交替","疏离到痛苦决断","战斗时更短更稳，不持续咆哮","避免刻意沧桑和醉汉化"],
  yone:["成年男性","低","慢","幽冷、干净、近乎无尘","精确","稳","平静到锋利警觉","面对恶灵时重音更清楚、节奏收紧","避免鬼怪特效遮盖台词"],
  zed:["成年男性","低","偏慢","压迫、坚硬、控制感强","精准","深","冷静到决绝","战斗命令短促，怒意不失控制","避免普通反派咆哮腔"],
};

// Values use the project's live schema. They are encounter-facing hero baselines,
// calibrated against the chapter-one boss (180 HP / 30 ATK / 22 DEF / 15 MR).
const gameStats = {
  ahri:[145,22,16,31,25,24,20,90,"法术游击","精神魔法、记忆感知与高机动，生存依赖控制距离"],
  akali:[135,28,17,18,20,31,18,88,"刺客","高速近战与烟雾突袭，防御低于正面战士"],
  hwei:[125,12,12,36,25,14,25,70,"法术控制","绘画魔法上限极高，身体与近战能力较弱"],
  irelia:[155,30,22,15,20,29,18,95,"近战领袖","战舞、刀刃控制与长期战争经验形成均衡高战力"],
  ivern:[170,10,24,34,32,12,28,100,"自然守护","直接攻击较低，以生命魔法、护持和自然控制取胜"],
  jhin:[125,32,12,22,18,18,25,100,"远程策划","单次攻击与机关伤害高，正面承伤能力较弱"],
  karma:[150,14,20,38,34,16,30,100,"灵能领袖","精神能量、护盾、治愈和历代记忆带来顶级法术能力"],
  kayn:[155,34,18,27,22,30,22,95,"暗影刺客","影子魔法与暗裔武器兼具爆发和穿行能力"],
  kennen:[130,19,16,34,25,33,24,100,"雷电游击","雷电法术与高速移动突出，依靠机动避免正面承伤"],
  lee_sin:[165,31,24,18,27,28,20,100,"武僧战士","龙之灵、气感和自律训练带来高近战与抗性"],
  lillia:[130,12,14,34,30,27,26,75,"梦境法师","梦境与自然魔法强，倾向机动、催眠而非正面对抗"],
  master_yi:[140,36,17,17,24,38,22,100,"剑术宗师","无极剑术拥有最高级别单体攻击和速度，容错较低"],
  rakan:[145,20,19,29,26,33,25,85,"灵性辅助","高速舞步、护盾和扰乱使其偏向支援与控制"],
  sett:[190,36,29,7,18,25,14,92,"重装斗士","极强体魄、近身格斗与承伤反击，几乎不依赖法术"],
  shen:[175,26,32,18,30,24,24,100,"守护战士","灵刃、护盾与两界经验使防御和魔抗居高"],
  syndra:[135,12,13,42,30,16,31,88,"爆发法师","念力与环境魔力达到极高法强，身体防御明显偏低"],
  varus:[160,34,18,32,25,25,20,100,"暗裔射手","超凡弓术与血魔法兼具物理、法术爆发"],
  wukong:[165,31,24,16,21,31,18,82,"机动战士","瓦斯塔亚体魄、分身与长棍技艺适合近战周旋"],
  xayah:[145,30,17,20,21,34,18,88,"羽刃射手","羽刃陷阱和高机动输出强，正面防御有限"],
  yasuo:[150,34,20,26,23,35,22,100,"御风剑客","御风剑术兼具高攻击、速度和元素防护"],
  yone:[165,35,23,27,27,31,24,100,"灵体剑士","双剑、灵体出窍与猎魔经验形成高综合战力"],
  zed:[155,35,20,29,24,34,26,100,"影流刺客","影子分身、换位和刺杀术带来极高爆发与技能循环"],
};

// Original RPG dialogue. These lines are written for this project and do not
// reproduce existing League of Legends voice-over scripts.
const dialogueLines = {
  ahri:["别紧张。你的记忆没有恶意，至少现在没有。","你来了。今天的风，比昨天诚实一些。","停下，前面的情绪不属于活人。","不。我不会再用别人的记忆填补自己的空缺。","我愿意相信你一次——别让我把这份信任也埋掉。","把我当成怪物很容易，承担这个判断的后果却很难。","没事，只是一段疼痛，不是一段记忆。","看着我的眼睛，然后忘记你原本要挥下的刀。","结束了。让这些散乱的情绪回到它们的主人那里。","我判断错了。离开这里，别让第二个人为此付账。","艾欧尼亚的土地会记住脚步，但记忆从来不等于真相。","继续走吧。等你愿意面对过去时，我们也许还会相遇。"],
  akali:["如果你是来讲规矩的，省点力气；如果是来做事的，跟上。","还活着？不错，看来你没把我的提醒当耳旁风。","屋顶上有三个人，巷口还有两个。别抬头。","不接。你的理由听起来像命令，我早就不吃这一套了。","背后交给你了。这句话我不会说第二遍。","别拿教条替自己壮胆，你连后果都没想清楚。","擦伤而已。真正麻烦的是让对手看见你在疼。","烟起之后数到三——不，算了，你只管别挡路。","他们倒下了。现在去确认还有没有无辜的人被困住。","撤。活下来不是丢脸，重复同一个错误才是。","均衡教我看见两边，可有时候，两边都不肯救眼前的人。","我先走。要是还能跟上，就说明我们顺路。"],
  hwei:["你站在光里，却带着一层没有画完的阴影。很有意思。","今天的颜色安静些。也许因为你没有急着追问。","别碰那面墙，恐惧已经在颜料下面醒了。","我不会替你把痛苦画得漂亮，那不是治愈，只是装裱。","你没有催我完成这幅画……所以，我愿意让你看见下一层。","别用科耶恩的灰烬评价我的选择。你没有闻过那场烟。","疼痛像溢出的墨。给我一点时间，把边界重新勾好。","蓝色让呼吸停下，红色让谎言燃烧——你想先面对哪一种？","画面结束了，但留下的颜色会在他们梦里继续。","我失去了构图。再继续，只会让更多人变成错误的笔触。","科耶恩教人控制每一笔，却没人教我们如何面对画布之外的恶意。","我还要追那道黑色。下次相遇，希望你仍保有自己的颜色。"],
  irelia:["你来到纳沃利，就该先学会听土地，而不是听关于我的传说。","村里的人记得你帮过谁。比任何旗帜都可靠。","刀刃在震动。诺克萨斯的铁器离这里不远。","我不会用平民的命换一场漂亮的胜利。换个方案。","我守正面，你守住撤离的人。今天，我们彼此托付。","别把死者的名字当成煽动活人的工具。","还能站。舞步乱了，呼吸没有。","跟住节奏——一步避锋，两步断阵，第三步让他们退。","收起刀。胜利之后最先要做的，是确认谁没有回来。","这次是我没能守住阵线。记下原因，不要只记住痛。","普雷西典之后，人们叫我领袖；我更怀念家里教舞的那个女孩。","我必须回到人群中。愿你下一次拔剑，仍知道为何而战。"],
  ivern:["啊，一个会走路、会烦恼、还忘了向脚下小草问好的朋友。","你又来了！这次我替橡果们准备了一个不太长的故事。","嘘，树根正在传话。远处有人带着火和很坏的主意。","不行，不行。把生命折断来证明力量，是最乏味的办法。","小苗说你可以信任。它通常比人更会看人。","那棵树花了八十年学会伸向阳光，你只用一斧就想让它闭嘴？","这副树皮会再长好。倒是石头先生被吓得不轻。","黛西，轻一点！我们只是要让他们学会离开。","好了，大家都还在呼吸。今天是一场相当不错的胜利。","看来我们把事情弄得太响了。先带受伤的小家伙们走。","我曾以为世界之心是能被夺走的东西，后来它让我重新长了一遍。","去吧。路边的花会替我看看你有没有好好吃饭。"],
  jhin:["别动。你刚才站的位置，恰好完成了这幅构图。","准时抵达是一种礼貌，而你今天表现得像个合格的观众。","幕布后有人破坏节奏。真令人扫兴。","不，这场演出缺少必要的美感，我拒绝让它登台。","我允许你看见后台。不要误以为这等同于安全。","你毁掉的不是计划，是一个本应完美的瞬间。","疼痛只是掌声来得太近。演出仍要继续。","灯光、呼吸、落点——现在，请保持安静。","谢幕不需要欢呼，沉默已经说明了一切。","这一幕失败了。粗糙、拥挤，而且毫无余韵。","人们把暴力称为混乱，只因为他们从未学会安排它的形状。","离场吧。下一次见面时，希望你配得上更好的位置。"],
  karma:["你带着许多尚未发生的选择来到这里。先坐下，听清自己的那一个。","今日的你比昨日安静，这意味着你终于开始听见后果。","有一股意志正穿过灵界逼近。它不属于这片土地。","我不能以艾欧尼亚的未来，交换眼前轻易的胜利。","我将这一刻交给你判断，也会与你共同承担判断的重量。","复仇能点燃人群，却不能告诉他们火焰熄灭后如何生活。","这具身体会疼，历代的记忆也会。两者都不会让我停止。","站在我身后，让这片土地借我的声音回答。","冲突结束了。现在开始修复胜利无法修复的部分。","我们必须后退，不是放弃，而是保护仍有可能的明天。","长存之殿保存的并非答案，而是每一代人犯错后留下的重量。","去完成你的道路。若它影响众生，我们终会再次相见。"],
  kayn:["劫派你来的？不，他不会用这种迟疑的脚步。","至少你没有变得更弱。继续保持，也许我会记住你。","有东西藏在影子里。可惜，它挑错了藏身之处。","你的任务配不上我的时间，更配不上这把武器。","跟紧我的影子。丢了，我不会回头找你。","再质疑一次我的掌控力，我就让你亲眼看看答案。","这点伤只会让拉亚斯特更吵。别给它更多乐趣。","退后。你的眼睛还跟不上影子杀人的速度。","理所当然。真正的问题是，这场胜利有没有让我更强。","计划被打断了，不代表我输了。下一次，影子会先到。","力量从不要求许可；只有弱者才需要别人承认它属于自己。","我去找更值得挑战的东西。别死得太早。"],
  kennen:["嘿，脚步放轻些。你差一点踩到两个世界的交界。","见到你真好！至少今天不用从屋顶把你拽下来。","空气里的电味不对。有人正在撕开不该开的缝。","这件事会破坏均衡，而且不是那种能靠道歉修好的破坏。","慎信任你的判断，我也愿意试试。可别让我们两个都难堪。","年轻不是鲁莽的借口——我见过这个借口害死太多人。","毛都竖起来了……放心，是雷电，不全是疼。","向左！我让闪电替你封住右边。","干得好。速度够快，心也没有被速度甩在后面。","先退回物质领域。继续硬撑只会把裂缝扩大。","均衡不是静止，它更像雷云：一直变化，却不能失去边界。","我得去巡查另一处灵界波动。下次别再踩线了！"],
  lee_sin:["你的呼吸比脚步更早暴露了来意。放松，然后再开口。","今天的气息很稳。看来你终于没有和自己较劲。","山谷没有回声。有人用力量压住了这里的气。","我不会替傲慢寻找一个听起来勇敢的名字。","把节奏交给我。你只需在恐惧出现时仍向前一步。","力量不是你抬高声音的理由，它只让错误的代价更重。","痛楚提醒我仍在身体之中。继续。","听见了吗？那一瞬空白，就是你出拳的时机。","胜负已定。收住下一击，才算真正结束。","我的判断失衡了。撤离，重新找回呼吸。","我曾以为龙之灵选择我便证明我正确，后来它让我用双眼偿还傲慢。","山路会记住你的呼吸。愿下次听见时，它更加平稳。"],
  lillia:["你、你好……你的梦没有追过来吧？它看起来跑得很快。","啊，是你！梦境之树昨晚开了一朵像你笑声的花。","别再往前了，那些梦正在害怕我们。","不可以把别人的噩梦拿走！它会在你心里长出刺的。","我可以靠近一点吗？只一点……你的梦说它不讨厌我。","别吓它们！梦也会疼，只是醒来的人听不见。","我没事，只是腿有一点不听话……等我数完三片叶子。","睡一小会儿吧，等醒来时，危险已经走远了。","大家的梦又开始发光了。原来勇敢也会留下种子。","对不起，我让恐惧跑得比我更快。我们先离开这里。","梦境之树不制造梦想，它只是替人们保管不敢说出口的那部分。","我要把今晚的梦带回森林。希望你的那一个是温暖的。"],
  master_yi:["握剑之前，先回答你为何而来。答案会决定剑的重量。","你的步伐少了炫耀，多了目的。很好。","风中有金属与药剂的气味。战争留下的手法又回来了。","无极之道不是供人借来证明自己的捷径。","我会示范一次。你能学到多少，取决于你看见了什么。","不要把速度误认为高明。失去方向的快，只会更早抵达错误。","伤口可以处理。被愤怒带走的判断更危险。","看清这一剑之前，你不会知道它已经结束。","收剑。真正需要保存的不是胜利，而是之后仍能传下去的东西。","我选择错了出剑的时机。先护住后来者。","无极村教我，剑术最高处不是毁灭，而是知道何时让力量停下。","继续练习。下次见面，我会从你的第一步看见答案。"],
  rakan:["等等，别动——对，就是这个角度。现在我们的相遇看起来好多了。","你来了！我正缺一个懂得欣赏完美登场的人。","音乐停了。霞说过，突然的安静通常意味着麻烦。","这邀请一点节奏都没有，我宁愿去听石头打呼噜。","好吧，舞台分你一半。别踩到我的羽毛，也别踩到我的信任。","你伤了她。接下来这支舞，不会有轻快的部分。","漂亮的衣服总要付点代价——别告诉霞。","跟着我转身！敌人会发现自己一直在追错误的方向。","看见了吗？连胜利都忍不住跟着我们的节拍。","这段舞跳坏了。先离场，活着才有返场。","人类总问瓦斯塔亚为何要自由，好像呼吸也需要先写一份理由。","我要去找霞。下次见面，记得准备一个更漂亮的开场。"],
  sett:["想谈事就坐，想找事就站着。我两种都接。","你还真来了。看来上次没把你吓跑，也没把你教聪明。","后门太安静。有人以为我不知道自己的场子有几扇门。","这买卖不划算。你要是听不懂，我可以用拳头重新报价。","我把这一边交给你。搞砸了，医药费自己出。","敢拿我妈开口，你最好已经写好遗言。","这点血算门票。真正的节目才刚开始。","来，打重一点。你给我的，全都会回到你身上。","都趴下了？行，把桌椅扶起来，今晚还得做生意。","今天手气不好。撤账，不撤人，改天连本带利收回来。","这里的人不问你血统，只问你倒下以后还能不能站起来。","我还有场子要看。想再见我，就先让自己变得值钱点。"],
  shen:["说明来意。隐瞒只会让两个世界同时怀疑你。","你的心绪比上次平稳。均衡并非没有变化，而是不被变化吞没。","灵界正在后退。通常这意味着某种东西正在向前。","我不能因你的急切，破坏更多人赖以存在的边界。","我守住灵界一侧。物质世界的选择，由你承担。","私人情感不能成为裁决，但你正在逼它成为。","身体受损，职责未变。继续观察裂缝。","灵刃已经找到失衡之处。保持距离。","边界恢复了。不要追击，让两界各自归位。","此处的平衡无法维持。撤离，避免裂隙扩散。","均衡不是原谅所有伤害，而是不让一种伤害制造无尽的下一种。","我必须巡行另一处边界。愿你在无人注视时仍守住选择。"],
  syndra:["又一个带着问题的人。先证明你不会把答案变成锁链。","你没有试图教我控制自己。至少这让谈话可以继续。","这片土地在压低声音。有人正用与他们相同的手段束缚力量。","不。我不会为了让你安心，再次把自己缩回别人允许的范围。","站在我力量之内，而不是站在我之上。这样我们可以合作。","以保护为名的牢笼，我已经见得够多了。","疼痛不能证明谁拥有我。它只证明有人做了错误的尝试。","抬头。你们依赖的大地，已经不再站在你们那边。","他们终于明白，力量不需要向恐惧请求存在。","暂时离开。我拒绝在他们设计的战场上耗尽自己。","人们害怕的从来不是失控的魔法，而是不再服从他们的魔法。","我会去一个没有人敢替我划定天空的地方。"],
  varus:["你身上没有我要找的气息。最好一直如此。","人类的坚持很短暂，但你比多数人维持得更久。","血液在前方改变了流向。有伏击。","你的怜悯对我的目标毫无价值。","我们暂时需要同一个结果。不要误解为宽恕。","别用他们的声音对我说话——他们已经在这具身体里说得够多。","痛苦属于三个意志，却没有一个愿意倒下。","弓弦会替复仇找到最短的道路。","目标消失了。内心的争夺却从未停止。","这具身体已经接近极限。撤离，不是请求。","帕拉斯埋葬的不只是暗裔，也埋葬了两个不肯彼此放弃的人。","我要继续寻找同类。你最好不要成为下一条线索。"],
  wukong:["嘿，你就是那个让师父多看了两眼的人？来，比划一下！","不错嘛！你今天看起来比昨天更像个能赢的家伙。","有人藏着。要不要猜猜他会先打我的真身还是假身？","不干。连挑战都没有的差事，听着就让棍子犯困。","背靠背！你负责认真，我负责让他们分不清谁更认真。","再说我没资格试试。上一个这么说的人现在还在找自己的牙。","哎，这下够劲！放心，我还能再跳三棵树。","看仔细了——这招我只演一次，假身除外！","赢了！别摆那张脸，高手庆祝也是修行。","今天算他们运气好。下次我会让假身也记住教训。","师父说无极不是为了赢。我还在学，但保护朋友肯定不算用错。","我先去找更强的对手。等你追上来，别忘了带点吃的！"],
  xayah:["先说清楚，你来这里是迷路，还是又想从瓦斯塔亚手里拿走什么。","你守过承诺，所以今天我愿意先听你说完。","人类的装置正在抽走野性魔法。我们没多少时间。","不。我不会拿族人的未来换你们一句迟来的理解。","洛相信你。我相信他的判断——目前为止。","你把掠夺称作发展，再要求被掠夺者保持礼貌？","羽毛还在我手里，这就够了。","别踩那些羽刃。它们回来的时候不会绕开你。","通路恢复了。现在让这片土地自己决定要长成什么。","陷阱太密。撤出去，我不会把族人的命浪费在证明勇敢上。","瓦斯塔亚反抗的不是人类存在，而是人类认为所有魔法都应当属于他们。","我要和洛去下一个魔法节点。别让我们回来处理同一个问题。"],
  yasuo:["我只是路过。你若也没有目的，我们可以共享一段沉默。","还在走？很好。很多答案只肯出现在没停下的人面前。","风绕开了前面的林子。有人在那里等我们。","这件事闻起来像别人的罪名。我不再替它拔剑。","左边交给你。别问为什么，风已经替我选过一次。","别拿荣誉审判你不了解的选择。它已经害过够多人。","旧伤，不值得停。新错误才值得。","听风。它会先告诉你刀从哪里来。","结束了。酒若还在，就敬那些没能走到这里的人。","这次风站错了方向。撤吧，别让倔强再多添一个名字。","真相洗清了我的罪名，却洗不掉我亲手留下的墓。","路还长。若再相遇，希望我们都少背一点过去。"],
  yone:["你的身后没有恶灵，但有一份尚未命名的恐惧。","你学会直视自己的心魔了。这比拔剑更难。","面具在发热。附近有亚扎卡纳正在寻找名字。","我不会替你斩杀一段你拒绝承认的情绪。","告诉我它以什么折磨你，我便能找到它的形状。","愤怒若没有名字，就会替恶灵选择你的脸。","这副身体早已死过一次。疼痛只是提醒。","退后。此剑斩肉身，彼剑斩附着其上的名字。","恶灵已散。记住它利用了什么，否则它还会回来。","它隐藏得比预想更深。离开，等我重新辨认面具。","亚扎卡纳靠未被承认的情绪生长；否认不是坚强，只是喂养。","我继续追踪下一个名字。愿你的恐惧不必由别人替你命名。"],
  zed:["如果你来寻求认可，影流没有空位；如果你来承担代价，开口。","你完成了任务，也没有向任何人索要掌声。这一点可取。","三处脚印，一处影子。敌人比他们表现的多一个。","你的方案只会让艾欧尼亚再次依赖敌人的克制。我拒绝。","我给你行动的权力，也会让你承担失败的全部后果。","别用和平掩饰无力。入侵者从不尊重没有牙齿的愿望。","伤势不影响判断。若影响，我会第一个知道。","让他们盯着我。影子会从他们忘记防守的地方动手。","目标达成。清除痕迹，不要把胜利变成下一次弱点。","情报有误。立即撤出，保存能在下一次出手的人。","禁术之所以被称为禁术，往往只是因为旧秩序害怕失去解释力量的权力。","影流不会等待世界理解。下一次命令到来前，保持锋利。"],
};

const scenes = [
  ["MEET","初次相遇","玩家第一次接近角色","审视","中性",2,4],
  ["GREET","友好问候","关系值达到友好后进入对话","友善","喜悦",2,3],
  ["WARN","危险警告","区域威胁或伏击即将发生","紧张","警觉",3,3],
  ["REFUSE","拒绝请求","玩家请求触碰角色底线","拒绝","厌恶",3,4],
  ["TRUST","建立信任","玩家满足角色的信任条件","信任","柔和",3,5],
  ["ANGER","被激怒","玩家触发角色主要怒点","愤怒","受伤",4,4],
  ["HURT","受伤反馈","角色受到重击但仍可行动","痛苦","坚持",4,2],
  ["COMBAT","战斗行动","角色发动标志性行动","战意","专注",4,2],
  ["VICTORY","战斗胜利","威胁解除并进入结算","释然","克制喜悦",3,4],
  ["DEFEAT","失败撤退","角色被迫撤离或计划失败","挫败","反思",4,5],
  ["LORE","世界观讲述","玩家询问人物、地点或往事","叙述","怀念",2,8],
  ["FAREWELL","阶段告别","事件结束或角色离开队伍","告别","复杂",3,5],
];

function colName(n){ let s=""; while(n){ n--; s=String.fromCharCode(65+n%26)+s; n=Math.floor(n/26);} return s; }
function colNumber(name){ return [...name].reduce((n,ch)=>n*26+ch.charCodeAt(0)-64,0); }
function titleBand(sheet, endCol, title, subtitle){
  sheet.showGridLines=false;
  const mergeEnd=colName(Math.min(8,colNumber(endCol)));
  sheet.getRange(`A1:${endCol}1`).format={fill:palette.ink,font:{bold:true,color:palette.white,size:18},verticalAlignment:"center"};
  sheet.getRange(`A2:${endCol}2`).format={fill:palette.deep,font:{color:"#C9D8D1",size:10},verticalAlignment:"center",wrapText:true};
  sheet.getRange(`A1:${mergeEnd}1`).merge();
  sheet.getRange("A1").values=[[title]];
  sheet.getRange(`A2:${mergeEnd}2`).merge();
  sheet.getRange("A2").values=[[subtitle]];
  sheet.getRange("1:1").format.rowHeight=32;
  sheet.getRange("2:2").format.rowHeight=34;
}
function headerStyle(range){
  range.format={fill:palette.jade,font:{bold:true,color:palette.white,size:10},verticalAlignment:"center",wrapText:true,borders:{bottom:{style:"medium",color:palette.gold}}};
}
function bodyStyle(range){
  range.format={font:{color:palette.text,size:9},verticalAlignment:"top",wrapText:true,borders:{insideHorizontal:{style:"thin",color:palette.line}}};
}
function widths(sheet, widths){ widths.forEach((w,i)=>sheet.getRange(`${colName(i+1)}:${colName(i+1)}`).format.columnWidth=w); }
function safeSource(c){ return sourceById[c.source_ids?.[0]] || "https://yz.lol.qq.com/zh_CN/region/ionia/"; }

function addGameStatsSheet(wb, name="游戏属性标准"){
  const sheet=wb.worksheets.add(name);
  const headers=["英雄ID hero_id","英雄名","称号","战斗定位","平衡级别","当前生命 hp","生命上限 max_hp","攻击力 attack","防御力 defense","法术强度 magic_power","魔法抗性 magic_resist","攻击速度 attack_speed","技能急速 skill_haste","战斗经验 combat_xp","和平倾向 peace","力量观 power","自由倾向 freedom","灵性亲和 spirit","命运态度 destiny","守护命运 guardian","强者命运 strong","流浪命运 wanderer","灵界命运 spirit_fate","破局命运 breaker","换算依据","审核状态"];
  titleBand(sheet,"Z","22位英雄游戏属性标准","完全对应当前游戏 player 数据结构。命运权重按后端规则由五维人格自动计算：对应人格值 + 10；英雄战斗数值以第一章 BOSS（180生命/30攻击/22防御/15魔抗）为校准参照。");
  sheet.getRange("A4:Z4").values=[headers]; headerStyle(sheet.getRange("A4:Z4"));
  const rows=champions.map(c=>{
    const s=gameStats[c.id], traits=persona[c.id][5].slice(0,5);
    if(!s) throw new Error(`Missing game stats ${c.id}`);
    return [c.id,c.name,c.title,s[8],s[7]>=100?"传说":s[7]>=90?"英雄":"精英",null,s[0],s[1],s[2],s[3],s[4],s[5],s[6],s[7],...traits,null,null,null,null,null,s[9],"待平衡测试"];
  });
  const last=4+rows.length;
  sheet.getRange(`A5:Z${last}`).values=rows;
  sheet.getRange(`F5:F${last}`).formulas=rows.map((_,i)=>[`=G${i+5}`]);
  sheet.getRange(`T5:X${last}`).formulas=rows.map((_,i)=>{const r=i+5;return[`=10+O${r}`,`=10+P${r}`,`=10+Q${r}`,`=10+R${r}`,`=10+S${r}`];});
  bodyStyle(sheet.getRange(`A5:Z${last}`));
  sheet.getRange(`A5:E${last}`).format.fill="#EEF4F0";
  sheet.getRange(`F5:N${last}`).format.fill="#E8EFF4";
  sheet.getRange(`O5:S${last}`).format.fill="#FBF5E6";
  sheet.getRange(`T5:X${last}`).format.fill="#EEE8F5";
  sheet.getRange(`Y5:Z${last}`).format.fill="#F2F3F0";
  sheet.getRange(`F5:X${last}`).format.numberFormat="0";
  for(let col=15;col<=19;col++) sheet.getRange(`${colName(col)}5:${colName(col)}${last}`).dataValidation={rule:{type:"whole",operator:"between",formula1:0,formula2:100}};
  sheet.getRange(`Z5:Z${last}`).dataValidation={rule:{type:"list",values:["待平衡测试","测试中","已平衡","锁定"]}};
  sheet.getRange(`Z5:Z${last}`).conditionalFormats.add("containsText",{text:"待平衡测试",format:{fill:"#FFF0C7",font:{color:"#7A5A15"}}});
  sheet.getRange(`Z5:Z${last}`).conditionalFormats.add("containsText",{text:"已平衡",format:{fill:"#DCEEDD",font:{color:"#295B36"}}});
  sheet.getRange(`F5:N${last}`).conditionalFormats.add("colorScale",{colors:["#E8EFF4","#9EC4D9","#356B87"],thresholds:["min","50%","max"]});
  sheet.getRange(`O5:S${last}`).conditionalFormats.add("colorScale",{colors:["#F7EED6","#D8B86C","#8C6731"],thresholds:["min","50%","max"]});
  sheet.getRange(`T5:X${last}`).conditionalFormats.add("colorScale",{colors:["#EEE8F5","#B8A2D2","#675080"],thresholds:["min","50%","max"]});
  widths(sheet,[17,11,14,16,12,14,17,14,14,19,19,19,18,18,16,14,16,16,16,18,17,19,20,18,48,14]);
  sheet.getRange("4:4").format.rowHeight=46; sheet.getRange(`5:${last}`).format.rowHeight=54;
  sheet.freezePanes.freezeRows(4); sheet.freezePanes.freezeColumns(5);
  sheet.tables.add(`A4:Z${last}`,true,`${name==="游戏属性标准"?"HeroGameStats":"VoiceGameStats"}Table`).style="TableStyleMedium4";
  return sheet;
}

async function buildPersonaWorkbook(){
  const wb=Workbook.create();
  const guide=wb.worksheets.add("使用说明");
  const gameSheet=addGameStatsSheet(wb,"游戏属性标准");
  const main=wb.worksheets.add("英雄人格主表");
  const rules=wb.worksheets.add("AI行为规则");
  const dict=wb.worksheets.add("字段字典");
  const enums=wb.worksheets.add("枚举与评分");

  titleBand(guide,"H","艾欧尼亚22英雄人格数据库模板","面向 AI 事件生成、NPC 决策、对话一致性和后端结构化存储。版本 V1.0 · 2026-08-11");
  guide.getRange("A4:B11").values=[
    ["模块","使用方法"],
    ["游戏属性标准","权威导入表：逐角色提供 attributes、personality、fate_weights 三组后端字段；命运权重由人格公式自动生成。"],
    ["英雄人格主表","官方事实字段已预填；浅金色区域为策划推断字段，修改后需将审核状态改为“已复核”。"],
    ["AI行为规则","把人格转成可执行的帮助、敌对、拒绝、结盟和记忆规则，可直接拼入事件生成提示词。"],
    ["字段字典","规定字段类型、必填性和用途，后端建表或 JSON Schema 应以此为准。"],
    ["枚举与评分","统一审核状态、关系距离和 0–100 人格评分锚点。"],
    ["22人范围","沿用现有经典艾欧尼亚阵容；芸阿娜为后加入角色，本版未计入，可复制一行扩展。"],
    ["版权边界","人物事实依据 Riot 官方宇宙资料；人格分数与生成约束属于本项目策划推断，不宣称官方结论。"],
  ];
  headerStyle(guide.getRange("A4:B4")); bodyStyle(guide.getRange("A5:B11"));
  guide.getRange("A:A").format.columnWidth=18; guide.getRange("B:B").format.columnWidth=82;
  guide.getRange("4:4").format.rowHeight=25; guide.getRange("5:11").format.rowHeight=42;
  guide.freezePanes.freezeRows(4);

  const headers=["英雄ID","英雄名","称号","物种","出身/活动地","当前状态","所属组织","官方来源URL","审核状态","人格版本","核心原型","公开面貌","私下真实","核心欲望","核心恐惧","价值优先级","道德底线","关键创伤","核心矛盾","防御机制","决策方式","冲突方式","社交距离","信任条件","愤怒触发","柔软点","对玩家初始态度","和平倾向","权力倾向","自由倾向","灵性亲和","命运态度","共情能力","自律程度","风险偏好","幽默方式","语言风格摘要","禁止偏离行为","编辑备注","资料完整度"];
  const end=colName(headers.length);
  titleBand(main,end,"艾欧尼亚22英雄人格主表","本表保存叙事人格与行为依据；游戏实际数值请以“游戏属性标准”工作表为准。前五项分数对应后端五维人格，其余三项仅供策划分析。");
  main.getRange(`A4:${end}4`).values=[headers]; headerStyle(main.getRange(`A4:${end}4`));
  const rows=champions.map(c=>{
    const p=persona[c.id]; if(!p) throw new Error(`Missing persona ${c.id}`);
    const [archetype,publicFace,privateSelf,desire,fear,scores,trust,anger,soft,speech,forbid]=p;
    return [c.id,c.name,c.title,c.species,c.origin,c.status,(c.affiliations||[]).join("、"),safeSource(c),"待复核","1.0",archetype,publicFace,privateSelf,desire,fear,"家园/自我/关系，按角色具体情境排序",forbid.replace(/^不可/,"不得"),c.story_arcs?.[0]||"",`${desire}，但又恐惧${fear}`,"压力下强化其核心原型",publicFace,publicFace,"陌生人保持观察距离",trust,anger,soft,"中立观察；依据玩家行为动态变化",...scores,"见角色语境，不强制插科打诨",speech,forbid,"",null];
  });
  main.getRange(`A5:${end}${4+rows.length}`).values=rows;
  bodyStyle(main.getRange(`A5:${end}${4+rows.length}`));
  main.getRange(`A5:J${4+rows.length}`).format.fill="#EEF4F0";
  main.getRange(`K5:AM${4+rows.length}`).format.fill="#FBF5E6";
  main.getRange(`AN5:AN${4+rows.length}`).formulas=rows.map((_,i)=>[`=COUNTA(K${i+5}:AM${i+5})/29`]);
  main.getRange(`AN5:AN${4+rows.length}`).format.numberFormat="0%";
  main.getRange(`I5:I${4+rows.length}`).dataValidation={rule:{type:"list",values:["待补充","待复核","已复核","锁定"]}};
  for(const col of [28,29,30,31,32,33,34,35]) main.getRange(`${colName(col)}5:${colName(col)}${4+rows.length}`).dataValidation={rule:{type:"whole",operator:"between",formula1:0,formula2:100}};
  main.getRange(`I5:I${4+rows.length}`).conditionalFormats.add("containsText",{text:"待复核",format:{fill:"#FFF0C7",font:{color:"#7A5A15"}}});
  main.getRange(`I5:I${4+rows.length}`).conditionalFormats.add("containsText",{text:"已复核",format:{fill:"#DCEEDD",font:{color:"#295B36"}}});
  main.getRange(`AN5:AN${4+rows.length}`).conditionalFormats.add("dataBar",{color:palette.jade,gradient:true});
  widths(main,[14,11,14,18,24,30,22,38,11,10,16,28,30,28,28,25,30,30,32,24,25,25,18,30,28,28,26,11,11,11,11,11,11,11,11,18,32,34,24,12]);
  main.getRange("4:4").format.rowHeight=42; main.getRange(`5:${4+rows.length}`).format.rowHeight=74;
  main.freezePanes.freezeRows(4); main.freezePanes.freezeColumns(4);
  main.tables.add(`A4:${end}${4+rows.length}`,true,"HeroPersonaTable").style="TableStyleMedium4";

  const ruleHeaders=["英雄ID","英雄名","默认关系姿态","愿意帮助的条件","转为敌对的条件","是否会欺骗","暴力阈值","结盟逻辑","拒绝规则","长期记忆钩子","事件功能","常见遭遇主题","战斗表达","对话一致性规则","AI提示词片段","审核状态"];
  const ruleEnd=colName(ruleHeaders.length); titleBand(rules,ruleEnd,"AI 行为规则","将人格资料转成事件生成器能够直接执行的条件和边界。所有规则均为项目策划层，可持续迭代。");
  rules.getRange(`A4:${ruleEnd}4`).values=[ruleHeaders]; headerStyle(rules.getRange(`A4:${ruleEnd}4`));
  const ruleRows=champions.map(c=>{const p=persona[c.id],s=p[5];return[c.id,c.name,"先观察玩家目的，再按价值观回应",`玩家满足：${p[6]}`,`玩家触发：${p[7]}`,s[1]>75?"会，为达成核心目标使用策略性隐瞒":"通常不会；仅在保护核心对象时隐瞒",s[6]>80?"低频且精准，只在必要时使用":"受情绪和环境影响",`共同目标必须与“${p[3]}”兼容`,p[10],`${p[4]}；${p[8]}`,"盟友/导师/对手/事件裁决者，依情境选择",(c.story_arcs||[]).slice(0,3).join("；"),s[7]>75?"主动推进、优先制造行动压力":"先评估局势，再选择介入",`始终保持：${p[9]}。${p[10]}`,`你是${c.name}（${c.title}）。核心欲望：${p[3]}；核心恐惧：${p[4]}；说话应${p[9]}；${p[10]}。根据玩家行为给出有收益也有代价的回应。`,"待复核"]});
  rules.getRange(`A5:${ruleEnd}${4+ruleRows.length}`).values=ruleRows; bodyStyle(rules.getRange(`A5:${ruleEnd}${4+ruleRows.length}`));
  rules.getRange(`A5:B${4+ruleRows.length}`).format.fill="#EEF4F0"; rules.getRange(`C5:P${4+ruleRows.length}`).format.fill="#FBF5E6";
  rules.getRange(`P5:P${4+ruleRows.length}`).dataValidation={rule:{type:"list",values:["待补充","待复核","已复核","锁定"]}};
  widths(rules,[14,11,25,34,34,27,26,32,32,34,25,36,30,38,58,11]); rules.getRange("4:4").format.rowHeight=42; rules.getRange(`5:${4+ruleRows.length}`).format.rowHeight=80;
  rules.freezePanes.freezeRows(4); rules.freezePanes.freezeColumns(2); rules.tables.add(`A4:${ruleEnd}${4+ruleRows.length}`,true,"HeroBehaviorTable").style="TableStyleMedium4";

  const fieldDesc={"英雄ID":"后端唯一键，使用英文 snake_case","官方来源URL":"对应 Riot 官方资料地址","审核状态":"内容工作流状态","人格版本":"人格策划版本号","和平倾向":"偏向协商、避免伤害的程度","权力倾向":"追求控制力、地位或强制手段的程度","自由倾向":"抗拒约束并追求自主的程度","灵性亲和":"与精神领域、自然魔法及仪式的亲近程度","命运态度":"相信使命、宿命或宏大目标的程度","共情能力":"感知并重视他人处境的程度","自律程度":"控制冲动并长期遵守原则的程度","风险偏好":"主动承担危险与不确定性的程度","资料完整度":"公式：人格推断字段的非空比例"};
  const dictRows=headers.map((h,i)=>[h,i<10||h==="资料完整度"?"事实/系统字段":"策划人格字段",["和平倾向","权力倾向","自由倾向","灵性亲和","命运态度","共情能力","自律程度","风险偏好"].includes(h)?"整数 0–100":h==="资料完整度"?"公式百分比":"文本",["英雄ID","英雄名","审核状态","核心原型","核心欲望","核心恐惧","语言风格摘要","禁止偏离行为"].includes(h)?"是":"否",fieldDesc[h]||"用于描述角色并约束 AI 行为；填写时保持单一语义。",h==="英雄ID"?"yasuo":h==="审核状态"?"已复核":"参见主表",i<10?"数据库索引/溯源":"事件选择、对话语气与行为边界"]);
  titleBand(dict,"G","字段字典","用于后端建表、JSON Schema 和策划协作。字段含义不可在不同英雄间随意变化。");
  dict.getRange("A4:G4").values=[["字段名","字段分组","数据类型","必填","定义","示例","AI/系统用途"]]; headerStyle(dict.getRange("A4:G4"));
  dict.getRange(`A5:G${4+dictRows.length}`).values=dictRows; bodyStyle(dict.getRange(`A5:G${4+dictRows.length}`)); widths(dict,[22,18,16,10,55,24,38]); dict.getRange("4:4").format.rowHeight=30; dict.getRange(`5:${4+dictRows.length}`).format.rowHeight=42; dict.freezePanes.freezeRows(4);

  titleBand(enums,"F","枚举与评分锚点","统一录入尺度，避免不同编辑人员使用相同分数表达不同含义。");
  enums.getRange("A4:F4").values=[["类型","值/区间","解释","录入示例","是否可扩展","备注"]]; headerStyle(enums.getRange("A4:F4"));
  const enumRows=[
    ["审核状态","待补充","关键字段为空","","否","不得进入正式 AI 上下文"],["审核状态","待复核","已填写但未通过世界观审核","","否","默认状态"],["审核状态","已复核","通过至少一名世界观编辑审核","","否","允许用于生成"],["审核状态","锁定","版本发布后冻结","","否","变更需升级版本"],
    ["人格分数","0–20","明显排斥或几乎不具备","和平倾向 10","否","极端低值需有剧情依据"],["人格分数","21–40","偏低","权力倾向 35","否",""],["人格分数","41–60","中性或情境化","风险偏好 55","否",""],["人格分数","61–80","明显倾向","共情能力 76","否",""],["人格分数","81–100","核心驱动力级别","自律程度 96","否","极端高值需写明代价"],
    ["关系姿态","敌对/警惕/中立/友善/信任","角色对玩家的基础距离","警惕","是","建议后端使用固定枚举"],["冲突方式","回避/协商/试探/威慑/行动/决斗","主要处理冲突的方法","试探","是","可多选但需排序"],
  ];
  enums.getRange(`A5:F${4+enumRows.length}`).values=enumRows; bodyStyle(enums.getRange(`A5:F${4+enumRows.length}`)); widths(enums,[18,26,48,24,14,38]); enums.getRange(`5:${4+enumRows.length}`).format.rowHeight=36; enums.freezePanes.freezeRows(4);
  return wb;
}

async function buildVoiceWorkbook(){
  const wb=Workbook.create();
  const guide=wb.worksheets.add("使用说明");
  const gameSheet=addGameStatsSheet(wb,"游戏属性引用");
  const specs=wb.worksheets.add("角色声线规格");
  const tasks=wb.worksheets.add("英雄游戏台词");
  const coverage=wb.worksheets.add("台词覆盖汇总");
  const dict=wb.worksheets.add("字段字典");
  const qc=wb.worksheets.add("场景与审核标准");

  titleBand(guide,"H","艾欧尼亚22英雄游戏台词数据库","用于 RPG 内英雄对话、事件触发与后端台词检索。已预填22位英雄 × 12种场景的264条原创中文台词。版本 V2.0");
  guide.getRange("A4:B11").values=[
    ["模块","使用方法"],["游戏属性引用","与人格模板完全相同的 attributes、personality、fate_weights，用于确定战斗、性格和命运台词。"],["英雄游戏台词","主数据表：每行是一条可直接进入游戏的台词，包含关系门槛、触发条件、人格键和命运键。"],["角色声线规格","约束台词节奏、用词和情绪表现，不要求模仿现有官方配音。"],["台词覆盖汇总","自动统计每位英雄的台词填写、审核和游戏录入进度。"],["场景与审核标准","定义12类核心场景以及原创性、人物一致性和第一人称交互要求。"],["版权要求","所有台词均为本项目原创，不复制《英雄联盟》现有语音或故事原句。"],["22人范围","与人格模板一致，暂不包含芸阿娜。"]
  ]; headerStyle(guide.getRange("A4:B4")); bodyStyle(guide.getRange("A5:B11")); guide.getRange("A:A").format.columnWidth=18; guide.getRange("B:B").format.columnWidth=84; guide.getRange("5:11").format.rowHeight=40; guide.freezePanes.freezeRows(4);

  const specHeaders=["英雄ID","英雄名","称号","年龄感/身份感","音高","语速","音色关键词","咬字方式","呼吸特征","情绪跨度","战斗状态变化","禁用表演方向","参考人格摘要","官方资料URL","审核状态","导演备注"];
  titleBand(specs,"P","22位英雄角色声线规格","声线描述是原创表演方向，不是对官方演员声音的复刻指令。所有“禁用方向”必须在试音前传达给演员。");
  specs.getRange("A4:P4").values=[specHeaders]; headerStyle(specs.getRange("A4:P4"));
  const specRows=champions.map(c=>{const v=voice[c.id],p=persona[c.id];return[c.id,c.name,c.title,...v,`${p[0]}；${p[9]}`,safeSource(c),"待试音",""]});
  specs.getRange(`A5:P${4+specRows.length}`).values=specRows; bodyStyle(specs.getRange(`A5:P${4+specRows.length}`)); specs.getRange(`A5:C${4+specRows.length}`).format.fill="#EEF4F0"; specs.getRange(`D5:P${4+specRows.length}`).format.fill="#FBF5E6";
  specs.getRange(`O5:O${4+specRows.length}`).dataValidation={rule:{type:"list",values:["待试音","试音中","已定声线","需重定"]}};
  widths(specs,[14,11,14,18,10,11,28,24,18,30,34,38,38,40,12,30]); specs.getRange(`5:${4+specRows.length}`).format.rowHeight=66; specs.freezePanes.freezeRows(4); specs.freezePanes.freezeColumns(3); specs.tables.add(`A4:P${4+specRows.length}`,true,"VoiceSpecTable").style="TableStyleMedium4";

  const taskHeaders=["台词ID line_id","英雄ID hero_id","英雄名","场景代码 scene_code","场景名称","触发条件","对话对象","主情绪","次情绪","强度1-5","游戏内中文台词 text_cn","语气与表演提示","建议时长秒","关系值下限","章节限制","地点限制","是否一次性","触发权重","关联人格键","关联命运键","冷却事件数","音频文件名","审核状态","审核备注","官方资料URL"];
  const taskEnd=colName(taskHeaders.length); titleBand(tasks,taskEnd,"22位英雄游戏台词主表","22位英雄 × 12类核心场景 = 264条原创游戏台词。台词直接面向玩家，触发字段可映射后端事件、关系值与命运权重。");
  tasks.getRange(`A4:${taskEnd}4`).values=[taskHeaders]; headerStyle(tasks.getRange(`A4:${taskEnd}4`));
  const taskRows=[];
  const traitByScene={MEET:"destiny",GREET:"peace",WARN:"destiny",REFUSE:"freedom",TRUST:"peace",ANGER:"power",HURT:"peace",COMBAT:"power",VICTORY:"destiny",DEFEAT:"spirit",LORE:"spirit",FAREWELL:"freedom"};
  const fateByTrait={peace:"guardian",power:"strong",freedom:"wanderer",spirit:"spirit_fate",destiny:"breaker"};
  for(const c of champions){ for(let sceneIndex=0;sceneIndex<scenes.length;sceneIndex++){
    const s=scenes[sceneIndex];
    const asset=`ION_${c.id.toUpperCase()}_${s[0]}`;
    const trait=traitByScene[s[0]], oneTime=["MEET","TRUST","LORE"].includes(s[0])?"是":"否",relation=s[0]==="TRUST"?40:s[0]==="GREET"?10:["ANGER","REFUSE"].includes(s[0])?-20:0;
    const lines=dialogueLines[c.id]; if(!lines||lines.length!==12) throw new Error(`Dialogue count must be 12 for ${c.id}`);
    taskRows.push([asset,c.id,c.name,s[0],s[1],s[2],"玩家",s[3],s[4],s[5],lines[sceneIndex],`保持${persona[c.id][9]}；${voice[c.id][8]}`,s[6],relation,"不限","不限",oneTime,10,trait,fateByTrait[trait],oneTime==="是"?0:3,null,"待审核","",safeSource(c)]);
  }}
  const last=4+taskRows.length; tasks.getRange(`A5:${taskEnd}${last}`).values=taskRows; bodyStyle(tasks.getRange(`A5:${taskEnd}${last}`));
  tasks.getRange(`V5:V${last}`).formulas=taskRows.map((_,i)=>[`=A${i+5}&".wav"`]);
  tasks.getRange(`A5:J${last}`).format.fill="#EEF4F0"; tasks.getRange(`K5:U${last}`).format.fill="#FBF5E6"; tasks.getRange(`V5:Y${last}`).format.fill="#F2F3F0";
  tasks.getRange(`J5:J${last}`).dataValidation={rule:{type:"whole",operator:"between",formula1:1,formula2:5}};
  tasks.getRange(`N5:N${last}`).dataValidation={rule:{type:"whole",operator:"between",formula1:-100,formula2:100}};
  tasks.getRange(`Q5:Q${last}`).dataValidation={rule:{type:"list",values:["是","否"]}};
  tasks.getRange(`R5:R${last}`).dataValidation={rule:{type:"whole",operator:"between",formula1:1,formula2:100}};
  tasks.getRange(`W5:W${last}`).dataValidation={rule:{type:"list",values:["待审核","需改写","已审核","已录入游戏","禁用"]}};
  tasks.getRange(`W5:W${last}`).conditionalFormats.add("containsText",{text:"已审核",format:{fill:"#DCEEDD",font:{color:"#295B36"}}}); tasks.getRange(`W5:W${last}`).conditionalFormats.add("containsText",{text:"需改写",format:{fill:"#F4D7D2",font:{color:"#8A372C"}}});
  widths(tasks,[24,16,11,18,16,36,14,14,14,10,62,44,12,13,13,18,12,12,17,19,13,30,14,32,42]); tasks.getRange("4:4").format.rowHeight=48; tasks.getRange(`5:${last}`).format.rowHeight=68; tasks.freezePanes.freezeRows(4); tasks.freezePanes.freezeColumns(3); tasks.tables.add(`A4:${taskEnd}${last}`,true,"HeroDialogueTable").style="TableStyleMedium4";

  titleBand(coverage,"G","英雄台词覆盖汇总","公式自动读取“英雄游戏台词”状态；每位英雄基础目标为12类场景全部覆盖。"); coverage.getRange("A4:G4").values=[["英雄ID","英雄名","计划台词数","已填写","已审核","已录入游戏","审核率"]]; headerStyle(coverage.getRange("A4:G4"));
  coverage.getRange(`A5:B${4+champions.length}`).values=champions.map(c=>[c.id,c.name]);
  for(let i=0;i<champions.length;i++){const r=i+5;coverage.getRange(`C${r}`).formulas=[[`=COUNTIF('英雄游戏台词'!$B$5:$B$${last},A${r})`]];coverage.getRange(`D${r}`).formulas=[[`=COUNTIFS('英雄游戏台词'!$B$5:$B$${last},A${r},'英雄游戏台词'!$K$5:$K$${last},"<>")`]];coverage.getRange(`E${r}`).formulas=[[`=COUNTIFS('英雄游戏台词'!$B$5:$B$${last},A${r},'英雄游戏台词'!$W$5:$W$${last},"已审核")+COUNTIFS('英雄游戏台词'!$B$5:$B$${last},A${r},'英雄游戏台词'!$W$5:$W$${last},"已录入游戏")`]];coverage.getRange(`F${r}`).formulas=[[`=COUNTIFS('英雄游戏台词'!$B$5:$B$${last},A${r},'英雄游戏台词'!$W$5:$W$${last},"已录入游戏")`]];coverage.getRange(`G${r}`).formulas=[[`=IF(C${r}=0,0,E${r}/C${r})`]];}
  bodyStyle(coverage.getRange(`A5:G${4+champions.length}`)); coverage.getRange(`G5:G${4+champions.length}`).format.numberFormat="0%"; coverage.getRange(`G5:G${4+champions.length}`).conditionalFormats.add("dataBar",{color:palette.jade,gradient:true}); widths(coverage,[16,12,14,18,18,14,16]); coverage.freezePanes.freezeRows(4);

  const dictRows=taskHeaders.map((h,i)=>[h,i<10?"触发与表演":i<22?"游戏内容与规则":"审核与来源",[9,12,13,17,20].includes(i)?"整数":"文本",[0,1,2,3,4,5,7,9,10,13,16,17,18,19,20,22].includes(i)?"是":"否",i===10?"英雄在本 RPG 中直接对玩家说出的原创中文台词":i===18?"peace/power/freedom/spirit/destiny 之一":i===19?"guardian/strong/wanderer/spirit_fate/breaker 之一":i===21?"由台词ID公式生成的音频文件名":"按字段名用于对话检索、触发或审核",i===0?"ION_YASUO_MEET":i===10?"我只是路过。":"参见主表"]);
  titleBand(dict,"F","游戏台词字段字典","后端 dialogue 数据表、事件触发器和 AI 上下文应保持同一字段语义。"); dict.getRange("A4:F4").values=[["字段名","字段组","数据类型","必填","定义","示例"]]; headerStyle(dict.getRange("A4:F4")); dict.getRange(`A5:F${4+dictRows.length}`).values=dictRows; bodyStyle(dict.getRange(`A5:F${4+dictRows.length}`)); widths(dict,[30,18,15,10,68,34]); dict.getRange(`5:${4+dictRows.length}`).format.rowHeight=40; dict.freezePanes.freezeRows(4);

  titleBand(qc,"F","游戏台词场景与审核标准","每条台词必须服务明确场景、符合角色人格与游戏数值，并保持项目的第二人称叙述习惯。"); qc.getRange("A4:F4").values=[["类别","代码/规则","定义","通过条件","失败处理","备注"]]; headerStyle(qc.getRange("A4:F4"));
  const qcRows=[...scenes.map(s=>["场景",s[0],s[1],s[2],"调整触发条件或重写台词",`默认主情绪：${s[3]}；强度：${s[5]}`]),
    ["内容","原创性","不得复制官方现成台词或故事原句","通过人工检索与世界观审核","标记禁用并重写","可使用角色事实，不复制表达"],["内容","人物一致性","欲望、恐惧、底线和语言节奏一致","与人格主表和声线规格不冲突","调整措辞或触发条件","不得只靠口头禅识别角色"],["系统","属性关联","关联一个五维人格键与对应命运键","键名属于游戏现有枚举","修正字段","peace→guardian 等映射固定"],["系统","关系门槛","信任/敌对类台词必须设定关系值下限","数值位于 -100 至 100","修正门槛","普通环境台词可为0"],["叙事","玩家称谓","英雄直接对玩家说话时统一使用“你”","不使用未定义玩家姓名","重写","符合全程第二人称规则"],["审核","待审核","原创台词已写入但未通过世界观复核","不可进入正式构建","分配审核人","默认状态"],["审核","已审核","世界观、角色语气和触发字段均通过","允许进入游戏数据","生成音频或直接使用文本",""],["审核","已录入游戏","已进入后端并通过运行测试","可在事件中触发","纳入版本管理",""]
  ]; qc.getRange(`A5:F${4+qcRows.length}`).values=qcRows; bodyStyle(qc.getRange(`A5:F${4+qcRows.length}`)); widths(qc,[16,22,40,48,36,44]); qc.getRange(`5:${4+qcRows.length}`).format.rowHeight=42; qc.freezePanes.freezeRows(4);
  return wb;
}

await fs.mkdir(outputDir,{recursive:true});
const personaWb=await buildPersonaWorkbook();
const voiceWb=await buildVoiceWorkbook();

const personaChecks=await personaWb.inspect({kind:"table",range:"英雄人格主表!A1:AN10",include:"values,formulas",tableMaxRows:10,tableMaxCols:40,maxChars:12000});
const voiceChecks=await voiceWb.inspect({kind:"table",range:"台词覆盖汇总!A1:G12",include:"values,formulas",tableMaxRows:12,tableMaxCols:8,maxChars:8000});
const personaErrors=await personaWb.inspect({kind:"match",searchTerm:"#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",options:{useRegex:true,maxResults:100},summary:"persona formula errors"});
const voiceErrors=await voiceWb.inspect({kind:"match",searchTerm:"#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",options:{useRegex:true,maxResults:100},summary:"voice formula errors"});
console.log(personaChecks.ndjson);
console.log(voiceChecks.ndjson);
console.log(personaErrors.ndjson);
console.log(voiceErrors.ndjson);

const personaPreviewSheets=[["使用说明","A1:H11"],["游戏属性标准","A1:N12"],["英雄人格主表","A1:N12"],["AI行为规则","A1:H12"],["字段字典","A1:G16"],["枚举与评分","A1:F15"]];
for(const [name,range] of personaPreviewSheets){const blob=await personaWb.render({sheetName:name,range,scale:1.2,format:"png"});await fs.writeFile(`${outputDir}/preview_persona_${name}.png`,new Uint8Array(await blob.arrayBuffer()));}
const voicePreviewSheets=[["使用说明","A1:H12"],["游戏属性引用","A1:N12"],["角色声线规格","A1:J12"],["英雄游戏台词","A1:M14"],["台词覆盖汇总","A1:G14"],["字段字典","A1:F16"],["场景与审核标准","A1:F17"]];
for(const [name,range] of voicePreviewSheets){const blob=await voiceWb.render({sheetName:name,range,scale:1.2,format:"png"});await fs.writeFile(`${outputDir}/preview_voice_${name}.png`,new Uint8Array(await blob.arrayBuffer()));}

await (await SpreadsheetFile.exportXlsx(personaWb)).save(`${outputDir}/艾欧尼亚22英雄人格数据库模板.xlsx`);
await (await SpreadsheetFile.exportXlsx(voiceWb)).save(`${outputDir}/艾欧尼亚22英雄语音采集字段表.xlsx`);
console.log(JSON.stringify({personaRows:champions.length,voiceTasks:champions.length*scenes.length,outputDir},null,2));
