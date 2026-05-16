from __future__ import annotations

import sqlite3

from app.infra.repositories.games import _json_dumps


def insert_game_metrics(
    conn: sqlite3.Connection,
    *,
    game_id: str,
    total_events: int,
    total_llm_calls: int,
    total_fallbacks: int,
    duration_ms: int,
    notes: dict | None = None,
) -> None:
    conn.execute(
        """
        INSERT INTO game_metrics (
            game_id, total_events, total_llm_calls, total_fallbacks, duration_ms, notes_json
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            game_id,
            total_events,
            total_llm_calls,
            total_fallbacks,
            duration_ms,
            _json_dumps(notes) if notes is not None else None,
        ),
    )
    conn.commit()


def fetch_game_metrics(conn: sqlite3.Connection, *, game_id: str) -> sqlite3.Row | None:
    return conn.execute(
        """
        SELECT total_events, total_llm_calls, total_fallbacks, duration_ms, notes_json
        FROM game_metrics
        WHERE game_id = ?
        ORDER BY rowid DESC
        LIMIT 1
        """,
        (game_id,),
    ).fetchone()
