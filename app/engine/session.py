"""Game session loop — orchestrates phase handlers, persistence, and events.

All business logic lives in app/engine/handlers/.
All LLM interaction lives in app/engine/llm_bridge.py.
"""
from __future__ import annotations

import asyncio
import inspect
import json
import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from time import monotonic
from typing import Any

TZ_CN = timezone(timedelta(hours=8))
from random import Random

from app.config import AppPaths, LLMSettings, get_paths
from app.domain.events import GameEvent
from app.domain.roles import EventScope, EventType, GameStatus, Phase
from app.domain.state import (
    GameState,
    PhaseResult,
    apply_state_patch,
    next_phase,
    snapshot_state,
)
from app.engine.handlers import PHASE_HANDLERS
from app.engine.human import HumanAwaiter
from app.infra.events import EventBus
from app.infra.repositories.events import insert_events
from app.infra.repositories.games import finalize_game, insert_game_players
from app.infra.repositories.metrics import insert_game_metrics
from app.infra.repositories.snapshots import insert_snapshot
from app.services.context_builder import build_prompt_context
from app.services.llm import LLMClient

_log = logging.getLogger(__name__)


@dataclass(slots=True)
class SessionServices:
    conn: sqlite3.Connection
    event_bus: EventBus
    rng: Random
    paths: AppPaths
    llm_client: LLMClient | None = None
    llm_settings: LLMSettings | None = None
    llm_semaphore: asyncio.Semaphore | None = None
    event_seq: int = 1
    total_llm_calls: int = 0
    total_fallbacks: int = 0
    llm_callback: Any = None
    human_awaiter: HumanAwaiter | None = None
    _phase_started_emitted: bool = False


async def run_game_session(
    state: GameState,
    *,
    conn: sqlite3.Connection,
    event_bus: EventBus | None = None,
    llm_settings: LLMSettings | None = None,
    llm_callback: Any = None,
    max_steps: int = 200,
    human_awaiter: HumanAwaiter | None = None,
) -> GameState:
    started = monotonic()
    services = SessionServices(
        conn=conn,
        event_bus=event_bus or EventBus(),
        rng=Random(state["seed"]),
        paths=get_paths(),
        llm_client=LLMClient(llm_settings) if llm_settings is not None else None,
        llm_settings=llm_settings,
        llm_semaphore=asyncio.Semaphore(llm_settings.max_concurrency) if llm_settings is not None else None,
        llm_callback=llm_callback,
        human_awaiter=human_awaiter,
    )
    insert_game_players(conn, game_id=state["game_id"], state=state)

    steps = 0
    while not state["ended"] and steps < max_steps:
        steps += 1
        current_phase = state["phase"]
        current_round = state["round"]

        # Mark that phase_started hasn't been emitted yet for this phase
        services._phase_started_emitted = False

        try:
            result = await _handle_phase(state, services)
        except Exception as exc:
            _log.exception("phase %s failed for game %s", current_phase.value, state["game_id"])
            _ensure_phase_started(services, state, conn, current_phase, current_round)
            state = apply_state_patch(state, {"status": GameStatus.FAILED, "ended": True, "winner": None})
            error_event = GameEvent(
                game_id=state["game_id"], phase=current_phase,
                scope=EventScope.SYSTEM, target_players=set(),
                event_type=EventType.ERROR_RAISED,
                content=f"event.{EventType.ERROR_RAISED.value}",
                data={"phase": current_phase.value, "round": current_round, "error": str(exc)},
            )
            services.event_seq = _publish_and_persist(services, state, [error_event], round_no=current_round)
            break

        # Skip phase — no persistence
        if result.get("skip_phase"):
            state = _apply_phase_result(state, result)
            continue

        # Ensure phase_started was emitted (handlers with no live events won't have triggered it)
        _ensure_phase_started(services, state, conn, current_phase, current_round)

        # End event after handler actions
        end_event = GameEvent(
            game_id=state["game_id"], phase=current_phase,
            scope=EventScope.SYSTEM, target_players=set(),
            event_type=EventType.PHASE_ENDED,
            content=f"event.{EventType.PHASE_ENDED.value}",
            data={"phase": current_phase.value, "round": current_round},
        )
        events = result.get("events", [])
        persisted_event_count = int(result.get("persisted_event_count", 0))
        persisted_events = events[persisted_event_count:] + [end_event]
        services.event_seq = _publish_and_persist(services, state, persisted_events, round_no=current_round)
        state = _apply_phase_result(state, result)
        insert_snapshot(
            conn, game_id=state["game_id"], seq=services.event_seq,
            round_no=current_round, phase=current_phase.value,
            snapshot_type="phase_end", state_json=snapshot_state(state),
        )
        _save_player_contexts(services, state)

        if state["ended"]:
            break

    if not state["ended"]:
        state = apply_state_patch(state, {"status": GameStatus.FAILED, "ended": True, "winner": None})
        error_event = GameEvent(
            game_id=state["game_id"], phase=state["phase"],
            scope=EventScope.SYSTEM, target_players=set(),
            event_type=EventType.ERROR_RAISED,
            content=f"event.{EventType.ERROR_RAISED.value}",
            data={"max_steps": max_steps},
        )
        services.event_seq = _publish_and_persist(services, state, [error_event], round_no=state["round"])

    finalize_game(conn, state=state, end_reason="completed" if state["status"] == GameStatus.COMPLETED else "failed")
    insert_game_metrics(
        conn, game_id=state["game_id"],
        total_events=max(services.event_seq - 1, 0),
        total_llm_calls=services.total_llm_calls,
        total_fallbacks=services.total_fallbacks,
        duration_ms=int((monotonic() - started) * 1000),
        notes={"llm_enabled": services.llm_client is not None},
    )
    return state


# ---------------------------------------------------------------------------
# Phase dispatch
# ---------------------------------------------------------------------------


async def _handle_phase(state: GameState, services: SessionServices) -> PhaseResult:
    handler = PHASE_HANDLERS.get(state["phase"], _handle_noop)
    result = handler(state, services)
    if inspect.isawaitable(result):
        return await result
    await asyncio.sleep(0)
    return result


def _handle_noop(state: GameState, services: SessionServices) -> PhaseResult:
    return PhaseResult(events=[], state_patch={})


# ---------------------------------------------------------------------------
# Event persistence (used by event_helpers.py and handlers)
# ---------------------------------------------------------------------------


def _ensure_phase_started(services: SessionServices, state: GameState, conn: sqlite3.Connection, phase: Phase, round_no: int) -> None:
    """Emit phase_started if not already emitted for this phase."""
    if services._phase_started_emitted:
        return
    services._phase_started_emitted = True
    insert_snapshot(
        conn, game_id=state["game_id"], seq=services.event_seq,
        round_no=round_no, phase=phase.value,
        snapshot_type="phase_start", state_json=snapshot_state(state),
    )
    start_event = _phase_event(state, EventType.PHASE_STARTED)
    services.event_seq = _publish_and_persist(services, state, [start_event], round_no=round_no)


def _publish_and_persist(services: SessionServices, state: GameState, events: list[GameEvent], *, round_no: int) -> int:
    next_seq = insert_events(
        services.conn, game_id=state["game_id"],
        round_no=round_no, start_seq=services.event_seq, events=events,
    )
    for event in events:
        services.event_bus.publish(event)
    return next_seq


def _phase_event(state: GameState, event_type: EventType) -> GameEvent:
    return GameEvent(
        game_id=state["game_id"], phase=state["phase"],
        scope=EventScope.SYSTEM, target_players=set(),
        event_type=event_type,
        content=f"event.{event_type.value}",
        data={"phase": state["phase"].value, "round": state["round"]},
    )


# ---------------------------------------------------------------------------
# State transition
# ---------------------------------------------------------------------------


def _apply_phase_result(state: GameState, result: PhaseResult) -> GameState:
    events = result.get("events", [])
    patch = dict(result.get("state_patch", {}))
    if events:
        public_history = list(state["public_history"])
        private_history = list(state["private_history"])
        for event in events:
            entry = {
                "phase": event.phase.value,
                "scope": event.scope.value,
                "event_type": event.event_type.value,
                "content": event.content,
                "data": event.data,
            }
            if event.scope in {EventScope.PUBLIC, EventScope.SYSTEM}:
                public_history.append(entry)
            else:
                private_history.append(entry)
        patch["public_history"] = public_history
        patch["private_history"] = private_history

    updated = apply_state_patch(state, patch)
    override = result.get("next_phase_override")

    if updated["ended"] and override is not None:
        phase_index = _phase_index_for(updated, override)
        return apply_state_patch(updated, {"phase": override, "phase_index": phase_index})
    if updated["ended"]:
        return updated
    if override is not None:
        phase_index = _phase_index_for(updated, override)
        return apply_state_patch(updated, {"phase": override, "phase_index": phase_index})

    phase = next_phase(updated)
    phase_index = min(updated["phase_index"] + 1, len(updated["runtime"]["phase_order"]) - 1)
    return apply_state_patch(updated, {"phase": phase, "phase_index": phase_index})


def _phase_index_for(state: GameState, phase: Phase) -> int:
    current = state["phase_index"]
    phases = state["runtime"]["phase_order"]
    for idx in range(current + 1, len(phases)):
        if phases[idx] == phase:
            return idx
    for idx, item in enumerate(phases):
        if item == phase:
            return idx
    return current


# ---------------------------------------------------------------------------
# Context saving (for replay/analysis)
# ---------------------------------------------------------------------------


_CONTEXT_PHASES = frozenset({
    Phase.NIGHT_WOLF, Phase.NIGHT_SEER, Phase.NIGHT_WITCH,
    Phase.SHERIFF_ELECTION, Phase.DAY_SPEECH, Phase.DAY_VOTE,
    Phase.PENDING_SKILLS,
})


def _save_player_contexts(services: SessionServices, state: GameState) -> None:
    """Save each player's prompt context to files for replay/analysis."""
    if state["phase"] not in _CONTEXT_PHASES:
        return
    game_id = state["game_id"]
    phase_dir = services.paths.contexts / game_id / f"{state['round']}_{state['phase'].value}"
    phase_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now(TZ_CN).isoformat()
    for player_id, player in state["players"].items():
        context = build_prompt_context(state, player_id=player_id)
        payload = {
            "player_id": player_id,
            "role": player["role"].value,
            "alive": player["alive"],
            "round": state["round"],
            "phase": state["phase"].value,
            "public": context["public"],
            "faction": context["faction"],
            "private": context["private"],
            "saved_at": now,
        }
        (phase_dir / f"{player_id}.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
