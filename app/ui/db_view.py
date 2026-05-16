"""Database view layer for TUI.

Supports two access patterns:
- Full load: initial view or game switch (load_game_view)
- Incremental: periodic refresh with only new events (GameViewCache)
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from app.infra.db import connect_database
from app.infra.repositories.events import fetch_events, fetch_events_after
from app.infra.repositories.games import delete_game, fetch_game, fetch_game_count, fetch_game_players, fetch_latest_game, fetch_recent_games
from app.infra.repositories.metrics import fetch_game_metrics
from app.infra.repositories.snapshots import fetch_latest_snapshot


class GameViewCache:
    """Persistent DB connection with incremental event loading.

    Avoids re-opening the connection and re-querying unchanged data every 0.5s.
    """

    def __init__(self, database: Path) -> None:
        self._database = database
        self._conn: sqlite3.Connection | None = None
        self._game_id: str | None = None
        self._scope: str = "all"
        self._last_seq: int = 0
        self._events: list[dict[str, Any]] = []
        self._slow_tick: int = 0  # counter for slow-path queries

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = connect_database(self._database)
        return self._conn

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def load_full(
        self,
        *,
        game_id: str | None = None,
        event_scope: str = "all",
        event_limit: int = 300,
    ) -> dict[str, Any] | None:
        """Full load — used on game switch, scope change, or force refresh."""
        conn = self.conn
        game = fetch_game(conn, game_id=game_id) if game_id else fetch_latest_game(conn)
        if game is None:
            return None
        gid = str(game["id"])
        self._game_id = gid
        self._scope = event_scope

        players = fetch_game_players(conn, game_id=gid)
        events = fetch_events(conn, game_id=gid, limit=event_limit, scope=event_scope)
        status_events = fetch_events(conn, game_id=gid, limit=1000, scope="all")
        snapshot = fetch_latest_snapshot(conn, game_id=gid)
        recent_games = fetch_recent_games(conn, limit=20)
        total_game_count = fetch_game_count(conn)
        metrics = fetch_game_metrics(conn, game_id=gid)

        decoded_snapshot = _decode_snapshot(snapshot)
        decoded_game = dict(game)
        _merge_game_from_snapshot(decoded_game, decoded_snapshot)
        decoded_players = [dict(row) for row in players]
        _merge_players_from_snapshot(decoded_players, decoded_snapshot)
        decoded_events = [_decode_event(dict(row)) for row in reversed(events)]
        decoded_status_events = [_decode_event(dict(row)) for row in reversed(status_events)]
        _merge_skill_labels(decoded_players, decoded_snapshot, decoded_status_events)
        _merge_action_badges(decoded_players, decoded_snapshot, decoded_status_events)

        # Cache events state
        self._events = decoded_events
        self._last_seq = max((e["seq"] for e in decoded_events), default=0)
        self._slow_tick = 0

        return {
            "game": decoded_game,
            "recent_games": [dict(row) for row in recent_games],
            "total_game_count": total_game_count,
            "players": decoded_players,
            "events": decoded_events,
            "snapshot": decoded_snapshot,
            "metrics": _decode_json_row(metrics, ["notes_json"]) if metrics is not None else None,
        }

    def load_incremental(self) -> dict[str, Any] | None:
        """Incremental load — only fetches new events + updated snapshot/players.

        Returns None if no changes detected. Returns full view dict otherwise.
        """
        if self._game_id is None:
            return None
        conn = self.conn
        gid = self._game_id

        # Fast path: only new events
        new_rows = fetch_events_after(conn, game_id=gid, after_seq=self._last_seq, scope=self._scope if self._scope != "all" else None)
        if not new_rows:
            return None  # No changes

        new_events = [_decode_event(dict(row)) for row in new_rows]
        self._events.extend(new_events)
        # Keep max 300 events in cache
        if len(self._events) > 300:
            self._events = self._events[-300:]
        self._last_seq = max((e["seq"] for e in self._events), default=self._last_seq)

        # Refresh snapshot + players (needed for player alive status, badges)
        snapshot = fetch_latest_snapshot(conn, game_id=gid)
        decoded_snapshot = _decode_snapshot(snapshot)
        game = fetch_game(conn, game_id=gid)
        decoded_game = dict(game) if game else {}
        _merge_game_from_snapshot(decoded_game, decoded_snapshot)

        players = fetch_game_players(conn, game_id=gid)
        decoded_players = [dict(row) for row in players]
        _merge_players_from_snapshot(decoded_players, decoded_snapshot)

        # Status events for badges — only refresh every 5 ticks (~2.5s)
        self._slow_tick += 1
        if self._slow_tick >= 5:
            self._slow_tick = 0
            status_events = fetch_events(conn, game_id=gid, limit=1000, scope="all")
            decoded_status_events = [_decode_event(dict(row)) for row in reversed(status_events)]
        else:
            decoded_status_events = self._events  # Use cached events as approximation

        _merge_skill_labels(decoded_players, decoded_snapshot, decoded_status_events)
        _merge_action_badges(decoded_players, decoded_snapshot, decoded_status_events)

        # Slow queries (recent_games, metrics) only on slow tick
        if self._slow_tick == 0:
            recent_games = fetch_recent_games(conn, limit=20)
            total_game_count = fetch_game_count(conn)
            metrics = fetch_game_metrics(conn, game_id=gid)
        else:
            recent_games = None
            total_game_count = None
            metrics = None

        result: dict[str, Any] = {
            "game": decoded_game,
            "players": decoded_players,
            "events": self._events,
            "snapshot": decoded_snapshot,
        }
        if recent_games is not None:
            result["recent_games"] = [dict(row) for row in recent_games]
            result["total_game_count"] = total_game_count
            result["metrics"] = _decode_json_row(metrics, ["notes_json"]) if metrics is not None else None
        return result

    def reset(self) -> None:
        """Reset cache state (e.g., on game switch)."""
        self._game_id = None
        self._last_seq = 0
        self._events = []
        self._slow_tick = 0


# ---------------------------------------------------------------------------
# Legacy API (still used by delete)
# ---------------------------------------------------------------------------


def load_game_view(
    database: Path,
    *,
    game_id: str | None = None,
    event_scope: str = "all",
    event_limit: int = 200,
) -> dict[str, Any] | None:
    """Legacy one-shot load. Use GameViewCache for repeated access."""
    conn = connect_database(database)
    try:
        game = fetch_game(conn, game_id=game_id) if game_id else fetch_latest_game(conn)
        if game is None:
            return None
        gid = str(game["id"])
        players = fetch_game_players(conn, game_id=gid)
        events = fetch_events(conn, game_id=gid, limit=event_limit, scope=event_scope)
        status_events = fetch_events(conn, game_id=gid, limit=1000, scope="all")
        snapshot = fetch_latest_snapshot(conn, game_id=gid)
        recent_games = fetch_recent_games(conn, limit=20)
        total_game_count = fetch_game_count(conn)
        metrics = fetch_game_metrics(conn, game_id=gid)
        decoded_snapshot = _decode_snapshot(snapshot)
        decoded_game = dict(game)
        _merge_game_from_snapshot(decoded_game, decoded_snapshot)
        decoded_players = [dict(row) for row in players]
        _merge_players_from_snapshot(decoded_players, decoded_snapshot)
        decoded_events = [_decode_event(dict(row)) for row in reversed(events)]
        decoded_status_events = [_decode_event(dict(row)) for row in reversed(status_events)]
        _merge_skill_labels(decoded_players, decoded_snapshot, decoded_status_events)
        _merge_action_badges(decoded_players, decoded_snapshot, decoded_status_events)
        return {
            "game": decoded_game,
            "recent_games": [dict(row) for row in recent_games],
            "total_game_count": total_game_count,
            "players": decoded_players,
            "events": decoded_events,
            "snapshot": decoded_snapshot,
            "metrics": _decode_json_row(metrics, ["notes_json"]) if metrics is not None else None,
        }
    finally:
        conn.close()


def delete_game_view(database: Path, *, game_id: str) -> None:
    conn = connect_database(database)
    try:
        delete_game(conn, game_id=game_id)
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Decode helpers
# ---------------------------------------------------------------------------


def _decode_snapshot(snapshot: sqlite3.Row | dict[str, Any] | None) -> dict[str, Any] | None:
    if snapshot is None:
        return None
    payload = dict(snapshot)
    state_json = payload.get("state_json")
    if isinstance(state_json, str):
        payload["state_json"] = json.loads(state_json)
    return payload


def _decode_event(payload: dict[str, Any]) -> dict[str, Any]:
    data_json = payload.get("data_json")
    if isinstance(data_json, str):
        payload["data_json"] = json.loads(data_json)
    return payload


def _merge_game_from_snapshot(game: dict[str, Any], snapshot: dict[str, Any] | None) -> None:
    if snapshot is None:
        return
    state = snapshot.get("state_json")
    if not isinstance(state, dict):
        return
    if state.get("round") is not None:
        game["round_count"] = state["round"]
    if state.get("status"):
        game["status"] = state["status"]
    game["winner"] = state.get("winner")
    game["current_phase"] = state.get("phase")


def _merge_players_from_snapshot(players: list[dict[str, Any]], snapshot: dict[str, Any] | None) -> None:
    if snapshot is None:
        return
    state = snapshot.get("state_json")
    if not isinstance(state, dict):
        return
    live_players = state.get("players")
    if not isinstance(live_players, dict):
        return
    for row in players:
        player_state = live_players.get(str(row["player_id"])) or live_players.get(row["player_id"])
        if not isinstance(player_state, dict):
            continue
        row["survived"] = 1 if player_state.get("alive", True) else 0
        row["is_sheriff"] = 1 if player_state.get("is_sheriff", False) else 0
        row["idiot_revealed"] = 1 if player_state.get("idiot_revealed", False) else 0
        row["death_round"] = player_state.get("death_round")
        row["death_cause"] = player_state.get("death_cause")


def _merge_skill_labels(
    players: list[dict[str, Any]],
    snapshot: dict[str, Any] | None,
    events: list[dict[str, Any]],
) -> None:
    state = snapshot.get("state_json") if snapshot else None
    state = state if isinstance(state, dict) else {}
    seer_checks = state.get("seer_checks") if isinstance(state.get("seer_checks"), list) else []
    seer_check_count = len(seer_checks) or sum(1 for event in events if event.get("event_type") == "seer_checked")
    witch_antidote_used = bool(state.get("witch_antidote_used", False)) or any(
        event.get("event_type") == "witch_used_antidote" for event in events
    )
    witch_poison_used = bool(state.get("witch_poison_used", False)) or any(
        event.get("event_type") == "witch_used_poison" for event in events
    )
    hunter_shots = {
        data.get("actor_id")
        for event in events
        if event.get("content") == "event.hunter_shot"
        for data in [event.get("data_json")]
        if isinstance(data, dict)
    }
    for row in players:
        role = row.get("role")
        if role == "seer":
            row["skill_label"] = f"验{seer_check_count}"
        elif role == "witch":
            row["skill_label"] = f"药{'✓' if witch_antidote_used else '-'} 毒{'✓' if witch_poison_used else '-'}"
        elif role == "hunter":
            row["skill_label"] = f"枪{'✓' if row.get('player_id') in hunter_shots else '-'}"
        elif role == "idiot":
            row["skill_label"] = f"翻{'✓' if row.get('idiot_revealed') else '-'}"


def _merge_action_badges(
    players: list[dict[str, Any]],
    snapshot: dict[str, Any] | None,
    events: list[dict[str, Any]],
) -> None:
    state = snapshot.get("state_json") if snapshot else None
    state = state if isinstance(state, dict) else {}
    badges_by_player: dict[int, list[str]] = {int(row["player_id"]): [] for row in players}

    # --- Source 1: snapshot state (always complete, scope-independent) ---

    # Seer checks
    seer_checks = state.get("seer_checks") if isinstance(state.get("seer_checks"), list) else []
    for check in seer_checks:
        if isinstance(check, dict):
            _add_badge(badges_by_player, check.get("target_id"), "🔍")

    # Wolf target (from night_actions)
    night_actions = state.get("night_actions") if isinstance(state.get("night_actions"), dict) else {}
    wolf_target = night_actions.get("wolf_target")
    if wolf_target is not None:
        _add_badge(badges_by_player, wolf_target, "🎯")

    # Witch antidote
    if night_actions.get("witch_use_antidote") and wolf_target is not None:
        _add_badge(badges_by_player, wolf_target, "💊")

    # Witch poison
    poison_target = night_actions.get("witch_poison_target")
    if poison_target is not None:
        _add_badge(badges_by_player, poison_target, "🧪")

    # Death badges + idiot revealed from player state (always accurate)
    _CAUSE_BADGE = {"wolf": "🔪", "poison": "☠", "hunter_shot": "🏹", "exile": "🗳", "self_destruct": "💥"}
    for pid, pstate in (state.get("players") or {}).items():
        if not isinstance(pstate, dict):
            continue
        if not pstate.get("alive", True):
            badge = _CAUSE_BADGE.get(pstate.get("death_cause"))
            if badge:
                _add_badge(badges_by_player, pid, badge)
        if pstate.get("idiot_revealed"):
            _add_badge(badges_by_player, pid, "🎭")

    # --- Source 2: events (only for info not in snapshot, e.g. hunter_shot target) ---

    for event in events:
        data = event.get("data_json")
        if not isinstance(data, dict):
            continue
        content = event.get("content")
        if content == "event.hunter_shot":
            _add_badge(badges_by_player, data.get("target_id"), "🔫")
        elif event.get("event_type") == "wolf_self_destruct":
            _add_badge(badges_by_player, data.get("player_id"), "💥")

    # Cleanup: remove target badges superseded by death badges
    _SUPERSEDED = {"🎯": "🔪", "🧪": "☠", "🔫": "🏹"}
    for badges in badges_by_player.values():
        for target_badge, death_badge in _SUPERSEDED.items():
            if target_badge in badges and death_badge in badges:
                badges.remove(target_badge)

    for row in players:
        badges = badges_by_player.get(int(row["player_id"]), [])
        if badges:
            row["action_badges"] = " ".join(badges)


def _add_badge(badges_by_player: dict[int, list[str]], player_id: object, badge: str) -> None:
    try:
        pid = int(player_id)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return
    badges = badges_by_player.get(pid)
    if badges is None or badge in badges:
        return
    badges.append(badge)



def _decode_json_row(row: sqlite3.Row | dict[str, Any], json_fields: list[str]) -> dict[str, Any]:
    payload = dict(row)
    for field in json_fields:
        value = payload.get(field)
        if isinstance(value, str):
            payload[field] = json.loads(value)
    return payload
