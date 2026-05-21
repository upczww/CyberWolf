from __future__ import annotations

from dataclasses import dataclass, field
from time import time
from typing import Any

from app.domain.roles import EventScope, EventType, Phase


@dataclass(slots=True)
class GameEvent:
    game_id: str
    phase: Phase
    scope: EventScope
    target_players: set[int]
    event_type: EventType
    content: str
    data: Any = None
    ts: float = field(default_factory=time)
    # Stamped by `insert_events` once the event is persisted — exposed
    # on the live WS payload so clients can order/dedupe history vs.
    # live events consistently.
    seq: int | None = None
    round: int | None = None
