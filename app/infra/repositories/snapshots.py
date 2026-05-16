from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

TZ_CN = timezone(timedelta(hours=8))

from app.infra.repositories.games import _json_dumps


def insert_snapshot(
    conn: sqlite3.Connection,
    *,
    game_id: str,
    seq: int,
    round_no: int,
    phase: str,
    snapshot_type: str,
    state_json: dict,
) -> None:
    conn.execute(
        """
        INSERT INTO state_snapshots (
            game_id, seq, round, phase, snapshot_type, state_json, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            game_id,
            seq,
            round_no,
            phase,
            snapshot_type,
            _json_dumps(state_json),
            datetime.now(TZ_CN).isoformat(),
        ),
    )
    conn.commit()


def fetch_latest_snapshot(conn: sqlite3.Connection, *, game_id: str) -> sqlite3.Row | None:
    return conn.execute(
        """
        SELECT seq, round, phase, snapshot_type, state_json, created_at
        FROM state_snapshots
        WHERE game_id = ?
        ORDER BY seq DESC, id DESC
        LIMIT 1
        """,
        (game_id,),
    ).fetchone()


def fetch_recent_snapshots(
    conn: sqlite3.Connection,
    *,
    game_id: str,
    limit: int = 20,
) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT seq, round, phase, snapshot_type, state_json, created_at
        FROM state_snapshots
        WHERE game_id = ?
        ORDER BY seq DESC, id DESC
        LIMIT ?
        """,
        (game_id, limit),
    ).fetchall()
