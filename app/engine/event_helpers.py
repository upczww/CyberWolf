"""Event creation and publishing helpers.

Reduces boilerplate: one function call instead of 8-line GameEvent construction.
"""
from __future__ import annotations

from app.domain.events import GameEvent
from app.domain.roles import EventScope, EventType, Phase
from app.domain.state import GameState


def _event_content_key(event_type: EventType) -> str:
    return f"event.{event_type.value}"


def emit_event(
    services,  # SessionServices (forward ref to avoid circular import)
    state: GameState,
    events: list[GameEvent],
    event_type: EventType,
    data: dict,
    *,
    scope: EventScope = EventScope.PUBLIC,
    targets: set[int] | None = None,
    content: str | None = None,
) -> None:
    """Create a GameEvent and immediately persist + publish it (live event).

    Automatically emits phase_started before the first live event in a phase.
    """
    from app.engine.session import _ensure_phase_started, _publish_and_persist

    # Ensure phase_started is emitted before any handler events
    if hasattr(services, '_phase_started_emitted') and not services._phase_started_emitted:
        _ensure_phase_started(services, state, services.conn, state["phase"], state["round"])

    event = GameEvent(
        game_id=state["game_id"],
        phase=state["phase"],
        scope=scope,
        target_players=targets or set(),
        event_type=event_type,
        content=content or _event_content_key(event_type),
        data=data,
    )
    events.append(event)
    services.event_seq = _publish_and_persist(services, state, [event], round_no=state["round"])


def emit_speaking_started(
    services,
    state: GameState,
    events: list[GameEvent],
    *,
    player_id: int,
) -> None:
    """Emit a SPEAKING_STARTED live event."""
    emit_event(
        services, state, events,
        EventType.SPEAKING_STARTED,
        {"player_id": player_id},
    )


def action_source(services, phase: Phase) -> str:
    """Determine if an action comes from LLM or local fallback."""
    if services.llm_client is not None and services.llm_settings is not None and phase.value in services.llm_settings.enabled_phase_names:
        return "llm"
    return "fallback"


def make_event(
    state: GameState,
    event_type: EventType,
    data: dict,
    *,
    scope: EventScope = EventScope.PUBLIC,
    targets: set[int] | None = None,
    content: str | None = None,
) -> GameEvent:
    """Create a GameEvent without publishing (for batch use)."""
    return GameEvent(
        game_id=state["game_id"],
        phase=state["phase"],
        scope=scope,
        target_players=targets or set(),
        event_type=event_type,
        content=content or _event_content_key(event_type),
        data=data,
    )
