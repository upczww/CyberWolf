"""Setup and night-start phase handlers."""
from __future__ import annotations

from typing import TYPE_CHECKING

from app.domain.events import GameEvent
from app.domain.roles import EventScope, EventType
from app.domain.state import GameState, PhaseResult
from app.engine.event_helpers import _event_content_key

if TYPE_CHECKING:
    from app.engine.session import SessionServices


def handle_setup_game(state: GameState, services: SessionServices) -> PhaseResult:
    return PhaseResult(
        events=[
            GameEvent(
                game_id=state["game_id"],
                phase=state["phase"],
                scope=EventScope.GOD,
                target_players=set(),
                event_type=EventType.SKILL_TRIGGERED,
                content="event.game_setup_completed",
                data={"players": len(state["players"])},
            )
        ]
    )
