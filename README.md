# Wolf

AI 狼人杀模拟器，包含：
- 配置驱动的规则与流程
- SQLite 对局记录、事件、快照、LLM 调用日志
- Textual TUI 上帝视角界面
- OpenAI 兼容 LLM 接入与本地回退链路

## 环境

推荐使用 `uv` 管理依赖与运行环境。

### 1. 安装依赖

```bash
uv sync
```

### 2. 配置 `.env`

项目根目录的 `.env` 支持这些字段：

```dotenv
API_KEY=...
API_URL=...
MODEL_ID=...

LLM_PROVIDER=openai_compatible
LLM_ENABLED_PHASES=night_seer,night_witch
LLM_MAX_CALLS_PER_GAME=8
LLM_TIMEOUT_SECONDS=8
LLM_MAX_RETRIES=5
LLM_RETRY_BACKOFF_SECONDS=1
LLM_MAX_CONCURRENCY=2
LLM_VERIFY_SSL=true
```

说明：
- `API_URL` 需要是 OpenAI 兼容 chat completions 端点
- 若不希望启用真实 LLM，可在运行时使用 `--no-llm`
- `LLM_ENABLED_PHASES` 控制哪些阶段会尝试真实模型

## 运行

### 跑一局游戏

```bash
uv run wolf-game --config 12p_pre_witch_hunter_idiot --no-llm
```

启用真实 LLM：

```bash
uv run wolf-game --config 12p_pre_witch_hunter_idiot
```

### 启动 TUI

```bash
uv run wolf-tui
```

也可以指定对局：

```bash
uv run wolf-tui --game-id <game_id>
```

## TUI 快捷键

- `r`：手动刷新
- `n`：下一局
- `p`：上一局
- `l`：跳到最新一局
- `f`：切换事件 scope
- `a`：切换自动刷新
- `c`：切换用于启动新局的配置
- `m`：切换“启动新局时是否启用真实 LLM”
- `s`：启动新局
- `q`：退出

## 数据目录

- `data/wolf.db`：SQLite 数据库
- `data/graphs/`：每局导出的 graph 文件
- `data/replays/`：预留回放文件目录

## 当前状态

当前项目已具备：
- 可跑通的规则模拟主循环
- graph 导出与持久化
- `public_speech` / 夜间行动的工具化结构
- SQLite 事件、快照、metrics、llm_calls
- 可读取数据库的 Textual TUI

仍在持续迭代的部分：
- 更完整的规则细节
- 真实 LLM 发言质量
- 更强的 TUI 交互和对局控制
