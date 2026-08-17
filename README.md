# 《无名者：符文之地》

当前版本：**v0.3.13**。版本创建、离线备份与安全恢复方法见 [版本说明.md](版本说明.md)。当前功能、技术结构、网页端接口约定和完整更新日志可在 **API节点管理器 → 项目总览与日志** 中查看，也可由 `GET /api/admin/project-status` 读取。

阶段4已把 World Engine、Event Director、事件选择、统一检定、Outcome 写回和 AI Narrator 接成完整闭环。AI 只接收结构化 `EventContext` 并输出经过契约校验的叙事；所有概率、随机数、结果档位、奖励、关系和世界线程变化仍由程序决定。内部状态统一隐藏，本地开发时仅可用 `?debug=1` 显式查看，生产 API 不返回完整调试载荷。

常规事件已不再来自固定20个模板。每次旅行会根据当前地点、世界时间、人物能力与伤势、活跃线程阶段、关注目标和导演节奏，即时组合场景、人物、关键物与压力，再先生成 2—4 条目标和策略不同的行动，最后按行动性质映射能力；其中可包含无需检定和持有条件行动。固定编写内容只保留明确的章节终局事件。

一个手机竖屏优先的 AI 原生互动 RPG Web Demo。玩家不是预设英雄，而是在艾欧尼亚东部出生的普通人；六次情境选择会塑造隐藏人格，随后进入由地点、经历、关系与随机因素共同驱动的旅途。

## 已实现玩法

- 六道无属性标签的情境人格题，记录 `peace / power / freedom / spirit / destiny`
- 按人格生成姓名、年龄、家庭、出生地、童年经历和初始标签
- 青木村、断风森林、战争遗迹、山间寺庙四节点自由地图
- 每季 3 点行动点；耗尽后下一次行动自动推进到新季节并恢复
- 第一章采用一年四季制：春夏秋冬每季恰好 3 次行动，共 12 次行动
- 第一年冬末强制触发青木村入侵、亚索相遇与第一章 Boss“血旗督军·卡尔戈”
- Boss 胜负拥有不同战后叙事；胜利可获得第一章遗物“血旗断刃”
- 常规事件由地点、世界时间、现场组件、世界线程、玩家状态、关注目标与导演张力即时组合，不再依赖固定 20 个事件
- 5 位有性格、目标、关系与长期记忆的 NPC
- 文字战斗与非战斗选择统一使用六项核心能力检定，前台呈现风险、主要修正与符合世界观的叙事结果
- 完整人物档案：六项核心能力、伤势/身体状态、生命风险、人格、命运倾向、物品与关系均可查看
- 五维人格与守护/强者/流浪/灵界/破局五类命运倾向公开显示
- 事件结算逐项说明属性、人格、命运、NPC 关系和物品变化
- 统一 Check Engine：战斗与非战斗选项均提前显示六项核心属性、风险、成功率和主要修正因素
- 所有风险事件拥有大成功、成功、部分成功、失败四级结果；失败会形成新困难、状态、关系变化或错失物品
- 稳定 Seed 由事件、选项和玩家状态版本共同生成，刷新无法重骰
- 价值观选择存在真实取舍：强化一种人格/命运方向时，可能削弱相对方向
- 24 件带世界观描述、稀有度与实际属性加成的物品
- 本地使用 SQLite 游戏存档；Vercel 使用 Runtime Cache 保存试玩进度
- 独立 `AIService` 接口层，当前无 Key 时使用本地 Mock，可替换为任意模型 API
- 知识库将人物传记与人物故事整合到英雄卡片；故事正文保持规范化存储，可被多位关联英雄共享

## 项目结构

```text
runeterra-ai-rpg/
├─ frontend/              React + Vite + Tailwind CSS
│  └─ src/
│     ├─ components/      公共 UI
│     ├─ pages/           首页、人格、出生和游戏页
│     └─ data/            人格情境题
├─ backend/               FastAPI + SQLite
│  ├─ api/                HTTP 路由
│  ├─ database/           SQLite 持久化
│  ├─ models/             请求模型
│  ├─ services/           游戏状态机与 AI Service
│  └─ tests/              核心循环测试
└─ game-data/             世界、地点、NPC、动态事件组件、线程与项目状态
```

## 一键启动（推荐）

直接双击项目根目录的 **`一键启动游戏.cmd`**。

启动器会自动检查 Python 与后端依赖，运行游戏服务并打开浏览器。再次双击会直接打开已经运行的游戏。需要关闭后台服务时，双击 **`停止游戏.cmd`**；SQLite 存档不会丢失。

## 手动启动方式

需要 Node.js 18+ 与 Python 3.10+。在两个终端中分别执行：

### 1. 后端

```powershell
cd runeterra-ai-rpg
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt
python -m uvicorn backend.main:app --reload --port 8000
```

后端健康检查位于 `http://127.0.0.1:8000/health`，交互式 API 文档位于 `http://127.0.0.1:8000/docs`。

### 2. 前端

```powershell
cd runeterra-ai-rpg\frontend
npm install
npm run dev
```

打开 `http://127.0.0.1:5173`。Vite 会将 `/api` 请求代理到本地 8000 端口。

## 验证

```powershell
# 项目根目录
python -m unittest backend.tests.test_game -v

# frontend 目录
npm run build
```

## 部署到 Vercel

仓库根目录已经包含 `vercel.json` 和 `api/index.py`。在 Vercel 导入 GitHub 仓库后使用以下设置：

```text
Framework Preset: Vite
Root Directory: runeterra-ai-rpg（若仓库根目录就是本目录则留空）
Install Command: pnpm install --frozen-lockfile
Build Command: pnpm run build
Output Directory: frontend/dist
```

AI 叙事为可选能力。未配置密钥时会自动使用本地 Mock，不影响完整试玩。需要真实 AI 时，在 Vercel Project Settings → Environment Variables 配置：

```env
DEEPSEEK_API_KEY=
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-flash
DEEPSEEK_TIMEOUT=15
RUNETERRA_DISABLE_REMOTE_AI=0
```

不要把真实 `.env`、SQLite 文件、`.vercel`、依赖目录或构建产物提交到 GitHub。生产环境的管理后台被关闭，密钥只由 FastAPI 服务端读取。

## 替换真实 AI

所有叙事生成入口都集中在 `backend/services/ai_service.py`：

- `generate_birth()`：出生背景
- `generate_event()`：动态事件包装
- `generate_dialogue()`：NPC 对话和记忆回应
- `generate_battle_text()`：战斗叙事

接入模型时保留这四个公开方法的输入输出结构即可。生产环境建议再增加超时、重试、内容安全、结构化输出校验和 Mock 降级逻辑。

## 说明

这是非商业同人概念 Demo，不包含《英雄联盟》官方美术或音频素材。视觉由 CSS 生成的水墨山形、纸张纹理与符号构成。
