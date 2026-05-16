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
