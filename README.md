# CyberWolf - AI 狼人杀 Web 模拟器

[English](./README.en.md)

CyberWolf 是一个 AI 驱动的狼人杀模拟器。项目当前以 **Web UI** 为主要入口，使用 React + Vite 构建前端，FastAPI 提供后端接口和 WebSocket 实时事件流；Electron 桌面壳、Textual TUI 和 CLI 仍保留用于调试、复盘和自动化。

所有非真人玩家都可以由 LLM Agent 驱动，也可以在未配置 LLM 时自动回退到本地随机策略。后端是游戏流程的唯一事实来源，负责阶段推进、规则结算、行动校验、计时、信息隔离和事件持久化；前端通过 REST + WebSocket 跟随后端事件渲染上帝视角或个人玩家视角。

## 当前重点

- **Web UI 优先**：支持开局、上帝模式观战、个人模式、真人行动面板、事件流、复盘、角色头像、阶段进度、BGM/SFX 播放钩子等。
- **后端驱动流程**：阶段、计时、弹窗、待操作请求和结算都由后端事件驱动，前端不再自行猜测游戏流程。
- **个人模式信息隔离**：运行中的真人局需要 `seat` + `seat_token`，玩家只能看到自己的私有信息；狼人可共享狼队信息。
- **上帝模式与回放**：上帝视角可查看全局信息，适合调试、观战、流程审计和历史复盘。
- **配置驱动玩法**：角色、阶段、规则、提示词和工具由 YAML 配置编译为运行时游戏图。
- **SQLite 持久化**：对局、玩家、事件、快照、LLM 调用、配置和指标都会落库，便于重放与排查。

## 支持的板子

当前主要支持配置：`12p_pre_witch_hunter_idiot`。

| 阵营 | 角色 | 人数 |
| --- | --- | ---: |
| 狼人阵营 | 狼人 | 4 |
| 好人阵营 | 预言家 | 1 |
| 好人阵营 | 女巫 | 1 |
| 好人阵营 | 猎人 | 1 |
| 好人阵营 | 白痴 | 1 |
| 好人阵营 | 平民 | 4 |

## 游戏流程

```text
夜晚：
  night_start
  -> 狼人选择击杀目标
  -> 预言家查验目标
  -> 女巫选择是否使用解药/毒药
  -> 猎人确认开枪状态
  -> 白痴确认身份
  -> 夜晚结算
  -> 死亡技能结算
  -> 胜负检查

白天：
  公布死讯
  -> 第一天警长竞选
  -> 白天发言
  -> 投票 / 平票加赛
  -> 放逐结算
  -> 死亡技能结算
  -> 胜负检查

循环直到一方获胜。
```

## 规则摘要

- 狼人每晚选择一个击杀目标，并可在支持的白天阶段自爆。
- 预言家每晚查验一名存活玩家，并获得私有的好人/狼人结果。
- 女巫拥有一瓶解药和一瓶毒药，每瓶每局只能使用一次。
- 猎人在符合条件时可以开枪，但被毒死不能开枪。
- 白痴被投票放逐时翻牌免死，之后失去投票权。
- 警长竞选发生在第一天发言前，警长投票权重为 1.5。
- 平票会进入补充发言和再次投票；再次平票则无人出局。
- 死亡玩家可触发遗言和死亡技能，按队列依次结算。
- 胜负规则为屠边：狼人全灭则好人胜；神牌全灭或民牌全灭则狼人胜。

## 快速开始 - Web UI

### 环境要求

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)
- Node.js 20+ 推荐
- npm

### 安装

```bash
git clone git@github.com:upczww/CyberWolf.git
cd CyberWolf

uv sync
cd desktop
npm install
```

### 开发模式运行

在仓库根目录启动后端 API 服务：

```bash
uv run uvicorn server.api:app --host 127.0.0.1 --port 8766
```

另开一个终端启动 Web UI：

```bash
cd desktop
npm run dev
```

打开 Vite 输出的地址，通常是：

```text
http://127.0.0.1:5173
```

开发服务器会把 `/api` 和 `/ws` 代理到 FastAPI 后端。

### 可选 Electron 模式

```bash
cd desktop
npm run electron:dev
```

Electron 只是同一套 Web UI 的桌面壳；当前默认推荐使用浏览器 Web UI。

## LLM 配置

如果希望启用 LLM Agent，在仓库根目录创建 `.env`：

```dotenv
API_KEY=your_api_key
API_URL=https://api.deepseek.com/chat/completions
MODEL_ID=deepseek-chat

LLM_PROVIDER=openai_compatible
LLM_ENABLED_PHASES=night_wolf,night_seer,night_witch,sheriff_election,day_speech,day_vote,pending_skills
LLM_MAX_CALLS_PER_GAME=200
LLM_MAX_CONCURRENCY=1
LLM_TIMEOUT_SECONDS=50
LLM_MAX_RETRIES=5
```

不配置 `.env`，或使用 `--no-llm` 运行时，游戏会自动使用本地随机策略，无需联网。

## 常用命令

### Web / Desktop

```bash
cd desktop
npm run dev          # 启动 Vite 开发服务器
npm run build        # 构建 Web UI
npm run test:flow    # 运行前端流程测试
npm run electron:dev # 启动 Electron 桌面壳
```

### 后端 / 引擎

```bash
uv run uvicorn server.api:app --port 8766
uv run wolf-game --config 12p_pre_witch_hunter_idiot --no-llm
uv run wolf-game --config 12p_pre_witch_hunter_idiot
```

### 兼容 TUI

```bash
uv run wolf-tui
uv run wolf-tui --game-id <id>
uv run wolf-tui --lang en
```

Textual TUI 仍可用于直接读取数据库观战和调试，但不再是主要产品界面。

## API 概览

Web UI 主要使用以下接口：

| 接口 | 用途 |
| --- | --- |
| `POST /api/games/start` | 开始新对局 |
| `GET /api/games` | 获取对局列表 |
| `GET /api/games/{game_id}` | 获取对局详情和快照 |
| `DELETE /api/games/{game_id}` | 删除对局 |
| `GET /api/games/{game_id}/human_pending` | 获取指定座位待处理的真人操作 |
| `POST /api/games/{game_id}/human_action` | 提交真人操作 |
| `POST /api/games/{game_id}/replay` | 生成 AI 复盘 |
| `WS /ws/games/{game_id}` | 推送历史事件和实时事件 |

运行中的真人个人模式需要匹配的 `seat` 和 `seat_token`。已结束对局可自由观战和回放。

## 数据目录

```text
data/
  wolf.sqlite3       # SQLite 数据库：对局、玩家、事件、快照、LLM 调用等
  graphs/            # 每局游戏图导出
  contexts/          # 调试用的提示词/上下文快照
```

## 架构

```text
app/
  domain/            # 纯领域类型：角色、阶段、事件、状态、动作
  engine/            # 异步游戏循环、阶段处理器、规则、计时、游戏图
  services/          # LLM、决策校验、提示词、上下文隔离、复盘
  infra/             # SQLite、schema、事件总线、repositories
  ui/                # 兼容 Textual TUI
  configs/           # YAML 板子配置和 Jinja2 提示词模板

server/
  api.py             # FastAPI REST + WebSocket API
  music.py           # BGM 生成接口

desktop/
  src/               # React Web UI
  electron/          # 可选 Electron 桌面壳
  public/assets/     # 头像、图标、UI 美术和可选音频资源
```

## 设计原则

- **后端是事实来源**：阶段推进、计时、真人提示、行动校验和结算都由后端事件驱动。
- **三层动作管线**：ProposedAction -> ValidatedAction -> ResolvedAction，LLM 与真人输入都必须经过校验。
- **信息隔离**：公开、狼队、角色私有、上帝视角事件在发给客户端前分离。
- **事件驱动 UI**：前端从快照和事件重建状态，再通过 WebSocket 接收实时增量。
- **可降级 Agent**：LLM 可选且有预算上限；失败或超限时自动回退本地策略。
- **Web 优先，TUI 兼容**：React Web UI 是主要界面，CLI/TUI 保留为调试和运维工具。
