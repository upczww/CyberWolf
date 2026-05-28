# CyberWolf - AI Werewolf Web Simulator

[中文](./README.md)

CyberWolf is an AI-driven Werewolf simulator. The project now primarily targets a **Web UI** powered by React + Vite, with FastAPI providing REST APIs and WebSocket live events. Electron, Textual TUI, and CLI entry points remain available for debugging, replay, and automation.

All non-human players can be driven by LLM agents or by a local random fallback. The backend is the source of truth for the game state machine, rules, timing, action validation, information isolation, and event persistence; the frontend follows backend events through REST + WebSocket updates.

## Current Focus

- **Web-first experience**: Game setup, god-mode spectating, personal player mode, human action panels, event feed, replay, portraits, visual progress, and BGM/SFX hooks.
- **Backend-driven flow**: Phases, timers, popups, pending human requests, and resolution are driven by backend events rather than frontend guesses.
- **Personal mode isolation**: Running human games require `seat` + `seat_token`. A player only sees their own private prompts, while wolves share wolf-team information.
- **God mode and replay**: Full-board view for debugging, spectating, flow audits, and historical replay.
- **Config-driven gameplay**: Roles, phases, prompts, tools, and rules are defined by YAML configs and compiled into a runtime game graph.
- **SQLite persistence**: Games, players, events, snapshots, LLM calls, configs, and metrics are stored for replay and debugging.

## Supported Board

The main supported config is `12p_pre_witch_hunter_idiot`.

| Faction | Role | Count |
| --- | --- | ---: |
| Wolves | Werewolf | 4 |
| Good | Seer | 1 |
| Good | Witch | 1 |
| Good | Hunter | 1 |
| Good | Idiot | 1 |
| Good | Villager | 4 |

## Gameplay Flow

```text
Night:
  night_start
  -> wolves choose a kill
  -> seer checks one target
  -> witch may use antidote / poison
  -> hunter status confirmation
  -> idiot identity confirmation
  -> night resolve
  -> pending death skills
  -> win check

Day:
  death announcement
  -> sheriff election on day 1
  -> public speeches
  -> vote / optional tie-break revote
  -> exile resolve
  -> pending death skills
  -> win check

Repeat until one faction wins.
```

## Rules Highlights

- Wolves pick one night kill target and may self-destruct during supported daytime phases.
- Seer checks one living target per night and receives a private good/wolf result.
- Witch has one antidote and one poison; each can be used once per game.
- Hunter can shoot when eligible, but cannot shoot if poisoned.
- Idiot reveals and survives when exiled, then loses voting power.
- Sheriff election happens before the first day discussion; sheriff votes count as 1.5.
- Tied votes trigger an additional speech/vote round; another tie exiles nobody.
- Dead players may receive last words and pending death skills are resolved in order.
- Win condition uses slaughter-side rules: all wolves dead means good wins; all villagers or all gods dead means wolves win.

## Quick Start - Web UI

### Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)
- Node.js 20+ recommended
- npm

### Install

```bash
git clone git@github.com:upczww/CyberWolf.git
cd CyberWolf

uv sync
cd desktop
npm install
```

### Run In Development

Start the backend API server from the repository root:

```bash
uv run uvicorn server.api:app --host 127.0.0.1 --port 8766
```

Start the Web UI in another terminal:

```bash
cd desktop
npm run dev
```

Open the Vite URL shown in the terminal, usually:

```text
http://127.0.0.1:5173
```

The dev server proxies `/api` and `/ws` traffic to the FastAPI backend.

### Optional Electron Mode

```bash
cd desktop
npm run electron:dev
```

Electron is a desktop shell around the same Web UI. The browser-based Web UI remains the recommended default.

## LLM Configuration

Create `.env` in the repository root if you want LLM-powered agents:

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

Without `.env`, or when running with `--no-llm`, the engine falls back to local random strategy so games can run offline.

## Useful Commands

### Web / Desktop

```bash
cd desktop
npm run dev          # Start Vite dev server
npm run build        # Build the Web UI
npm run test:flow    # Run frontend flow tests
npm run electron:dev # Optional Electron shell
```

### Backend / Engine

```bash
uv run uvicorn server.api:app --port 8766
uv run wolf-game --config 12p_pre_witch_hunter_idiot --no-llm
uv run wolf-game --config 12p_pre_witch_hunter_idiot
```

### Legacy TUI

```bash
uv run wolf-tui
uv run wolf-tui --game-id <id>
uv run wolf-tui --lang en
```

The Textual TUI is still useful for direct DB-backed spectating and debugging, but it is no longer the main product surface.

## API Overview

Key endpoints used by the Web UI:

| Endpoint | Purpose |
| --- | --- |
| `POST /api/games/start` | Start a new game |
| `GET /api/games` | List games |
| `GET /api/games/{game_id}` | Load game detail and snapshots |
| `DELETE /api/games/{game_id}` | Delete a game |
| `GET /api/games/{game_id}/human_pending` | Fetch pending human actions for a seat |
| `POST /api/games/{game_id}/human_action` | Submit a human action |
| `POST /api/games/{game_id}/replay` | Generate replay analysis |
| `WS /ws/games/{game_id}` | Stream history and live game events |

Personal-mode endpoints require a matching `seat` and `seat_token` while a human game is running. Finished games can be observed freely.

## Data Directory

```text
data/
  wolf.sqlite3       # SQLite database: games, players, events, snapshots, LLM calls
  graphs/            # Per-game graph exports
  contexts/          # Prompt/context snapshots for debugging
```

## Architecture

```text
app/
  domain/            # Pure role, phase, event, state, and action types
  engine/            # Async game loop, phase handlers, graph, rules, pacing
  services/          # LLM provider, decisions, prompts, context isolation, replay
  infra/             # SQLite, schema, event bus, repositories
  ui/                # Legacy Textual TUI
  configs/           # YAML boards and Jinja2 prompt templates

server/
  api.py             # FastAPI REST + WebSocket API
  music.py           # BGM generation endpoints

desktop/
  src/               # React Web UI
  electron/          # Optional Electron shell
  public/assets/     # Portraits, icons, UI art, optional audio assets
```

## Design Principles

- **Backend as source of truth**: Phase transitions, timers, human prompts, validation, and resolution are driven by backend events.
- **Three-layer action pipeline**: ProposedAction -> ValidatedAction -> ResolvedAction. LLM and human inputs both pass validation.
- **Information isolation**: Public, wolf-team, role-private, and god scopes are separated before reaching clients.
- **Event-sourced UI**: Frontend state is rebuilt from snapshots and events, then updated live over WebSocket.
- **Fallback-safe agents**: LLM calls are optional and bounded; local strategy keeps games playable without network access.
- **Web-first, TUI-compatible**: The React Web UI is the primary surface; CLI/TUI remain available for operations and debugging.
