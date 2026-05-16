from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

TZ_CN = timezone(timedelta(hours=8))

from app.domain.events import GameEvent
from app.infra.repositories.games import _json_dumps


def insert_events(
    conn: sqlite3.Connection,
    *,
    game_id: str,
    round_no: int,
    start_seq: int,
    events: list[GameEvent],
) -> int:
    seq = start_seq
    rows = []
    for event in events:
        rows.append(
            (
                game_id,
                seq,
                round_no,
                event.phase.value,
                event.scope.value,
                event.data.get("actor_id") if isinstance(event.data, dict) else None,
                _json_dumps(sorted(event.target_players)),
                event.event_type.value,
                event.content,
                _json_dumps(event.data) if event.data is not None else None,
                datetime.fromtimestamp(event.ts, tz=TZ_CN).isoformat(),
            )
        )
        seq += 1
    conn.executemany(
        """
        INSERT INTO game_events (
            game_id, seq, round, phase, scope, actor_id, target_ids_json,
            event_type, content, data_json, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    conn.commit()
    return seq


def fetch_events(
    conn: sqlite3.Connection,
    *,
    game_id: str,
    limit: int = 200,
    scope: str | None = None,
) -> list[sqlite3.Row]:
    if scope is None or scope == "all":
        return conn.execute(
            """
            SELECT seq, round, phase, scope, event_type, content, data_json, created_at
            FROM game_events
            WHERE game_id = ?
            ORDER BY seq DESC
            LIMIT ?
            """,
            (game_id, limit),
        ).fetchall()
    return conn.execute(
        """
        SELECT seq, round, phase, scope, event_type, content, data_json, created_at
        FROM game_events
        WHERE game_id = ? AND scope = ?
        ORDER BY seq DESC
        LIMIT ?
        """,
        (game_id, scope, limit),
    ).fetchall()
