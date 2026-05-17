"""FastAPI server — REST + WebSocket API for the game engine.

Run with: uv run uvicorn server.api:app --port 8765
"""
from __future__ import annotations

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.config import AppPaths, get_llm_settings, get_paths
from app.domain.events import GameEvent
from app.engine.bootstrap import bootstrap_and_run_game, list_config_ids
from app.infra.db import connect_database, initialize_database
from app.infra.events import EventBus
from app.infra.repositories.games import fetch_game, fetch_game_players, fetch_recent_games, fetch_game_count
from app.infra.repositories.events import fetch_events
from app.infra.repositories.snapshots import fetch_latest_snapshot
from app.services.tts import tts_engine

_log = logging.getLogger(__name__)

# Active game sessions: game_id -> (EventBus, asyncio.Task)
_active_games: dict[str, tuple[EventBus, asyncio.Task]] = {}
# WebSocket subscribers: game_id -> set of queues
_ws_subscribers: dict[str, set[asyncio.Queue]] = {}


def _get_paths() -> AppPaths:
    return get_paths()


@asynccontextmanager
async def lifespan(app: FastAPI):
    paths = _get_paths()
    initialize_database(paths.database, paths.schema)
    yield
    # Cleanup active games
    for game_id, (bus, task) in _active_games.items():
        task.cancel()
    _active_games.clear()


app = FastAPI(title="LycanTUI API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class StartGameRequest(BaseModel):
    config_id: str = "12p_pre_witch_hunter_idiot"
    use_llm: bool = True


class StartGameResponse(BaseModel):
    game_id: str
    config_id: str


class GameSummary(BaseModel):
    id: str
    config_id: str | None = None
    status: str | None = None
    winner: str | None = None
    started_at: str | None = None
    ended_at: str | None = None


class GameDetail(BaseModel):
    game: dict[str, Any]
    players: list[dict[str, Any]]
    events: list[dict[str, Any]]
    snapshot: dict[str, Any] | None = None


class ReplayResponse(BaseModel):
    success: bool
    report: dict[str, Any] | None = None
    error: str | None = None


# ---------------------------------------------------------------------------
# REST Endpoints
# ---------------------------------------------------------------------------


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/api/configs")
async def list_configs():
    """List available game configurations."""
    paths = _get_paths()
    return {"configs": list_config_ids(paths.configs)}


@app.get("/api/games", response_model=list[GameSummary])
async def list_games(limit: int = 20):
    """List recent games."""
    paths = _get_paths()
    conn = connect_database(paths.database)
    try:
        rows = fetch_recent_games(conn, limit=limit)
        return [GameSummary(**dict(row)) for row in rows]
    finally:
        conn.close()


@app.get("/api/games/count")
async def game_count():
    paths = _get_paths()
    conn = connect_database(paths.database)
    try:
        return {"count": fetch_game_count(conn)}
    finally:
        conn.close()


@app.get("/api/games/{game_id}")
async def get_game(game_id: str, event_limit: int = 300):
    """Get full game detail."""
    paths = _get_paths()
    conn = connect_database(paths.database)
    try:
        game = fetch_game(conn, game_id=game_id)
        if game is None:
            return {"error": "game not found"}
        players = fetch_game_players(conn, game_id=game_id)
        events = fetch_events(conn, game_id=game_id, limit=event_limit)
        snapshot = fetch_latest_snapshot(conn, game_id=game_id)

        decoded_events = []
        for row in reversed(events):
            ev = dict(row)
            if isinstance(ev.get("data_json"), str):
                ev["data_json"] = json.loads(ev["data_json"])
            decoded_events.append(ev)

        decoded_snapshot = None
        if snapshot:
            decoded_snapshot = dict(snapshot)
            if isinstance(decoded_snapshot.get("state_json"), str):
                decoded_snapshot["state_json"] = json.loads(decoded_snapshot["state_json"])

        return GameDetail(
            game=dict(game),
            players=[dict(row) for row in players],
            events=decoded_events,
            snapshot=decoded_snapshot,
        )
    finally:
        conn.close()


@app.post("/api/games/start", response_model=StartGameResponse)
async def start_game(req: StartGameRequest):
    """Start a new game."""
    paths = _get_paths()
    llm_settings = get_llm_settings() if req.use_llm else None

    event_bus = EventBus()
    game_id_holder: list[str] = []

    def on_started(gid: str) -> None:
        game_id_holder.append(gid)

    # Subscribe WebSocket broadcaster
    def on_event(event: GameEvent) -> None:
        gid = event.game_id
        subscribers = _ws_subscribers.get(gid, set())
        event_data = _serialize_event(event)
        for queue in subscribers:
            try:
                queue.put_nowait(event_data)
            except asyncio.QueueFull:
                pass

    event_bus.subscribe(on_event)
    event_bus.subscribe(tts_engine.on_event)

    async def run():
        try:
            boot = await bootstrap_and_run_game(
                paths=paths,
                config_id=req.config_id,
                llm_settings=llm_settings,
                event_bus=event_bus,
                on_game_started=on_started,
            )
            tts_engine.set_player_roles(boot.state["players"])
        except Exception as exc:
            _log.exception("Game failed: %s", exc)
        finally:
            gid = game_id_holder[0] if game_id_holder else None
            if gid and gid in _active_games:
                del _active_games[gid]

    task = asyncio.create_task(run())

    # Wait for game_id to be assigned
    for _ in range(100):
        if game_id_holder:
            break
        await asyncio.sleep(0.05)

    if not game_id_holder:
        return {"error": "game failed to start"}

    gid = game_id_holder[0]
    _active_games[gid] = (event_bus, task)
    return StartGameResponse(game_id=gid, config_id=req.config_id)


@app.delete("/api/games/{game_id}")
async def delete_game(game_id: str):
    """Delete a game."""
    from app.infra.repositories.games import delete_game as db_delete_game
    paths = _get_paths()
    conn = connect_database(paths.database)
    try:
        db_delete_game(conn, game_id=game_id)
        return {"deleted": game_id}
    finally:
        conn.close()


@app.post("/api/games/{game_id}/replay", response_model=ReplayResponse)
async def replay_game(game_id: str):
    """Generate AI replay analysis."""
    from app.services.replay import generate_replay
    paths = _get_paths()
    llm_settings = get_llm_settings()
    if llm_settings is None:
        return ReplayResponse(success=False, error="LLM not configured")
    result = await generate_replay(paths.database, game_id, llm_settings)
    if result is None:
        return ReplayResponse(success=False, error="Replay generation failed")
    return ReplayResponse(success=True, report=result)


@app.post("/api/tts/toggle")
async def toggle_tts():
    """Toggle TTS on/off."""
    new_state = tts_engine.toggle()
    return {"enabled": new_state}


@app.get("/api/tts/status")
async def tts_status():
    return {"enabled": tts_engine.enabled}


# ---------------------------------------------------------------------------
# WebSocket
# ---------------------------------------------------------------------------


@app.websocket("/ws/games/{game_id}")
async def game_websocket(websocket: WebSocket, game_id: str):
    """Real-time game event stream via WebSocket."""
    await websocket.accept()
    queue: asyncio.Queue = asyncio.Queue(maxsize=200)

    # Register subscriber
    if game_id not in _ws_subscribers:
        _ws_subscribers[game_id] = set()
    _ws_subscribers[game_id].add(queue)

    try:
        # Send existing events as initial batch
        paths = _get_paths()
        conn = connect_database(paths.database)
        try:
            events = fetch_events(conn, game_id=game_id, limit=300)
            for row in reversed(events):
                ev = dict(row)
                if isinstance(ev.get("data_json"), str):
                    ev["data_json"] = json.loads(ev["data_json"])
                await websocket.send_json({"type": "history", "event": ev})
        finally:
            conn.close()

        await websocket.send_json({"type": "history_complete"})

        # Stream new events
        while True:
            event_data = await queue.get()
            await websocket.send_json({"type": "live", "event": event_data})
    except WebSocketDisconnect:
        pass
    finally:
        _ws_subscribers.get(game_id, set()).discard(queue)
        if game_id in _ws_subscribers and not _ws_subscribers[game_id]:
            del _ws_subscribers[game_id]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _serialize_event(event: GameEvent) -> dict[str, Any]:
    return {
        "game_id": event.game_id,
        "phase": event.phase.value,
        "scope": event.scope.value,
        "event_type": event.event_type.value,
        "content": event.content,
        "data": event.data,
    }
