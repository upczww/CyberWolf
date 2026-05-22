"""Game session — `transitions`-driven phase orchestrator.

The `GameSession` class IS the FSM model: each phase in the runtime's
`phase_order` is a state, and a single generic `_on_enter_phase`
callback is bound to every state. That callback dispatches the
registered handler, persists events, updates `GameState`, and triggers
the next transition via `await self.advance()` or
`await self.to_<phase>()`. With `queued=True`, the chain propagates
itself from initial state to terminal — no external `while` loop.

All phase business logic lives in `app/engine/handlers/`, decorated
with `@phase(...)` from `app.engine.registry`. All LLM interaction
lives in `app/engine/llm_bridge.py`.
"""
from __future__ import annotations

import asyncio
import inspect
import json
import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from random import Random
from time import monotonic
from typing import Any

from app.config import AppPaths, LLMSettings, get_paths
from app.domain.events import GameEvent
from app.domain.roles import EventScope, EventType, GameStatus, Phase
from app.domain.state import (
    GameState,
    PhaseResult,
    apply_state_patch,
    snapshot_state,
)
from app.engine.handlers import PHASE_HANDLERS
from app.engine.human import HumanAwaiter
from app.engine.pacing import start_phase_budget
from app.engine.state_machine import build_phase_machine
from app.infra.events import EventBus
from app.infra.repositories.events import insert_events
from app.infra.repositories.games import finalize_game, insert_game_players
from app.infra.repositories.metrics import insert_game_metrics
from app.infra.repositories.snapshots import insert_snapshot
from app.services.context_builder import build_prompt_context
from app.services.llm import LLMClient

TZ_CN = timezone(timedelta(hours=8))
_log = logging.getLogger(__name__)


# Every phase narration ("天黑请闭眼", "狼人请睁眼", "进入放逐投票"...)
# must stay visible at least this long before the next phase's narration
# is allowed to replace it. Phases that naturally take longer (LLM,
# human awaiters) pay no cost — the wait only kicks in for transitions
# that would otherwise flash by faster than a human can read.
MIN_PHASE_NARRATION_HOLD_SECONDS = 5.0


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
    phase_delay_seconds: float = 0.0  # debug/demo aid: pause after each phase
    _phase_started_emitted: bool = False
    _last_narration_at: float | None = None
    _phase_started_at: float | None = None
    _phase_deadline_at: float | None = None


# ---------------------------------------------------------------------------
# GameSession — FSM model + orchestrator
# ---------------------------------------------------------------------------


class GameSession:
    """transitions-driven game runner.

    The `AsyncMachine` sets `self.state` to the current phase id. The
    generic `_on_enter_phase` callback runs the registered handler,
    persists events, updates `game_state`, then triggers the next
    transition. With `queued=True`, that trigger is queued and fires
    when the current callback returns — driving the game forward
    without an external loop.

    The chain stops when:
      * `game_state['ended']` is True (no further trigger fired), or
      * `_step_count` exceeds `max_steps` (safety bound + error event), or
      * a handler raises (error event + ended set).
    """

    def __init__(
        self,
        game_state: GameState,
        services: SessionServices,
        conn: sqlite3.Connection,
        *,
        max_steps: int = 200,
    ) -> None:
        self.game_state = game_state
        self.services = services
        self.conn = conn
        self.max_steps = max_steps
        self._step_count = 0

        self.machine = build_phase_machine(
            game_state["runtime"],
            model=self,
        )
        # The GameState's initial phase usually matches the machine's
        # `initial` (= phase_order[0]); resync silently if not.
        initial = game_state["phase"].value
        if self.state != initial:
            self.state = initial

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------

    async def run(self) -> GameState:
        """Drive the FSM until terminal. Returns the final GameState."""
        # transitions doesn't fire on_enter for the initial state, so
        # kick off manually. Every subsequent transition runs on_enter
        # via the queued trigger chain inside `_on_enter_phase`.
        await self._on_enter_phase()
        return self.game_state

    # ------------------------------------------------------------------
    # Generic state-entry callback
    # ------------------------------------------------------------------

    async def _on_enter_phase(self, *_args: Any, **_kwargs: Any) -> None:
        if self.game_state["ended"]:
            return
        self._step_count += 1
        if self._step_count > self.max_steps:
            await self._abort_max_steps()
            return

        phase = Phase(self.state)
        round_no = self.game_state["round"]
        self.services._phase_started_emitted = False

        # Hold the previous phase's narration on screen long enough to
        # be read before this phase emits its own.
        await _wait_for_min_narration_hold(self.services)
        start_phase_budget(self.services, phase)

        try:
            result = await _dispatch_handler(self, self.game_state, self.services)
        except Exception as exc:
            _log.exception("phase %s failed for game %s", phase.value, self.game_state["game_id"])
            _ensure_phase_started(self.services, self.game_state, self.conn, phase, round_no)
            self.game_state = apply_state_patch(
                self.game_state,
                {"status": GameStatus.FAILED, "ended": True, "winner": None},
            )
            error_event = GameEvent(
                game_id=self.game_state["game_id"], phase=phase,
                scope=EventScope.SYSTEM, target_players=set(),
                event_type=EventType.ERROR_RAISED,
                content=f"event.{EventType.ERROR_RAISED.value}",
                data={"phase": phase.value, "round": round_no, "error": str(exc)},
            )
            self.services.event_seq = _publish_and_persist(
                self.services, self.game_state, [error_event], round_no=round_no,
            )
            return  # terminal — chain stops

        skip = bool(result.get("skip_phase"))

        if not skip:
            # Ensure phase_started + narration fire even if the handler
            # emitted no events of its own.
            _ensure_phase_started(self.services, self.game_state, self.conn, phase, round_no)

            end_event = GameEvent(
                game_id=self.game_state["game_id"], phase=phase,
                scope=EventScope.SYSTEM, target_players=set(),
                event_type=EventType.PHASE_ENDED,
                content=f"event.{EventType.PHASE_ENDED.value}",
                data={"phase": phase.value, "round": round_no},
            )
            events = result.get("events", [])
            persisted_event_count = int(result.get("persisted_event_count", 0))
            persisted_events = events[persisted_event_count:] + [end_event]
            self.services.event_seq = _publish_and_persist(
                self.services, self.game_state, persisted_events, round_no=round_no,
            )

        # Apply state patch + accumulate event histories. Phase changes
        # are deferred to the FSM trigger below.
        self.game_state = _apply_state_only(self.game_state, result)

        if not skip:
            insert_snapshot(
                self.conn, game_id=self.game_state["game_id"],
                seq=self.services.event_seq,
                round_no=round_no, phase=phase.value,
                snapshot_type="phase_end", state_json=snapshot_state(self.game_state),
            )
            _save_player_contexts(self.services, self.game_state)

        override = result.get("next_phase_override")

        if self.game_state["ended"]:
            # Terminal — chain stops. If the handler also requested a
            # phase override (e.g. check_win → game_over on a win),
            # apply it to game_state for reporting, but skip the FSM
            # trigger (game_over is a silent terminal state).
            if override is not None:
                new_index = _phase_index_for(self.game_state, override)
                self.game_state = apply_state_patch(
                    self.game_state, {"phase": override, "phase_index": new_index},
                )
            return

        if self.services.phase_delay_seconds > 0:
            await asyncio.sleep(self.services.phase_delay_seconds)

        # Compute next phase + update GameState BEFORE triggering the
        # transition, so the next on_enter callback sees a coherent
        # (phase, phase_index) when it reads game_state.
        if override is not None:
            new_index = _phase_index_for(self.game_state, override)
            self.game_state = apply_state_patch(
                self.game_state, {"phase": override, "phase_index": new_index},
            )
            trigger = getattr(self, f"to_{override.value}")
            await trigger()
        else:
            order = self.game_state["runtime"]["phase_order"]
            new_index = min(self.game_state["phase_index"] + 1, len(order) - 1)
            new_phase = order[new_index]
            self.game_state = apply_state_patch(
                self.game_state, {"phase": new_phase, "phase_index": new_index},
            )
            await self.advance()

    async def _abort_max_steps(self) -> None:
        self.game_state = apply_state_patch(
            self.game_state,
            {"status": GameStatus.FAILED, "ended": True, "winner": None},
        )
        error_event = GameEvent(
            game_id=self.game_state["game_id"], phase=self.game_state["phase"],
            scope=EventScope.SYSTEM, target_players=set(),
            event_type=EventType.ERROR_RAISED,
            content=f"event.{EventType.ERROR_RAISED.value}",
            data={"max_steps": self.max_steps},
        )
        self.services.event_seq = _publish_and_persist(
            self.services, self.game_state, [error_event],
            round_no=self.game_state["round"],
        )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


async def run_game_session(
    state: GameState,
    *,
    conn: sqlite3.Connection,
    event_bus: EventBus | None = None,
    llm_settings: LLMSettings | None = None,
    llm_callback: Any = None,
    max_steps: int = 200,
    human_awaiter: HumanAwaiter | None = None,
    phase_delay_seconds: float = 0.0,
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
        phase_delay_seconds=max(0.0, phase_delay_seconds),
    )
    insert_game_players(conn, game_id=state["game_id"], state=state)

    session = GameSession(state, services, conn, max_steps=max_steps)
    final_state = await session.run()

    finalize_game(
        conn, state=final_state,
        end_reason="completed" if final_state["status"] == GameStatus.COMPLETED else "failed",
    )
    insert_game_metrics(
        conn, game_id=final_state["game_id"],
        total_events=max(services.event_seq - 1, 0),
        total_llm_calls=services.total_llm_calls,
        total_fallbacks=services.total_fallbacks,
        duration_ms=int((monotonic() - started) * 1000),
        notes={"llm_enabled": services.llm_client is not None},
    )
    return final_state


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _wait_for_min_narration_hold(services: SessionServices) -> None:
    if services._last_narration_at is None:
        return
    elapsed = monotonic() - services._last_narration_at
    remaining = MIN_PHASE_NARRATION_HOLD_SECONDS - elapsed
    if remaining > 0:
        await asyncio.sleep(remaining)


async def _dispatch_handler(
    session: "GameSession", state: GameState, services: SessionServices,
) -> PhaseResult:
    """Resolve and run the handler attached to the current PhaseState."""
    phase_state = session.machine.get_state(session.state)
    handler = getattr(phase_state, "handler", None)
    if handler is None:
        handler = PHASE_HANDLERS.get(state["phase"], _handle_noop)
    result = handler(state, services)
    if inspect.isawaitable(result):
        return await result
    await asyncio.sleep(0)
    return result


def _handle_noop(state: GameState, services: SessionServices) -> PhaseResult:
    return PhaseResult(events=[], state_patch={})


def _ensure_phase_started(
    services: SessionServices, state: GameState, conn: sqlite3.Connection,
    phase: Phase, round_no: int,
) -> None:
    """Emit phase_started + narration when entering a phase.

    Narration is read from the PhaseState (transitions.State subclass)
    stored in PHASE_REGISTRY — the same object the FSM uses, so this
    works regardless of caller (session orchestration or in-handler
    re-entry from llm_bridge / event_helpers).
    """
    if services._phase_started_emitted:
        return
    services._phase_started_emitted = True
    insert_snapshot(
        conn, game_id=state["game_id"], seq=services.event_seq,
        round_no=round_no, phase=phase.value,
        snapshot_type="phase_start", state_json=snapshot_state(state),
    )
    start_event = _phase_event(state, EventType.PHASE_STARTED)
    events_to_send = [start_event]
    from app.engine.registry import get_spec
    phase_state = get_spec(phase.value)
    narration = getattr(phase_state, "narration", None) if phase_state else None
    if narration is not None:
        kind, text_template = narration
        text = text_template.format(round=round_no)
        events_to_send.append(GameEvent(
            game_id=state["game_id"], phase=phase,
            scope=EventScope.SYSTEM, target_players=set(),
            event_type=EventType.NARRATION,
            content=f"event.{EventType.NARRATION.value}",
            data={"text": text, "kind": kind, "style": "intro",
                  "round": round_no, "phase": phase.value},
        ))
        services._last_narration_at = monotonic()
    services.event_seq = _publish_and_persist(services, state, events_to_send, round_no=round_no)


def _publish_and_persist(
    services: SessionServices, state: GameState,
    events: list[GameEvent], *, round_no: int,
) -> int:
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


def _apply_state_only(state: GameState, result: PhaseResult) -> GameState:
    """Apply event-history additions + state_patch from a PhaseResult.

    Phase transitions are driven by the FSM trigger (`advance` or
    `to_<phase>()`) in `_on_enter_phase`, not by this helper.
    """
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
    return apply_state_patch(state, patch)


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
