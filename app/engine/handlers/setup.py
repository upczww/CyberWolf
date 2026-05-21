"""Setup and night-start phase handlers."""
from __future__ import annotations

from typing import TYPE_CHECKING

from app.domain.events import GameEvent
from app.domain.roles import EventScope, EventType
from app.domain.state import GameState, PhaseResult

if TYPE_CHECKING:
    from app.engine.session import SessionServices


async def handle_setup_game(state: GameState, services: SessionServices) -> PhaseResult:
    """Initial setup. In personal mode this also waits for the human player
    to acknowledge their identity card (tool=confirm_identity, 30s timeout).
    On timeout the awaiter falls back to {confirmed: True} so the game keeps
    moving — the human will simply have missed the reveal window.
    """
    human_seat = state.get("human_seat")
    if human_seat is not None and services.human_awaiter is not None:
        # Make sure phase_started + setup_game narration are emitted BEFORE we
        # block on confirm_identity — otherwise the frontend never learns the
        # game is in setup_game and the "对局准备中…" intro flash gets eaten
        # by the awaiting_human event arriving first.
        from app.engine.session import _ensure_phase_started
        _ensure_phase_started(services, state, services.conn, state["phase"], state["round"])
        from app.engine.llm_bridge import _await_human_action
        role = state["players"][human_seat]["role"]
        await _await_human_action(
            state, services,
            actor_id=human_seat, role=role, phase=state["phase"],
            tool_name="confirm_identity", local_args={"confirmed": True},
        )
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
