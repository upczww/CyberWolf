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
第一轮：竞选警长 → 白天发言 → 投票放逐
后续轮：夜晚行动（狼人杀人 → 预言家查验 → 女巫用药）
       → 天亮公布死讯 → 检查胜负 → 白天发言 → 投票放逐
       → 死亡技能结算（猎人开枪、警徽移交） → 检查胜负
循环直到一方获胜
```

### 规则细节

- 第一轮白天前竞选警长，警长投票 1.5 倍权重（规划中）
- 狼人自爆：竞选/发言/投票阶段狼人可自爆，立即进入黑夜
- 女巫首夜不可自救
- 猎人被毒死不可开枪
- 警长死亡时可移交警徽或撕毁
- 平票时加赛一轮发言再投，再次平票则无人出局进入黑夜
- 胜负判定：屠边局（所有狼人死亡 = 好人胜；好人阵营全部死亡 = 狼人胜）

### LLM 集成

支持 OpenAI 兼容接口（DeepSeek、智谱 GLM 等），每个角色由 LLM 驱动决策：
- 夜间行动（狼人杀人、预言家查验、女巫用药）
- 白天发言（结构化 JSON 输出 + 内心独白）
- 投票决策
- 警长竞选

支持前缀缓存优化（~81% 缓存命中率），以及 LLM 调用失败时的本地随机回退。

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
LLM_ENABLED_PHASES=night_wolf,night_seer,night_witch,day_speech,day_vote
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
| `l` | 跳到最新一局 |
| `f` | 切换事件可见范围（公开/狼队/私有/上帝/系统） |
| `a` | 切换自动刷新 |
| `g` | 切换中英文 |
| `d` | 删除当前对局 |
| `q` | 退出 |

## 数据目录

```
data/
├── wolf.db            # SQLite 数据库（事件、快照、LLM 调用日志）
├── graphs/            # 每局游戏流程图（Mermaid/DOT/PNG）
├── contexts/          # 每个玩家每阶段的完整上下文快照
└── replays/           # 预留回放目录
```

## 技术架构

- **配置驱动**：YAML 定义角色、流程、规则、提示词、工具，新板子只需新配置
- **14 阶段主循环**：Phase handler dispatch 字典映射，每个阶段返回 state_patch + events
- **三层动作管线**：ProposedAction → ValidatedAction → ResolvedAction，所有 LLM 输出必须经过校验
- **信息隔离**：每个玩家只能看到自己视角的信息（公共 + 阵营 + 私有）
- **事件溯源**：每个阶段边界写入 snapshot + events，TUI 从 DB 读取而非直连内存
- **双链路 LLM**：优先 LLM，失败时回退到本地随机策略
- **自定义图引擎**：CompiledGraph（非 LangGraph），支持条件边和阶段裁剪
