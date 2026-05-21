"""Lobby room persistence.

A room is a pre-game holding pen for multi-human matches: 12 seats, one
host (whoever created it), an invite token (URL-shareable), and a status
('lobby' | 'started' | 'closed'). When the host hits start, we spawn a
game and the room transitions to 'started' with game_id set.

Schema lives in app/infra/schema.sql (tables `rooms`, `room_seats`).
"""
from __future__ import annotations

import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any, TypedDict

TZ_CN = timezone(timedelta(hours=8))


PLAYER_COUNT = 12


class RoomSeat(TypedDict):
    seat_index: int
    user_id: str | None
    nickname: str | None
    joined_at: str | None


class RoomRecord(TypedDict):
    id: str
    config_id: str
    host_user_id: str
    invite_token: str
    status: str
    game_id: str | None
    use_llm: bool
    created_at: str
    started_at: str | None
    closed_at: str | None
    seats: list[RoomSeat]


def _now() -> str:
    return datetime.now(TZ_CN).isoformat()


def _generate_token() -> str:
    # 16-char URL-safe token. Collision probability is negligible at this size.
    return secrets.token_urlsafe(12)


def create_room(
    conn: sqlite3.Connection,
    *,
    room_id: str,
    config_id: str,
    host_user_id: str,
    host_nickname: str,
    use_llm: bool = True,
) -> RoomRecord:
    """Create a fresh room with 12 AI seats; the host occupies seat 1."""
    invite_token = _generate_token()
    now = _now()
    with conn:
        conn.execute(
            """
            INSERT INTO rooms (id, config_id, host_user_id, invite_token,
                               status, use_llm, created_at)
            VALUES (?, ?, ?, ?, 'lobby', ?, ?)
            """,
            (room_id, config_id, host_user_id, invite_token, 1 if use_llm else 0, now),
        )
        # Seed all 12 seats — host on seat 1, AI on 2..12.
        for seat_index in range(1, PLAYER_COUNT + 1):
            if seat_index == 1:
                conn.execute(
                    """
                    INSERT INTO room_seats (room_id, seat_index, user_id, nickname, joined_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (room_id, 1, host_user_id, host_nickname, now),
                )
            else:
                conn.execute(
                    "INSERT INTO room_seats (room_id, seat_index) VALUES (?, ?)",
                    (room_id, seat_index),
                )
    record = get_room(conn, room_id=room_id)
    assert record is not None
    return record


def get_room(conn: sqlite3.Connection, *, room_id: str) -> RoomRecord | None:
    row = conn.execute(
        "SELECT id, config_id, host_user_id, invite_token, status, game_id, "
        "use_llm, created_at, started_at, closed_at "
        "FROM rooms WHERE id = ?",
        (room_id,),
    ).fetchone()
    if row is None:
        return None
    return _hydrate_room(conn, row)


def get_room_by_token(conn: sqlite3.Connection, *, invite_token: str) -> RoomRecord | None:
    row = conn.execute(
        "SELECT id, config_id, host_user_id, invite_token, status, game_id, "
        "use_llm, created_at, started_at, closed_at "
        "FROM rooms WHERE invite_token = ?",
        (invite_token,),
    ).fetchone()
    if row is None:
        return None
    return _hydrate_room(conn, row)


def list_open_rooms(conn: sqlite3.Connection, *, limit: int = 50) -> list[RoomRecord]:
    rows = conn.execute(
        "SELECT id, config_id, host_user_id, invite_token, status, game_id, "
        "use_llm, created_at, started_at, closed_at "
        "FROM rooms WHERE status = 'lobby' ORDER BY created_at DESC LIMIT ?",
        (limit,),
    ).fetchall()
    return [_hydrate_room(conn, row) for row in rows]


def claim_seat(
    conn: sqlite3.Connection,
    *,
    room_id: str,
    user_id: str,
    nickname: str,
    seat_index: int | None = None,
) -> RoomSeat | None:
    """Claim a seat in the room. If seat_index is None, pick the lowest
    available seat. If the user already holds a seat, return that one
    unchanged (idempotent for repeat joins). Returns None if the room is
    full or has no matching seat.
    """
    existing = conn.execute(
        "SELECT seat_index, user_id, nickname, joined_at FROM room_seats "
        "WHERE room_id = ? AND user_id = ?",
        (room_id, user_id),
    ).fetchone()
    if existing is not None:
        # Refresh nickname in case the user updated it before re-joining.
        with conn:
            conn.execute(
                "UPDATE room_seats SET nickname = ? WHERE room_id = ? AND seat_index = ?",
                (nickname, room_id, int(existing[0])),
            )
        return {
            "seat_index": int(existing[0]),
            "user_id": user_id,
            "nickname": nickname,
            "joined_at": existing[3],
        }
    target_seat: int | None = seat_index
    if target_seat is None:
        row = conn.execute(
            "SELECT seat_index FROM room_seats "
            "WHERE room_id = ? AND user_id IS NULL "
            "ORDER BY seat_index ASC LIMIT 1",
            (room_id,),
        ).fetchone()
        if row is None:
            return None
        target_seat = int(row[0])
    now = _now()
    with conn:
        cur = conn.execute(
            "UPDATE room_seats SET user_id = ?, nickname = ?, joined_at = ? "
            "WHERE room_id = ? AND seat_index = ? AND user_id IS NULL",
            (user_id, nickname, now, room_id, target_seat),
        )
        if cur.rowcount == 0:
            return None
    return {"seat_index": target_seat, "user_id": user_id, "nickname": nickname, "joined_at": now}


def release_seat(
    conn: sqlite3.Connection,
    *,
    room_id: str,
    seat_index: int,
) -> bool:
    """Reset a seat back to AI (user_id = NULL). Returns True if a seat was
    actually released (was previously held by a human)."""
    with conn:
        cur = conn.execute(
            "UPDATE room_seats SET user_id = NULL, nickname = NULL, joined_at = NULL "
            "WHERE room_id = ? AND seat_index = ? AND user_id IS NOT NULL",
            (room_id, seat_index),
        )
        return cur.rowcount > 0


def release_user(
    conn: sqlite3.Connection,
    *,
    room_id: str,
    user_id: str,
) -> int | None:
    """Release whatever seat the user holds. Returns the freed seat index
    or None if the user wasn't in the room."""
    row = conn.execute(
        "SELECT seat_index FROM room_seats WHERE room_id = ? AND user_id = ?",
        (room_id, user_id),
    ).fetchone()
    if row is None:
        return None
    seat_index = int(row[0])
    release_seat(conn, room_id=room_id, seat_index=seat_index)
    return seat_index


def mark_room_started(
    conn: sqlite3.Connection,
    *,
    room_id: str,
    game_id: str,
) -> None:
    with conn:
        conn.execute(
            "UPDATE rooms SET status = 'started', game_id = ?, started_at = ? "
            "WHERE id = ? AND status = 'lobby'",
            (game_id, _now(), room_id),
        )


def close_room(conn: sqlite3.Connection, *, room_id: str) -> None:
    with conn:
        conn.execute(
            "UPDATE rooms SET status = 'closed', closed_at = ? WHERE id = ?",
            (_now(), room_id),
        )


def delete_room(conn: sqlite3.Connection, *, room_id: str) -> None:
    with conn:
        conn.execute("DELETE FROM room_seats WHERE room_id = ?", (room_id,))
        conn.execute("DELETE FROM rooms WHERE id = ?", (room_id,))


def _hydrate_room(conn: sqlite3.Connection, row: Any) -> RoomRecord:
    seats = _load_seats(conn, room_id=row[0])
    return {
        "id": row[0],
        "config_id": row[1],
        "host_user_id": row[2],
        "invite_token": row[3],
        "status": row[4],
        "game_id": row[5],
        "use_llm": bool(row[6]),
        "created_at": row[7],
        "started_at": row[8],
        "closed_at": row[9],
        "seats": seats,
    }


def _load_seats(conn: sqlite3.Connection, *, room_id: str) -> list[RoomSeat]:
    rows = conn.execute(
        "SELECT seat_index, user_id, nickname, joined_at FROM room_seats "
        "WHERE room_id = ? ORDER BY seat_index ASC",
        (room_id,),
    ).fetchall()
    return [
        {
            "seat_index": int(row[0]),
            "user_id": row[1],
            "nickname": row[2],
            "joined_at": row[3],
        }
        for row in rows
    ]
