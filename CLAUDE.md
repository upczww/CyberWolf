# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI werewolf simulator (AI 狼人杀模拟器). All players are AI agents driven by LLM or local random fallback. Config-driven rules, SQLite persistence, Textual TUI for god-mode spectating.

## Commands

```bash
uv sync                    # Install dependencies
uv run wolf-game --config 12p_pre_witch_hunter_idiot --no-llm   # Run a game (no LLM)
uv run wolf-game --config 12p_pre_witch_hunter_idiot            # Run a game (with LLM)
uv run wolf-tui            # Launch TUI
uv run wolf-tui --game-id <id>  # Watch a specific game
```

No test runner yet — no tests exist currently.

## Architecture

```
app/
├── main.py              # wolf-game CLI entry point
├── config.py            # AppPaths, LLMSettings, dotenv loading
├── configs/             # YAML game configs + Jinja2 prompt templates
├── domain/              # Pure types, no external dependencies
│   ├── roles.py         # StrEnum types: Role, Faction, Phase, EventType, EventScope, WinRule, GameStatus
│   ├── config.py        # TypedDict types: GameConfig, RuntimeConfig, RoleSpec, RuleFlags, ToolSpec
│   ├── state.py         # GameState, PlayerState, PhaseResult, state helpers (init, patch, snapshot)
│   ├── actions.py       # ProposedAction -> ValidatedAction -> ResolvedAction (3-layer action pipeline)
│   ├── events.py        # GameEvent dataclass
│   └── context.py       # PublicContext, FactionContext, RolePrivateContext, GodContext, PromptContext
├── engine/              # Game loop and orchestration (all async)
│   ├── bootstrap.py     # Full bootstrap: load config -> compile runtime -> build graph -> init DB -> run
│   ├── session.py       # Main game loop, all 14 phase handlers in _PHASE_HANDLERS dispatch dict
│   ├── graph.py         # Custom CompiledGraph (not LangGraph), built from RuntimeConfig
│   ├── graph_viz.py     # Export to Mermaid / DOT / PNG
│   ├── config_loader.py # Load YAML, validate, compile RuntimeConfig with phase pruning
│   ├── rules.py         # check_win() and rule adjudication
│   ├── reducers.py      # Placeholder
│   └── replay.py        # Placeholder
├── services/            # External integrations
│   ├── llm.py           # TOOL_REGISTRY (8 tools), LLMClient with retry, raw HTTP (no SDK)
│   ├── llm_provider.py  # OpenAICompatibleProvider + DeepSeekProvider, provider lookup
│   ├── decisions.py     # validate_tool_call() + resolve_action()
│   ├── prompts.py       # Template resolution (phase+role -> fallback -> default), {{ var }} substitution
│   ├── context_builder.py # build_prompt_context() with information isolation
│   └── summaries.py     # Placeholder
├── infra/               # Persistence and events
│   ├── db.py            # SQLite connection (WAL mode)
│   ├── schema.sql       # 7 tables: games, game_players, game_events, state_snapshots, llm_calls, game_metrics, configs
│   ├── events.py        # EventBus (per-session, not global singleton)
│   └── repositories/    # CRUD for each table
├── ui/                  # Textual TUI
│   ├── app.py           # WerewolfApp — card layout, event log, toolbar, game launching
│   ├── commands.py      # wolf-tui CLI entry point
│   ├── db_view.py       # Read-only DB loader for TUI
│   ├── i18n.py          # Bilingual zh/en translations (~130 keys)
│   └── widgets/         # Placeholder files (rendering is inlined in app.py)
└── data/                # Runtime data (gitignored)
    ├── wolf.sqlite3
    └── graphs/          # Per-game graph exports
```

## Key Design Patterns

- **Config-driven gameplay**: YAML defines roles, phases, rules, prompts, tools. `RuntimeConfig` is compiled with role-based phase pruning. New boards = new config + minimal code.
- **Phase handler dispatch**: `_PHASE_HANDLERS` dict maps `Phase` enum to handler function. Each returns `PhaseResult` (state_patch + events + optional next_phase_override).
- **Three-layer action pipeline**: `ProposedAction` (LLM or fallback) -> `ValidatedAction` (rule-checked) -> `ResolvedAction` (effects applied). No raw tool args bypass validation.
- **Information isolation**: `PromptContext` = `PublicContext` + optional `FactionContext` + `RolePrivateContext`. Wolf teammates see each other; seer sees only own checks; GodContext never enters player prompts.
- **Event-sourced persistence**: Every phase boundary writes snapshots + events to SQLite. TUI reads from DB, not live state.
- **Dual-path LLM with fallback**: Try LLM first (if enabled and within budget), fall back to RNG-based local decisions. `--no-llm` disables entirely.
- **Custom graph, not LangGraph**: `CompiledGraph` with `GraphNode`, edges, and `ConditionalEdge` — functionally equivalent to LangGraph without the dependency.

## Known Gaps (vs PLAN.md)

- Win condition only checks all-wolves-dead and only-wolves-alive (full "slaughter-side" not yet implemented)
- Sheriff 1.5x vote weight not implemented
- Tie-breaking second vote not implemented (currently random pick)
- No tests exist
- `reducers.py`, `replay.py`, `summaries.py` are placeholders
- Only one game config (`12p_pre_witch_hunter_idiot.yaml`)
- Widget files are empty — rendering inlined in `app.py`

## Language

UI and configs are in Chinese (zh) with English (en) i18n support. Code comments and PLAN.md are in Chinese.
