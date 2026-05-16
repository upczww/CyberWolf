from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

TZ_CN = timezone(timedelta(hours=8))

from app.infra.repositories.games import _json_dumps


def insert_llm_call(
    conn: sqlite3.Connection,
    *,
    game_id: str,
    player_id: int | None,
    round_no: int,
    phase: str,
    model: str,
    tool_name: str | None,
    prompt_key: str | None,
    request_json: dict,
    response_json: dict | None,
    latency_ms: int,
    retry_count: int,
    fallback_level: int,
    success: bool,
    error_message: str | None,
) -> None:
    conn.execute(
        """
        INSERT INTO llm_calls (
            game_id, player_id, round, phase, model, tool_name, prompt_key,
            request_json, response_json, latency_ms, retry_count, fallback_level,
            success, error_message, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            game_id,
            player_id,
            round_no,
            phase,
            model,
            tool_name,
            prompt_key,
            _json_dumps(request_json),
            _json_dumps(response_json) if response_json is not None else None,
            latency_ms,
            retry_count,
            fallback_level,
            1 if success else 0,
            error_message,
            datetime.now(TZ_CN).isoformat(),
        ),
    )
    conn.commit()


def fetch_llm_calls(
    conn: sqlite3.Connection,
    *,
    game_id: str,
    limit: int = 50,
) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT player_id, round, phase, model, tool_name, prompt_key, latency_ms,
               retry_count, fallback_level, success, error_message, created_at
        FROM llm_calls
        WHERE game_id = ?
        ORDER BY rowid DESC
        LIMIT ?
        """,
        (game_id, limit),
    ).fetchall()
