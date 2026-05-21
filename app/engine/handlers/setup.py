"""Setup and night-start phase handlers."""
from __future__ import annotations

from typing import TYPE_CHECKING

from app.domain.events import GameEvent
from app.domain.roles import EventScope, EventType
from app.domain.state import GameState, PhaseResult

if TYPE_CHECKING:
    from app.engine.session import SessionServices


async def handle_setup_game(state: GameState, services: SessionServices) -> PhaseResult:
    """Initial setup. Every human player (personal OR multi-human lobby)
    sees a confirm_identity prompt with 30s timeout. Prompts fire in
    parallel — each human's frontend shows their identity card
    immediately, and we don't gate any one human on another. The phase
    advances once everyone has confirmed or timed out.
    """
    import asyncio as _asyncio
    raw_seats = state.get("human_seats") or (
        {state["human_seat"]} if state.get("human_seat") is not None else set()
    )
    human_seats = sorted(raw_seats)
    if human_seats and services.human_awaiter is not None:
        # Phase narration ("对局准备中…") must fire BEFORE we publish the
        # per-human awaiting_human events so the frontend banners show
        # the setup phase rather than whatever came before.
        from app.engine.session import _ensure_phase_started
        _ensure_phase_started(services, state, services.conn, state["phase"], state["round"])
        from app.engine.llm_bridge import _await_human_action
        await _asyncio.gather(*[
            _await_human_action(
                state, services,
                actor_id=seat, role=state["players"][seat]["role"], phase=state["phase"],
                tool_name="confirm_identity", local_args={"confirmed": True},
            )
            for seat in human_seats
        ])
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
