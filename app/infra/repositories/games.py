from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone

TZ_CN = timezone(timedelta(hours=8))
from enum import Enum
from pathlib import Path
from typing import Any

from app.domain.config import RuntimeConfig
from app.domain.roles import GameStatus


def _json_default(value: Any) -> Any:
    if isinstance(value, set):
        return sorted(_json_default(item) for item in value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Path):
        return str(value)
    return value


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, default=_json_default, sort_keys=True)


def insert_game_bootstrap(
    conn: sqlite3.Connection,
    *,
    game_id: str,
    runtime: RuntimeConfig,
    seed: int,
    graph_artifacts: dict[str, str | None],
) -> None:
    now = datetime.now(TZ_CN).isoformat()
    conn.execute(
        """
        INSERT INTO games (
            id, status, started_at, round_count, config_id, config_json,
            prompt_profile_json, graph_mermaid_path, graph_dot_path, graph_png_path,
            seed, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            game_id,
            GameStatus.RUNNING.value,
            now,
            0,
            runtime["config_id"],
            _json_dumps(runtime),
            _json_dumps(runtime["prompt_profile"]),
            graph_artifacts.get("mermaid"),
            graph_artifacts.get("dot"),
            graph_artifacts.get("png"),
            seed,
            now,
        ),
    )
    conn.commit()


def insert_game_players(conn: sqlite3.Connection, *, game_id: str, state: dict) -> None:
    rows = []
    for player_id, player in sorted(state["players"].items()):
        rows.append(
            (
                game_id,
                player_id,
                player_id,
                player["role"].value,
                player["faction"].value,
                1 if player["is_sheriff"] else 0,
                1 if player["alive"] else 0,
                player["death_round"],
                player["death_cause"],
                None,
            )
        )
    conn.executemany(
        """
        INSERT INTO game_players (
            game_id, player_id, seat_index, role, faction, is_sheriff,
            survived, death_round, death_cause, summary_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    conn.commit()


def finalize_game(conn: sqlite3.Connection, *, state: dict, end_reason: str) -> None:
    now = datetime.now(TZ_CN).isoformat()
    conn.execute(
        """
        UPDATE games
        SET status = ?, ended_at = ?, winner = ?, round_count = ?, end_reason = ?
        WHERE id = ?
        """,
        (
            state["status"].value,
            now,
            state["winner"],
            state["round"],
            end_reason,
            state["game_id"],
        ),
    )
    for player_id, player in state["players"].items():
        conn.execute(
            """
            UPDATE game_players
            SET is_sheriff = ?, survived = ?, death_round = ?, death_cause = ?
            WHERE game_id = ? AND player_id = ?
            """,
            (
                1 if player["is_sheriff"] else 0,
                1 if player["alive"] else 0,
                player["death_round"],
                player["death_cause"],
                state["game_id"],
                player_id,
            ),
        )
    conn.commit()


__all__ = ["_json_dumps", "insert_game_bootstrap", "insert_game_players", "finalize_game"]


def fetch_latest_game(conn: sqlite3.Connection) -> sqlite3.Row | None:
    return conn.execute(
        """
        SELECT id, status, winner, round_count, config_id, started_at, ended_at, graph_mermaid_path, graph_dot_path, graph_png_path
        FROM games
        ORDER BY rowid DESC
        LIMIT 1
        """
    ).fetchone()


def fetch_game(conn: sqlite3.Connection, *, game_id: str) -> sqlite3.Row | None:
    return conn.execute(
        """
        SELECT id, status, winner, round_count, config_id, started_at, ended_at, graph_mermaid_path, graph_dot_path, graph_png_path
        FROM games
        WHERE id = ?
        """,
        (game_id,),
    ).fetchone()


def fetch_game_players(conn: sqlite3.Connection, *, game_id: str) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT player_id, seat_index, role, faction, is_sheriff, survived, death_round, death_cause
        FROM game_players
        WHERE game_id = ?
        ORDER BY seat_index ASC
        """,
        (game_id,),
    ).fetchall()


def fetch_recent_games(conn: sqlite3.Connection, *, limit: int = 20) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT id, status, winner, round_count, config_id, started_at, ended_at
        FROM games
        ORDER BY rowid DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()


def fetch_game_count(conn: sqlite3.Connection) -> int:
    return conn.execute("SELECT COUNT(*) FROM games").fetchone()[0]


def delete_game(conn: sqlite3.Connection, *, game_id: str) -> None:
    """Delete a game and all related data from the database."""
    conn.execute("DELETE FROM game_events WHERE game_id = ?", (game_id,))
    conn.execute("DELETE FROM state_snapshots WHERE game_id = ?", (game_id,))
    conn.execute("DELETE FROM llm_calls WHERE game_id = ?", (game_id,))
    conn.execute("DELETE FROM game_metrics WHERE game_id = ?", (game_id,))
    conn.execute("DELETE FROM game_players WHERE game_id = ?", (game_id,))
    conn.execute("DELETE FROM games WHERE id = ?", (game_id,))
    conn.commit()
