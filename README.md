# LycanTUI — AI 狼人杀模拟器

AI 驱动的狼人杀模拟器。所有玩家均为 AI Agent，由 LLM 或本地随机策略控制。支持配置驱动规则、SQLite 事件溯源持久化、Textual TUI 上帝视角观战。

## 当前支持的玩法

### 板子配置：12人预女猎白

| 阵营 | 角色 | 人数 |
|------|------|------|
| 狼人阵营 | 狼人 | 4 |
| 好人阵营 | 预言家 | 1 |
| 好人阵营 | 女巫 | 1 |
| 好人阵营 | 猎人 | 1 |
| 好人阵营 | 白痴 | 1 |
| 好人阵营 | 平民 | 4 |

### 角色技能

- **预言家**：每晚查验一名玩家身份（好人/狼人）
- **女巫**：拥有一瓶解药（救人）和一瓶毒药（杀人），各一局只能用一次
- **猎人**：死亡时可开枪带走一名玩家（被毒死不能开枪）
- **白痴**：被投票放逐时翻牌免死，翻牌后失去投票权
- **狼人**：每晚选择一名玩家击杀；白天阶段可选择自爆立即进入黑夜

### 游戏流程

```
夜晚：狼人杀人 → 预言家查验 → 女巫用药 → 夜晚结算
     → 死亡技能结算（猎人开枪、警徽移交） → 检查胜负
白天：公布死讯 → 警长竞选（仅第一轮）
     → 白天发言 → 投票放逐 → 放逐结算
     → 死亡技能结算（猎人开枪、警徽移交） → 检查胜负
循环直到一方获胜
```

### 规则细节

- 警长竞选：第一轮白天前进行，警长投票 1.5 倍权重
- 警长发言顺序：警长决定从左手/右手边开始，警长最后发言，后续白天交替方向
- 狼人自爆：竞选/发言/投票阶段狼人可自爆，触发技能结算后进入黑夜
- 女巫首夜可自救（fallback 模式下必定自救），次夜起不可自救
- 猎人被毒死不可开枪
- 猎人开枪带走的目标如果是警长，会触发警徽移交
- 警长死亡时可移交警徽或撕毁
- 平票时加赛一轮发言再投，再次平票则无人出局进入黑夜
- 所有死亡玩家均有遗言机会
- 胜负判定：屠边局（所有狼人死亡 = 好人胜；神牌全灭或民牌全灭 = 狼人胜）

### LLM 集成

支持 OpenAI 兼容接口（DeepSeek、智谱 GLM 等），每个角色由 LLM 驱动决策：
- 夜间行动（狼人杀人、预言家查验、女巫用药）
- 白天发言（结构化 JSON 输出 + 内心独白）
- 投票决策
- 警长竞选（是否参选 + 竞选发言）

支持前缀缓存优化（~81% 缓存命中率），LLM 调用达到上限时自动降级为本地策略。

## 快速开始

### 安装

```bash
uv sync
```

### 配置 LLM（可选）

创建 `.env` 文件：

```dotenv
API_KEY=your_api_key
API_URL=https://api.deepseek.com/chat/completions
MODEL_ID=deepseek-chat
LLM_PROVIDER=openai_compatible
LLM_ENABLED_PHASES=night_wolf,night_seer,night_witch,day_speech,day_vote,sheriff_election
LLM_MAX_CALLS_PER_GAME=200
LLM_MAX_CONCURRENCY=1
```

不配置 `.env` 或使用 `--no-llm` 时，所有决策使用本地随机策略。

### 运行一局游戏

```bash
# 纯本地策略（无需 LLM）
uv run wolf-game --config 12p_pre_witch_hunter_idiot --no-llm

# 启用 LLM
uv run wolf-game --config 12p_pre_witch_hunter_idiot
```

### 启动 TUI 观战

```bash
uv run wolf-tui                # 观看最新一局
uv run wolf-tui --game-id <id> # 指定对局
```

### TUI 快捷键

| 按键 | 功能 |
|------|------|
| `s` | 启动新局 |
| `r` | 手动刷新 |
| `n` / `p` | 下一局 / 上一局 |
| `1`-`9` | 快速跳到最近第 N 局 |
| `l` | 跳到最新一局 |
| `f` | 切换事件可见范围（全部/公开/狼队/私有/上帝/系统） |
| `w` | 快速切换狼队视角 |
| `a` | 切换自动刷新 |
| `Space` | 暂停/恢复自动滚动 |
| `PgUp`/`PgDn` | 翻页浏览历史 |
| `Home`/`End` | 跳到顶部/底部 |
| `g` | 切换中英文 |
| `d` | 删除当前对局 |
| `q` | 退出 |

### TUI 功能

- **实时显示**：狼刀、验人、用药、投票、开枪等操作即时显示
- **阵营着色**：狼人红色，好人默认色，当前行动角色高亮
- **存活计数**：标题栏实时显示 `神N 民N 狼N`
- **投票统计**：票数排名 + 警长 1.5x 权重标注
- **死因标记**：🔪刀杀 ☠毒杀 🏹枪杀 🗳放逐 💥自爆
- **技能标记**：🎯被刀目标 💊被救 🧪被毒目标 🔍被验 🎭翻牌
- **增量刷新**：0.5s 轮询，仅查询新事件，DB 连接复用

## 数据目录

```
data/
├── wolf.sqlite3       # SQLite 数据库（事件、快照、LLM 调用日志）
├── graphs/            # 每局游戏流程图（Mermaid/DOT/PNG）
└── contexts/          # 每个玩家每阶段的完整上下文快照
```

## 技术架构

```
app/
├── engine/
│   ├── session.py          # 游戏主循环（~300行），阶段调度 + 事件持久化
│   ├── handlers/           # 阶段处理器（night/day/sheriff/skills/setup）
│   ├── llm_bridge.py       # 统一 LLM 决策管道（tool call + retry + fallback）
│   ├── event_helpers.py    # 事件创建/发布快捷方法
│   ├── bootstrap.py        # 游戏初始化：配置加载 → 编译 → 建图 → 运行
│   ├── config_loader.py    # YAML 配置 → RuntimeConfig 编译
│   ├── graph.py            # 自定义 CompiledGraph（非 LangGraph）
│   ├── graph_viz.py        # Mermaid/DOT/PNG 导出
│   └── rules.py            # 胜负判定（屠边规则）
├── domain/                 # 纯数据类型（Role, Phase, GameState, PhaseResult, ...）
├── services/               # LLM 客户端、动作校验、提示词模板、上下文构建
├── infra/                  # SQLite 持久化层（EventBus, repositories）
├── ui/                     # Textual TUI（app, db_view, i18n）
└── configs/                # YAML 游戏配置 + Jinja2 提示词模板
```

### 设计模式

- **配置驱动**：YAML 定义角色、流程、规则、提示词、工具，新板子只需新配置
- **阶段处理器分发**：`PHASE_HANDLERS` dict 映射 Phase → handler，每个返回 PhaseResult
- **三层动作管线**：ProposedAction → ValidatedAction → ResolvedAction，LLM 输出必须经过校验
- **信息隔离**：每个玩家只能看到自己视角的信息（公共 + 阵营 + 私有）
- **事件溯源**：每个阶段边界写入 snapshot + events，TUI 从 DB 读取
- **实时 live events**：handler 内部 `emit_event` 立即写入 DB + EventBus 通知 TUI
- **双链路 LLM**：优先 LLM，失败/超限时回退到本地随机策略
