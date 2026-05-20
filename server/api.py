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

# Active game sessions: game_id -> (EventBus, asyncio.Task)
_active_games: dict[str, tuple[EventBus, asyncio.Task]] = {}


class WSSubscriber:
    """Per-WebSocket queue + seat + vote buffer.

    For self-mode (seat is not None) we never deliver another seat's vote_cast
    immediately — those would let the human "follow" the AI's vote in real
    time. Instead we buffer them until the round's vote_resolved or
    sheriff_elected arrives, then flush them right before the resolution event.
    """

    __slots__ = ("queue", "seat", "buffered_votes", "buffered_declares")

    def __init__(self, queue: asyncio.Queue, seat: int | None) -> None:
        self.queue = queue
        self.seat = seat
        self.buffered_votes: list[dict[str, Any]] = []
        self.buffered_declares: list[dict[str, Any]] = []

    def __hash__(self) -> int:
        return id(self)


# WebSocket subscribers: game_id -> set of WSSubscriber
_ws_subscribers: dict[str, set[WSSubscriber]] = {}
# Per-game HumanAwaiter
_human_awaiters: dict[str, HumanAwaiter] = {}
# Per-game human seat (for WS event filtering)
_human_seats: dict[str, int] = {}


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
    phase_delay_seconds: float = 0.0  # debug aid: hold each phase for visual/screenshot


class HumanActionRequest(BaseModel):
    actor_id: int
    tool_name: str
    args: dict[str, Any]


class StartGameResponse(BaseModel):
    game_id: str
    config_id: str
    human_seat: int | None = None


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
async def get_game(game_id: str, event_limit: int = 300, seat: int | None = None):
    """Get full game detail.

    Optional ``seat=N`` filters role_private / wolf_team events to those whose
    target_ids include seat N — mirrors the WS filter so the human player can
    safely call this endpoint without leaking other players' private info.
    """
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
        # Self-mode vote anti-leak: defer other seats' vote_cast until the
        # round's vote_resolved / sheriff_elected.
        decoded_events = _mask_vote_replay_for_seat(decoded_events, seat)

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
    """Start a new game."""
    paths = _get_paths()
    llm_settings = get_llm_settings() if req.use_llm else None

    # Resolve human seat: if human_join is true and no seat specified, pick at random 1-12.
    resolved_seat: int | None
    if req.human_join:
        if req.human_seat is None:
            import secrets
            resolved_seat = secrets.randbelow(12) + 1
        else:
            resolved_seat = req.human_seat
    else:
        resolved_seat = None

    event_bus = EventBus()
    game_id_holder: list[str] = []
    human_awaiter = HumanAwaiter() if resolved_seat is not None else None

    def on_started(gid: str) -> None:
        game_id_holder.append(gid)
        if resolved_seat is not None:
            _human_seats[gid] = resolved_seat
            if human_awaiter is not None:
                _human_awaiters[gid] = human_awaiter

    def on_event(event: GameEvent) -> None:
        gid = event.game_id
        subscribers = _ws_subscribers.get(gid, set())
        event_data = _serialize_event(event)
        scope = event.scope
        targets = event.target_players or set()
        et = event.event_type.value
        for sub in subscribers:
            seat = sub.seat
            if seat is not None and scope in (EventScope.ROLE_PRIVATE, EventScope.WOLF_TEAM):
                if seat not in targets:
                    continue
            # Self-mode anti-leak: buffer other seats' per-player decisions
            # (vote_cast / sheriff_declare) until their corresponding
            # resolution lands. The resolution + buffered batch then arrives
            # in one chunk so the human can't "follow" the AI's choices.
            if seat is not None and et == "vote_cast":
                voter = event.data.get("voter_id") if isinstance(event.data, dict) else None
                if voter is not None and int(voter) != seat:
                    sub.buffered_votes.append(event_data)
                    continue
            if seat is not None and et == "sheriff_declare":
                pid = event.data.get("player_id") if isinstance(event.data, dict) else None
                if pid is not None and int(pid) != seat:
                    sub.buffered_declares.append(event_data)
                    continue
            if seat is not None and et in ("sheriff_campaign", "sheriff_elected", "sheriff_direction") and sub.buffered_declares:
                pending = sub.buffered_declares
                sub.buffered_declares = []
                for ev in pending:
                    try:
                        sub.queue.put_nowait(ev)
                    except asyncio.QueueFull:
                        pass
            if seat is not None and et in ("vote_resolved", "sheriff_elected") and sub.buffered_votes:
                pending = sub.buffered_votes
                sub.buffered_votes = []
                for ev in pending:
                    try:
                        sub.queue.put_nowait(ev)
                    except asyncio.QueueFull:
                        pass
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
                _human_seats.pop(gid, None)
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
    return StartGameResponse(game_id=gid, config_id=req.config_id, human_seat=resolved_seat)


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


@app.post("/api/games/{game_id}/human_action")
async def submit_human_action(game_id: str, req: HumanActionRequest):
    """Inject a human player's action into the awaiting phase handler."""
    awaiter = _human_awaiters.get(game_id)
    if awaiter is None:
        return {"accepted": False, "reason": "no_human_in_game"}
    expected_seat = _human_seats.get(game_id)
    if expected_seat is not None and req.actor_id != expected_seat:
        return {"accepted": False, "reason": "actor_mismatch"}
    accepted = await awaiter.submit(actor_id=req.actor_id, tool_name=req.tool_name, args=req.args)
    return {"accepted": accepted, "pending": awaiter.pending_snapshot()}


@app.get("/api/games/{game_id}/human_pending")
async def human_pending(game_id: str, seat: int | None = None):
    """Return actions currently awaiting human input (for reconnect).

    If ``seat=N`` is provided we only surface the entries whose actor matches
    that seat — anything else would leak the role of other seats via the
    ``tool_name`` field (e.g. an outstanding ``witch_antidote`` tells you who
    the witch is). Self-mode clients always call this with ``?seat=N``.
    """
    awaiter = _human_awaiters.get(game_id)
    if awaiter is None:
        return {"pending": [], "seat": seat}
    items = awaiter.pending_snapshot()
    if seat is not None:
        items = [p for p in items if p.get("actor_id") == seat]
    return {"pending": items, "seat": seat if seat is not None else _human_seats.get(game_id)}


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
    seat: int | None = None
    if seat_param:
        try:
            seat = int(seat_param)
        except ValueError:
            seat = None
    await websocket.accept()
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
                if seat is not None and ev.get("scope") in {"role_private", "wolf_team"}:
                    raw_targets = ev.get("target_ids_json") or "[]"
                    try:
                        targets = json.loads(raw_targets) if isinstance(raw_targets, str) else raw_targets
                    except (ValueError, TypeError):
                        targets = []
                    if seat not in targets:
                        continue
                decoded.append(ev)
            for ev in _mask_vote_replay_for_seat(decoded, seat):
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
    }


# ---------------------------------------------------------------------------
# Self-mode information isolation
# ---------------------------------------------------------------------------


def _mask_vote_replay_for_seat(events: list[dict[str, Any]], seat: int | None) -> list[dict[str, Any]]:
    """Rearrange a historical event list so that other-seat per-player
    decisions land in one batch right before their resolution event,
    instead of trickling out one at a time and letting a self-mode human
    "follow" the AI's choices.

    Two batched flows:
      * ``vote_cast`` (others)   →  flushed ahead of ``vote_resolved`` or
                                     ``sheriff_elected``.
      * ``sheriff_declare`` (others) → flushed ahead of ``sheriff_campaign``,
                                       ``sheriff_elected``, or ``sheriff_direction``
                                       (whichever marks candidacy closing).

    Self events (voter_id == seat / player_id == seat) are emitted in place.
    Buffered events whose resolution never landed (game in progress, mid-round
    reconnect) are dropped to avoid leaking partial information.
    """
    if seat is None:
        return events
    out: list[dict[str, Any]] = []
    vote_buf: list[dict[str, Any]] = []
    declare_buf: list[dict[str, Any]] = []
    flush_declare = ("sheriff_campaign", "sheriff_elected", "sheriff_direction")
    flush_vote = ("vote_resolved", "sheriff_elected")
    for ev in events:
        et = ev.get("event_type")
        data = ev.get("data_json") or ev.get("data") or {}
        if not isinstance(data, dict):
            data = {}

        if et == "vote_cast":
            voter = data.get("voter_id")
            try:
                if voter is not None and int(voter) == seat:
                    out.append(ev)
                    continue
            except (TypeError, ValueError):
                pass
            vote_buf.append(ev)
            continue

        if et == "sheriff_declare":
            pid = data.get("player_id")
            try:
                if pid is not None and int(pid) == seat:
                    out.append(ev)
                    continue
            except (TypeError, ValueError):
                pass
            declare_buf.append(ev)
            continue

        # Resolution markers — flush buffers ahead of the resolution event.
        if et in flush_declare and declare_buf:
            out.extend(declare_buf)
            declare_buf = []
        if et in flush_vote and vote_buf:
            out.extend(vote_buf)
            vote_buf = []
        out.append(ev)
    # Drop any unresolved buffered items — they'd leak partial info.
    return out

# Fields on `state_snapshots.state_json` that may leak private info to non-self
# seats; we drop them entirely from the seat=N response and only re-add the
# slice that belongs to the viewing seat.
_PRIVATE_STATE_FIELDS = (
    "private_history",       # mirror of role-private events
    "night_actions",         # wolf vote tally + witch antidote/poison targets
    "night_result",          # engine intermediate state
    "seed",                  # rng seed — knowing it lets you replay AI decisions
)


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
                    and (s.get("actor_id") == seat or s.get("kind") == "sheriff_transfer")
                ]

            snapshot["state_json"] = new_state
            detail["snapshot"] = snapshot

    return detail
