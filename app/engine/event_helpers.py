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


def emit_narration(
    services,
    state: GameState,
    events: list[GameEvent],
    text: str,
    *,
    kind: str = "info",
    glyph: str | None = None,
) -> None:
    """Emit a player-facing narration line.

    The frontend renders these as transient flash banners so the human can
    follow the game without having to interpret raw engine events. Keep the
    text concise (single sentence) and Chinese-natural.

    Args:
      text:  the narration sentence, e.g. "天亮了，昨晚是平安夜。"
      kind:  "info" / "good" / "wolf" / "gold" — drives the flash tone.
      glyph: optional emoji prefix (frontend may default one by kind).
    """
    payload: dict = {"text": text, "kind": kind, "round": state["round"]}
    if glyph is not None:
        payload["glyph"] = glyph
    emit_event(
        services, state, events,
        EventType.NARRATION,
        payload,
    )


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
