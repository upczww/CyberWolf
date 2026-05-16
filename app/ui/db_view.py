from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from app.infra.db import connect_database
from app.infra.repositories.events import fetch_events
from app.infra.repositories.games import delete_game, fetch_game, fetch_game_players, fetch_latest_game, fetch_recent_games
from app.infra.repositories.llm_calls import fetch_llm_calls
from app.infra.repositories.metrics import fetch_game_metrics
from app.infra.repositories.snapshots import fetch_latest_snapshot, fetch_recent_snapshots


def load_game_view(
    database: Path,
    *,
    game_id: str | None = None,
    event_scope: str = "all",
    event_limit: int = 200,
) -> dict[str, Any] | None:
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
        snapshots = fetch_recent_snapshots(conn, game_id=gid, limit=20)
        metrics = fetch_game_metrics(conn, game_id=gid)
        llm_calls = fetch_llm_calls(conn, game_id=gid, limit=50)
        recent_games = fetch_recent_games(conn, limit=20)
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
            "players": decoded_players,
            "events": decoded_events,
            "snapshot": decoded_snapshot,
            "snapshots": [_decode_snapshot(row) for row in reversed(snapshots)],
            "metrics": _decode_json_row(metrics, ["notes_json"]) if metrics is not None else None,
            "llm_calls": [_decode_json_row(dict(row), []) for row in reversed(llm_calls)],
        }
    finally:
        conn.close()


def delete_game_view(database: Path, *, game_id: str) -> None:
    """Delete a game and all its data."""
    conn = connect_database(database)
    try:
        delete_game(conn, game_id=game_id)
    finally:
        conn.close()


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

    seer_checks = state.get("seer_checks") if isinstance(state.get("seer_checks"), list) else []
    for check in seer_checks:
        if isinstance(check, dict):
            _add_badge(badges_by_player, check.get("target_id"), "🔍")

    for event in events:
        data = event.get("data_json")
        if not isinstance(data, dict):
            continue
        event_type = event.get("event_type")
        content = event.get("content")
        if event_type == "wolf_target_selected":
            _add_badge(badges_by_player, data.get("target_id"), "🔪")
        elif event_type == "seer_checked":
            _add_badge(badges_by_player, data.get("target_id"), "🔍")
        elif event_type == "witch_used_antidote":
            _add_badge(badges_by_player, data.get("target_id"), "💊")
        elif event_type == "witch_used_poison":
            _add_badge(badges_by_player, data.get("target_id"), "☠️")
        elif content == "event.hunter_shot":
            _add_badge(badges_by_player, data.get("target_id"), "🏹")
        elif content == "event.idiot_revealed":
            _add_badge(badges_by_player, data.get("player_id"), "🎭")
        elif event_type == "wolf_self_destruct":
            _add_badge(badges_by_player, data.get("player_id"), "💥")
        elif event_type == "player_died":
            cause = data.get("cause")
            if cause == "wolf":
                _add_badge(badges_by_player, data.get("player_id"), "🔪")
            elif cause == "poison":
                _add_badge(badges_by_player, data.get("player_id"), "☠️")
            elif cause == "hunter_shot":
                _add_badge(badges_by_player, data.get("player_id"), "🏹")
            elif cause == "exile":
                _add_badge(badges_by_player, data.get("player_id"), "🗳️")
            elif cause == "self_destruct":
                _add_badge(badges_by_player, data.get("player_id"), "💥")

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
