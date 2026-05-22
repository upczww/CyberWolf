"""FastAPI server — REST + WebSocket API for the game engine.

Run with: uv run uvicorn server.api:app --port 8765
"""
from __future__ import annotations

import asyncio
import json
import logging
import secrets
import sqlite3
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.config import AppPaths, get_llm_settings, get_paths
from app.domain.events import GameEvent
from app.domain.roles import EventScope, EventType
from app.engine.bootstrap import bootstrap_and_run_game, list_config_ids
from app.engine.human import HumanAwaiter
from app.infra.db import connect_database, initialize_database
from app.infra.events import EventBus
from app.infra.repositories.games import fetch_game, fetch_game_players, fetch_recent_games, fetch_game_count
from app.infra.repositories.events import fetch_events
from app.infra.repositories.snapshots import fetch_latest_snapshot

_log = logging.getLogger(__name__)
TZ_CN = timezone(timedelta(hours=8))

# Active game sessions: game_id -> (EventBus, asyncio.Task)
_active_games: dict[str, tuple[EventBus, asyncio.Task]] = {}


class WSSubscriber:
    """Per-WebSocket queue + seat. Anti-vote-leak no longer needs subscriber-
    level buffering because the engine no longer emits per-voter vote_cast
    nor per-declarer sheriff_declare — both are folded into the aggregated
    vote_resolved / sheriff_elected events.
    """

    __slots__ = ("queue", "seat")

    def __init__(self, queue: asyncio.Queue, seat: int | None) -> None:
        self.queue = queue
        self.seat = seat

    def __hash__(self) -> int:
        return id(self)


# WebSocket subscribers: game_id -> set of WSSubscriber
_ws_subscribers: dict[str, set[WSSubscriber]] = {}
# Per-game HumanAwaiter
_human_awaiters: dict[str, HumanAwaiter] = {}
# Per-game set of human-controlled seats. Single-human mode uses a 1-elt
# set; multi-human lobby games carry every seated player. submit_human_
# action validates req.actor_id is in this set.
_human_seats: dict[str, set[int]] = {}
# Per-game per-seat bearer tokens. Personal / multi-human game clients must
# present the token for their own seat when asking for self-mode data or
# submitting actions. Pure AI/god games do not populate this map.
_seat_tokens: dict[str, dict[int, str]] = {}

# ---------------------------------------------------------------------------
# Lobby room state (in-process — DB is the source of truth, this caches
# WS subscribers per room)
# ---------------------------------------------------------------------------


class RoomWSSubscriber:
    """Per-WebSocket queue for a lobby room. We broadcast room state diffs
    (seat joined/left/kicked, room started) to every connected client."""

    __slots__ = ("queue", "user_id")

    def __init__(self, queue: asyncio.Queue, user_id: str | None) -> None:
        self.queue = queue
        self.user_id = user_id

    def __hash__(self) -> int:
        return id(self)


_room_ws_subscribers: dict[str, set[RoomWSSubscriber]] = {}


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

# Mount music generator router
from server.music import router as music_router
app.include_router(music_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve generated assets (BGM, avatars, etc.)
_assets_dir = Path(__file__).resolve().parents[1] / "desktop" / "public" / "assets"
_assets_dir.mkdir(parents=True, exist_ok=True)
app.mount("/assets", StaticFiles(directory=str(_assets_dir)), name="assets")


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class StartGameRequest(BaseModel):
    config_id: str = "12p_pre_witch_hunter_idiot"
    use_llm: bool = True
    human_join: bool = False
    human_seat: int | None = None  # if human_join is True and this is None, server picks at random
    # Multi-human lobby games supply the full set of human-controlled seats
    # directly (1..N). Overrides human_seat/human_join when provided.
    human_seats: list[int] | None = None
    phase_delay_seconds: float = 0.0  # debug aid: hold each phase for visual/screenshot


class HumanActionRequest(BaseModel):
    actor_id: int
    tool_name: str
    args: dict[str, Any]
    seat_token: str | None = None


class StartGameResponse(BaseModel):
    game_id: str
    config_id: str
    human_seat: int | None = None
    seat_token: str | None = None
    seat_tokens: dict[int, str] | None = None


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
async def get_game(
    game_id: str,
    event_limit: int = 300,
    seat: int | None = None,
    seat_token: str | None = None,
):
    """Get full game detail.

    Optional ``seat=N`` filters role_private / wolf_team events to those whose
    target_ids include seat N — mirrors the WS filter so the human player can
    safely call this endpoint without leaking other players' private info.
    """
    _require_seat_access(game_id, seat, seat_token)
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
            if seat is not None and ev.get("scope") in {"role_private", "wolf_team"}:
                raw_targets = ev.get("target_ids_json") or "[]"
                try:
                    targets = json.loads(raw_targets) if isinstance(raw_targets, str) else raw_targets
                except (ValueError, TypeError):
                    targets = []
                if seat not in targets:
                    continue
            decoded_events.append(ev)

        decoded_snapshot = None
        if snapshot:
            decoded_snapshot = dict(snapshot)
            if isinstance(decoded_snapshot.get("state_json"), str):
                decoded_snapshot["state_json"] = json.loads(decoded_snapshot["state_json"])

        detail = GameDetail(
            game=dict(game),
            players=[dict(row) for row in players],
            events=decoded_events,
            snapshot=decoded_snapshot,
        )
        if seat is not None:
            return _sanitize_detail_for_seat(detail.model_dump(), seat)
        return detail
    finally:
        conn.close()


@app.post("/api/games/start", response_model=StartGameResponse)
async def start_game(req: StartGameRequest):
    """Start a new game.

    Three modes:
    * Multi-human (req.human_seats supplied) — every listed seat is a
      human; remaining seats AI.
    * Personal (req.human_join + req.human_seat) — exactly one human seat.
    * God / observer (default) — pure AI game.
    """
    paths = _get_paths()
    llm_settings = get_llm_settings() if req.use_llm else None

    # Resolve the full set of human seats.
    resolved_seats: set[int] = set()
    if req.human_seats:
        resolved_seats = {int(s) for s in req.human_seats if 1 <= int(s) <= 12}
    elif req.human_join:
        if req.human_seat is None:
            import secrets
            resolved_seats = {secrets.randbelow(12) + 1}
        else:
            resolved_seats = {int(req.human_seat)}
    # Primary seat (used for the legacy `human_seat` field on the response
    # + the singular state.human_seat alias) is the smallest seat number.
    resolved_seat: int | None = min(resolved_seats) if resolved_seats else None

    event_bus = EventBus()
    game_id_holder: list[str] = []
    human_awaiter = HumanAwaiter() if resolved_seats else None
    issued_tokens = _issue_seat_tokens(resolved_seats)

    def on_started(gid: str) -> None:
        game_id_holder.append(gid)
        if resolved_seats:
            _human_seats[gid] = set(resolved_seats)
            _seat_tokens[gid] = dict(issued_tokens)
            conn = connect_database(paths.database)
            try:
                _persist_seat_tokens(conn, game_id=gid, seat_tokens=issued_tokens)
            finally:
                conn.close()
            if human_awaiter is not None:
                _human_awaiters[gid] = human_awaiter

    def on_event(event: GameEvent) -> None:
        gid = event.game_id
        subscribers = _ws_subscribers.get(gid, set())
        event_data = _serialize_event(event)
        scope = event.scope
        targets = event.target_players or set()
        for sub in subscribers:
            seat = sub.seat
            if seat is not None and scope == EventScope.GOD:
                # God-only events never reach a seat-bound (personal) client.
                continue
            if seat is not None and scope in (EventScope.ROLE_PRIVATE, EventScope.WOLF_TEAM):
                if seat not in targets:
                    continue
            try:
                sub.queue.put_nowait(event_data)
            except asyncio.QueueFull:
                pass

    event_bus.subscribe(on_event)

    async def run():
        try:
            boot = await bootstrap_and_run_game(
                paths=paths,
                config_id=req.config_id,
                llm_settings=llm_settings,
                event_bus=event_bus,
                on_game_started=on_started,
                human_seat=resolved_seat,
                human_seats=resolved_seats or None,
                human_awaiter=human_awaiter,
                phase_delay_seconds=req.phase_delay_seconds,
            )
        except Exception as exc:
            _log.exception("Game failed: %s", exc)
        finally:
            gid = game_id_holder[0] if game_id_holder else None
            if gid:
                if gid in _active_games:
                    del _active_games[gid]
                awaiter = _human_awaiters.pop(gid, None)
                if awaiter is not None:
                    await awaiter.cancel_all()

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
    primary_token = issued_tokens.get(resolved_seat) if resolved_seat is not None else None
    return StartGameResponse(
        game_id=gid,
        config_id=req.config_id,
        human_seat=resolved_seat,
        seat_token=primary_token,
        seat_tokens=issued_tokens or None,
    )


@app.delete("/api/games/{game_id}")
async def delete_game(game_id: str):
    """Stop a running game and delete its records.

    1) Cancel the engine task if it's still running so handlers stop awaiting.
    2) Cancel any outstanding human-awaiter futures so the frontend isn't
       stuck on a tool it'll never submit.
    3) Drop the SQLite rows.
    """
    from app.infra.repositories.games import delete_game as db_delete_game
    # 1) Cancel the engine task
    active = _active_games.pop(game_id, None)
    if active is not None:
        _bus, task = active
        if not task.done():
            task.cancel()
    # 2) Cancel any pending human awaiter futures
    awaiter = _human_awaiters.pop(game_id, None)
    if awaiter is not None:
        try:
            await awaiter.cancel_all()
        except Exception:
            pass
    _human_seats.pop(game_id, None)
    _seat_tokens.pop(game_id, None)
    # 3) Delete DB rows
    paths = _get_paths()
    conn = connect_database(paths.database)
    try:
        db_delete_game(conn, game_id=game_id)
        return {"deleted": game_id, "stopped": active is not None}
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


@app.post("/api/games/{game_id}/human_action")
async def submit_human_action(game_id: str, req: HumanActionRequest):
    """Inject a human player's action into the awaiting phase handler."""
    awaiter = _human_awaiters.get(game_id)
    if awaiter is None:
        return {"accepted": False, "reason": "no_human_in_game"}
    expected_seats = _human_seats.get(game_id) or set()
    if expected_seats and req.actor_id not in expected_seats:
        return {"accepted": False, "reason": "actor_mismatch"}
    if not _authorize_seat_access(game_id, req.actor_id, req.seat_token):
        return {"accepted": False, "reason": "unauthorized"}
    accepted = await awaiter.submit(actor_id=req.actor_id, tool_name=req.tool_name, args=req.args)
    return {"accepted": accepted, "pending": awaiter.pending_snapshot()}


@app.get("/api/games/{game_id}/human_pending")
async def human_pending(game_id: str, seat: int | None = None, seat_token: str | None = None):
    """Return actions currently awaiting human input (for reconnect).

    If ``seat=N`` is provided we only surface the entries whose actor matches
    that seat — anything else would leak the role of other seats via the
    ``tool_name`` field (e.g. an outstanding ``witch_antidote`` tells you who
    the witch is). Self-mode clients always call this with ``?seat=N``.
    """
    _require_seat_access(game_id, seat, seat_token)
    awaiter = _human_awaiters.get(game_id)
    if awaiter is None:
        return {"pending": [], "seat": seat}
    items = awaiter.pending_snapshot()
    if seat is not None:
        items = [p for p in items if p.get("actor_id") == seat]
    return {"pending": items, "seat": seat if seat is not None else _human_seats.get(game_id)}


# ---------------------------------------------------------------------------
# Lobby rooms (multi-human matchmaking)
# ---------------------------------------------------------------------------


class CreateRoomRequest(BaseModel):
    user_id: str  # client-generated UUID stored in localStorage
    nickname: str
    config_id: str = "12p_pre_witch_hunter_idiot"
    use_llm: bool = True


class JoinRoomRequest(BaseModel):
    user_id: str
    nickname: str


class KickRequest(BaseModel):
    host_user_id: str
    seat_index: int


class LeaveRequest(BaseModel):
    user_id: str


class StartRoomRequest(BaseModel):
    host_user_id: str


def _broadcast_room(room_id: str, payload: dict) -> None:
    subs = _room_ws_subscribers.get(room_id, set())
    for sub in list(subs):
        outbound = _personalize_room_payload(payload, sub.user_id)
        try:
            sub.queue.put_nowait(outbound)
        except asyncio.QueueFull:
            pass


def _personalize_room_payload(payload: dict, user_id: str | None) -> dict:
    outbound = dict(payload)
    if payload.get("type") == "room_started":
        owners = payload.get("seat_owners") or {}
        your_seat = None
        for seat, owner in owners.items():
            if user_id is not None and owner == user_id:
                your_seat = int(seat)
                break
        outbound["your_seat"] = your_seat
        outbound["seat_owners"] = {your_seat: user_id} if your_seat is not None and user_id is not None else {}
        tokens_by_user = outbound.pop("seat_tokens_by_user", {}) or {}
        if user_id is not None and user_id in tokens_by_user:
            outbound["seat_token"] = tokens_by_user[user_id]
    if payload.get("type") == "room_state" and isinstance(payload.get("room"), dict):
        outbound["room"] = _sanitize_room_for_user(payload["room"], user_id)
    return outbound


def _sanitize_room_for_user(room: dict, user_id: str | None) -> dict:
    sanitized = dict(room)
    if sanitized.get("host_user_id") != user_id:
        sanitized["host_user_id"] = "__host__"
    seats = []
    for seat in sanitized.get("seats") or []:
        item = dict(seat)
        if item.get("user_id") != user_id:
            item["user_id"] = "__occupied__" if item.get("user_id") else None
        seats.append(item)
    sanitized["seats"] = seats
    return sanitized


def _room_snapshot_payload(room: dict) -> dict:
    return {"type": "room_state", "room": room}


@app.post("/api/rooms")
async def create_room(req: CreateRoomRequest):
    """Create a fresh lobby room. The creator becomes the host on seat 1."""
    from uuid import uuid4
    from app.infra.repositories.rooms import create_room as repo_create_room
    paths = _get_paths()
    conn = connect_database(paths.database)
    try:
        room_id = str(uuid4())
        room = repo_create_room(
            conn,
            room_id=room_id,
            config_id=req.config_id,
            host_user_id=req.user_id,
            host_nickname=req.nickname.strip()[:24] or "玩家",
            use_llm=req.use_llm,
        )
        return {"room": _sanitize_room_for_user(room, req.user_id), "your_seat": 1}
    finally:
        conn.close()


@app.get("/api/rooms/{room_id}")
async def get_room(room_id: str, user_id: str | None = None):
    from app.infra.repositories.rooms import get_room as repo_get_room
    paths = _get_paths()
    conn = connect_database(paths.database)
    try:
        room = repo_get_room(conn, room_id=room_id)
        if room is None:
            return {"error": "room not found"}
        return {"room": _sanitize_room_for_user(room, user_id)}
    finally:
        conn.close()


@app.get("/api/rooms/by-token/{invite_token}")
async def get_room_by_token(invite_token: str, user_id: str | None = None):
    """Resolve an invite token to a room — used when a recipient clicks
    a share link. Returns the room so the frontend can render the lobby
    (or display "room already started" / "room closed" states)."""
    from app.infra.repositories.rooms import get_room_by_token as repo_get_by_token
    paths = _get_paths()
    conn = connect_database(paths.database)
    try:
        room = repo_get_by_token(conn, invite_token=invite_token)
        if room is None:
            return {"error": "invalid invite"}
        return {"room": _sanitize_room_for_user(room, user_id)}
    finally:
        conn.close()


@app.post("/api/rooms/{room_id}/join")
async def join_room(room_id: str, req: JoinRoomRequest):
    """Claim a seat in the room. Idempotent — repeat calls from the same
    user_id return the same seat (and refresh the nickname). Returns
    {your_seat: int} or {error} if the room is full / closed."""
    from app.infra.repositories.rooms import get_room as repo_get_room, claim_seat
    paths = _get_paths()
    conn = connect_database(paths.database)
    try:
        room = repo_get_room(conn, room_id=room_id)
        if room is None:
            return {"error": "room not found"}
        if room["status"] != "lobby":
            return {"error": "room already started or closed", "status": room["status"], "game_id": room.get("game_id")}
        nickname = req.nickname.strip()[:24] or "玩家"
        seat = claim_seat(conn, room_id=room_id, user_id=req.user_id, nickname=nickname)
        if seat is None:
            return {"error": "room is full"}
        room = repo_get_room(conn, room_id=room_id)
        _broadcast_room(room_id, _room_snapshot_payload(room))
        return {"your_seat": seat["seat_index"], "room": _sanitize_room_for_user(room, req.user_id)}
    finally:
        conn.close()


@app.post("/api/rooms/{room_id}/kick")
async def kick_seat(room_id: str, req: KickRequest):
    """Host removes a player from a seat. Seat reverts to AI."""
    from app.infra.repositories.rooms import get_room as repo_get_room, release_seat
    paths = _get_paths()
    conn = connect_database(paths.database)
    try:
        room = repo_get_room(conn, room_id=room_id)
        if room is None:
            return {"error": "room not found"}
        if room["host_user_id"] != req.host_user_id:
            return {"error": "only host can kick"}
        if req.seat_index == 1:
            return {"error": "host cannot be kicked"}
        if room["status"] != "lobby":
            return {"error": "room is not in lobby"}
        released = release_seat(conn, room_id=room_id, seat_index=req.seat_index)
        if not released:
            return {"error": "seat already empty"}
        room = repo_get_room(conn, room_id=room_id)
        _broadcast_room(room_id, _room_snapshot_payload(room))
        return {"kicked": req.seat_index, "room": _sanitize_room_for_user(room, req.host_user_id)}
    finally:
        conn.close()


@app.post("/api/rooms/{room_id}/leave")
async def leave_room(room_id: str, req: LeaveRequest):
    """A non-host player leaves the room voluntarily. If the host leaves,
    the room is closed (and any connected clients are notified)."""
    from app.infra.repositories.rooms import (
        get_room as repo_get_room,
        release_user,
        close_room as repo_close_room,
    )
    paths = _get_paths()
    conn = connect_database(paths.database)
    try:
        room = repo_get_room(conn, room_id=room_id)
        if room is None:
            return {"error": "room not found"}
        if room["host_user_id"] == req.user_id:
            repo_close_room(conn, room_id=room_id)
            _broadcast_room(room_id, {"type": "room_closed", "reason": "host_left"})
            return {"closed": True}
        released = release_user(conn, room_id=room_id, user_id=req.user_id)
        room = repo_get_room(conn, room_id=room_id)
        if room is not None:
            _broadcast_room(room_id, _room_snapshot_payload(room))
        return {"left_seat": released}
    finally:
        conn.close()


@app.post("/api/rooms/{room_id}/start")
async def start_room(room_id: str, req: StartRoomRequest):
    """Host starts the game. Resolves the human-controlled seats from the
    room's seat assignments, spawns a game with those seats, marks the
    room as started, and broadcasts a `room_started` message carrying the
    game_id so every connected client can transition into the game view."""
    from app.infra.repositories.rooms import (
        get_room as repo_get_room,
        mark_room_started,
    )
    paths = _get_paths()
    conn = connect_database(paths.database)
    try:
        room = repo_get_room(conn, room_id=room_id)
        if room is None:
            return {"error": "room not found"}
        if room["host_user_id"] != req.host_user_id:
            return {"error": "only host can start"}
        if room["status"] != "lobby":
            return {"error": "room already started", "game_id": room.get("game_id")}
        human_seats = [s["seat_index"] for s in room["seats"] if s["user_id"]]
        if not human_seats:
            return {"error": "no humans seated"}
    finally:
        conn.close()

    # Spawn the game using the same plumbing as /api/games/start.
    start_req = StartGameRequest(
        config_id=room["config_id"],
        use_llm=room["use_llm"],
        human_seats=human_seats,
    )
    started = await start_game(start_req)
    if isinstance(started, dict) and started.get("error"):
        return started
    game_id = started.game_id  # type: ignore[union-attr]
    seat_tokens = started.seat_tokens or {}  # type: ignore[union-attr]

    # Stamp the room and tell every connected lobby client to transition.
    conn = connect_database(paths.database)
    try:
        mark_room_started(conn, room_id=room_id, game_id=game_id)
    finally:
        conn.close()

    # Map seat_index -> user_id so each lobby client knows whether THEY
    # are seated (and at which seat) once the game opens.
    seat_owners = {s["seat_index"]: s["user_id"] for s in room["seats"] if s["user_id"]}
    seat_tokens_by_user = {
        user_id: seat_tokens.get(seat)
        for seat, user_id in seat_owners.items()
        if seat_tokens.get(seat) is not None
    }
    _broadcast_room(room_id, {
        "type": "room_started",
        "game_id": game_id,
        "seat_owners": seat_owners,
        "seat_tokens_by_user": seat_tokens_by_user,
    })
    host_seat = next((seat for seat, user_id in seat_owners.items() if user_id == req.host_user_id), None)
    return {
        "game_id": game_id,
        "human_seats": human_seats,
        "your_seat": host_seat,
        "seat_token": seat_tokens.get(host_seat) if host_seat is not None else None,
    }


@app.websocket("/ws/rooms/{room_id}")
async def room_websocket(websocket: WebSocket, room_id: str):
    """Live updates for the lobby — seat changes, kicks, host close, and
    the room_started transition message."""
    user_id = websocket.query_params.get("user_id")
    await websocket.accept()
    queue: asyncio.Queue = asyncio.Queue(maxsize=64)
    subs = _room_ws_subscribers.setdefault(room_id, set())
    subscriber = RoomWSSubscriber(queue, user_id)
    subs.add(subscriber)
    try:
        # Send the current room snapshot first.
        from app.infra.repositories.rooms import get_room as repo_get_room
        paths = _get_paths()
        conn = connect_database(paths.database)
        try:
            room = repo_get_room(conn, room_id=room_id)
        finally:
            conn.close()
        if room is not None:
            await websocket.send_json(_personalize_room_payload(_room_snapshot_payload(room), user_id))
        # Then stream live updates.
        while True:
            payload = await queue.get()
            await websocket.send_json(payload)
    except WebSocketDisconnect:
        pass
    finally:
        subs.discard(subscriber)
        if not subs:
            _room_ws_subscribers.pop(room_id, None)


# ---------------------------------------------------------------------------
# WebSocket
# ---------------------------------------------------------------------------


@app.websocket("/ws/games/{game_id}")
async def game_websocket(websocket: WebSocket, game_id: str):
    """Real-time game event stream via WebSocket.

    Optional query param ``seat=N`` restricts which scope=role_private /
    wolf_team events are forwarded — used by human-player clients to avoid
    leaking other players' private info.
    """
    seat_param = websocket.query_params.get("seat")
    seat_token = websocket.query_params.get("seat_token")
    seat: int | None = None
    if seat_param:
        try:
            seat = int(seat_param)
        except ValueError:
            seat = None
    await websocket.accept()
    if not _authorize_seat_access(game_id, seat, seat_token):
        await websocket.send_json({"type": "error", "error": "unauthorized"})
        await websocket.close(code=1008)
        return
    queue: asyncio.Queue = asyncio.Queue(maxsize=200)

    # Register subscriber
    if game_id not in _ws_subscribers:
        _ws_subscribers[game_id] = set()
    subscriber = WSSubscriber(queue, seat)
    _ws_subscribers[game_id].add(subscriber)

    try:
        # Send existing events as initial batch
        paths = _get_paths()
        conn = connect_database(paths.database)
        try:
            raw = fetch_events(conn, game_id=game_id, limit=300)
            decoded: list[dict[str, Any]] = []
            for row in reversed(raw):
                ev = dict(row)
                if isinstance(ev.get("data_json"), str):
                    ev["data_json"] = json.loads(ev["data_json"])
                # Filter private events for seat-bound subscribers
                if seat is not None and ev.get("scope") == "god":
                    # God-only events never reach a seat-bound (personal) client.
                    continue
                if seat is not None and ev.get("scope") in {"role_private", "wolf_team"}:
                    raw_targets = ev.get("target_ids_json") or "[]"
                    try:
                        targets = json.loads(raw_targets) if isinstance(raw_targets, str) else raw_targets
                    except (ValueError, TypeError):
                        targets = []
                    if seat not in targets:
                        continue
                decoded.append(ev)
            for ev in decoded:
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
        _ws_subscribers.get(game_id, set()).discard(subscriber)
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
        # seq/round are stamped by insert_events; ts is created at
        # GameEvent construction. The frontend uses seq to order events
        # and to dedupe history-vs-live arrivals — must be on the wire.
        "seq": event.seq,
        "round": event.round,
        "created_at": event.ts,
    }


def _issue_seat_tokens(seats: set[int]) -> dict[int, str]:
    return {int(seat): secrets.token_urlsafe(32) for seat in seats}


def _persist_seat_tokens(conn: sqlite3.Connection, *, game_id: str, seat_tokens: dict[int, str]) -> None:
    now = datetime.now(TZ_CN).isoformat()
    conn.executemany(
        """
        INSERT OR REPLACE INTO game_seat_tokens (game_id, seat_index, seat_token, created_at)
        VALUES (?, ?, ?, ?)
        """,
        [(game_id, int(seat), token, now) for seat, token in seat_tokens.items()],
    )
    conn.commit()


def _load_persisted_seat_tokens(game_id: str) -> dict[int, str]:
    paths = _get_paths()
    conn = connect_database(paths.database)
    try:
        rows = conn.execute(
            """
            SELECT seat_index, seat_token
            FROM game_seat_tokens
            WHERE game_id = ?
            """,
            (game_id,),
        ).fetchall()
    except sqlite3.OperationalError:
        return {}
    finally:
        conn.close()
    return {int(row["seat_index"]): str(row["seat_token"]) for row in rows}


def _authorize_seat_access(game_id: str, seat: int | None, seat_token: str | None) -> bool:
    human_seats = _human_seats.get(game_id) or set()
    if not human_seats:
        persisted_tokens = _load_persisted_seat_tokens(game_id)
        if persisted_tokens:
            _seat_tokens[game_id] = dict(persisted_tokens)
            _human_seats[game_id] = set(persisted_tokens)
            human_seats = set(persisted_tokens)
    if not human_seats:
        return True
    if seat is None or seat not in human_seats:
        return False
    expected = (_seat_tokens.get(game_id) or {}).get(seat)
    return bool(expected and seat_token and secrets.compare_digest(expected, seat_token))


def _require_seat_access(game_id: str, seat: int | None, seat_token: str | None) -> None:
    if not _authorize_seat_access(game_id, seat, seat_token):
        raise HTTPException(status_code=403, detail="unauthorized seat access")


# ---------------------------------------------------------------------------
# Self-mode information isolation
# ---------------------------------------------------------------------------


# Fields on `state_snapshots.state_json` that may leak private info to non-self
# seats; we drop them entirely from the seat=N response and only re-add the
# slice that belongs to the viewing seat.
_PRIVATE_STATE_FIELDS = (
    "private_history",       # mirror of role-private events
    "night_actions",         # wolf vote tally + witch antidote/poison targets
    "night_result",          # engine intermediate state
    "seed",                  # rng seed — knowing it lets you replay AI decisions
)

# Causes that are private to a night kill — the village only learns WHO
# died, not HOW. Public-cause deaths (exile / self_destruct / a daytime
# hunter shot) keep their cause.
_NIGHT_DEATH_CAUSES = frozenset({"wolf", "poison"})


def _mask_night_death_cause(player: dict[str, Any]) -> None:
    """Hide how a night death occurred (wolf kill / witch poison).

    The frontend derives the displayed cause from public events (which
    carry no cause for night deaths), so blanking the snapshot field
    just closes a raw-API leak without changing any visible UI.
    """
    if player.get("death_cause") in _NIGHT_DEATH_CAUSES:
        player["death_cause"] = None


def _sanitize_detail_for_seat(detail: dict[str, Any], seat: int | None) -> dict[str, Any]:
    """Mask other players' identities + private state when serving a self-mode
    client. Returns the same dict (mutated). For seat=None (god / observer
    mode the *client* is allowed to see everything) returns unchanged.

    Sanitization rules:
      * Players that are NOT the viewing seat AND still alive get role/faction
        replaced with ``"unknown"``.
      * Wolf-team mates are visible to a wolf viewer (they know each other).
      * Dead players' roles are revealed (mirrors normal werewolf rules
        where a dead player's identity is announced at dawn / vote-resolve).
      * ``snapshot.state_json.players`` is masked the same way.
      * Other role-private fields are stripped from snapshot.state_json unless
        the viewing seat owns that role:
          - ``seer_checks`` is kept only for the seer.
          - ``witch_antidote_used`` / ``witch_poison_used`` only for the witch.
          - ``night_actions`` only for wolves.
      * ``private_history`` and ``night_result`` are always dropped — they
        contain raw engine state mirroring private events.
    """
    if seat is None:
        return detail

    players = detail.get("players") or []
    # Locate viewing player to determine faction + role
    my_player: dict[str, Any] | None = None
    for p in players:
        try:
            if int(p.get("seat_index", -1)) == seat:
                my_player = p
                break
        except (TypeError, ValueError):
            continue
    my_role = (my_player or {}).get("role")
    my_faction = (my_player or {}).get("faction")
    wolf_seats: set[int] = set()
    if my_faction == "wolf":
        for p in players:
            try:
                if p.get("faction") == "wolf":
                    wolf_seats.add(int(p["seat_index"]))
            except (TypeError, ValueError):
                continue

    def _visible_role(seat_index: int, alive: bool) -> bool:
        # Self + dead + wolf-mates (when viewer is wolf) → role visible
        if seat_index == seat:
            return True
        if not alive:
            return True
        if seat_index in wolf_seats:
            return True
        return False

    # --- Mask top-level `players` list ---
    masked_players: list[dict[str, Any]] = []
    for p in players:
        mp = dict(p)
        try:
            si = int(mp.get("seat_index", -1))
        except (TypeError, ValueError):
            si = -1
        alive = bool(mp.get("survived", 1))
        if not _visible_role(si, alive):
            mp["role"] = "unknown"
            mp["faction"] = "unknown"
        _mask_night_death_cause(mp)
        masked_players.append(mp)
    detail["players"] = masked_players

    # --- Mask snapshot.state_json ---
    snapshot = detail.get("snapshot")
    if snapshot and isinstance(snapshot, dict):
        state = snapshot.get("state_json")
        if isinstance(state, dict):
            new_state = dict(state)
            # Mask `players` dict inside state
            sp = new_state.get("players")
            if isinstance(sp, dict):
                masked_sp: dict[Any, dict[str, Any]] = {}
                for pid, pl in sp.items():
                    try:
                        ipid = int(pid)
                    except (TypeError, ValueError):
                        ipid = -1
                    mpl = dict(pl)
                    alive = bool(mpl.get("alive", True))
                    if not _visible_role(ipid, alive):
                        mpl["role"] = "unknown"
                        mpl["faction"] = "unknown"
                    _mask_night_death_cause(mpl)
                    masked_sp[pid] = mpl
                new_state["players"] = masked_sp

            # Always strip raw private/internal fields
            for k in _PRIVATE_STATE_FIELDS:
                new_state.pop(k, None)

            # Role-gated fields
            if my_role != "seer":
                new_state["seer_checks"] = []
            if my_role != "witch":
                new_state.pop("witch_antidote_used", None)
                new_state.pop("witch_poison_used", None)

            # pending_skills can leak hidden roles (e.g. a queued
            # hunter_shot trigger on a dying seat reveals that seat as
            # a hunter). Keep only entries whose actor is the viewing
            # seat — they'll be asked to act on their own pending skill
            # via awaiting_human anyway.
            ps = new_state.get("pending_skills")
            if isinstance(ps, list):
                new_state["pending_skills"] = [
                    s for s in ps
                    if isinstance(s, dict)
                    and s.get("actor_id") == seat
                ]

            snapshot["state_json"] = new_state
            detail["snapshot"] = snapshot

    return detail
