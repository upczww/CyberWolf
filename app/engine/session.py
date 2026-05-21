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
    phase_delay_seconds: float = 0.0  # debug/demo aid: pause after each phase
    _phase_started_emitted: bool = False
    # Monotonic timestamp of the last phase_started narration. Used to
    # enforce a minimum on-screen lifetime for each phase prompt so it
    # doesn't get instantly replaced by the next phase's narration.
    _last_narration_at: float | None = None


# Every phase narration ("天黑请闭眼", "狼人请睁眼", "进入放逐投票"...)
# must stay visible at least this long before the next phase's narration
# is allowed to replace it. Phases that naturally take longer (LLM,
# human awaiters) pay no cost — the wait only kicks in for transitions
# that would otherwise flash by faster than a human can read.
MIN_PHASE_NARRATION_HOLD_SECONDS = 5.0


async def _wait_for_min_narration_hold(services: SessionServices) -> None:
    if services._last_narration_at is None:
        return
    elapsed = monotonic() - services._last_narration_at
    remaining = MIN_PHASE_NARRATION_HOLD_SECONDS - elapsed
    if remaining > 0:
        await asyncio.sleep(remaining)


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

    steps = 0
    while not state["ended"] and steps < max_steps:
        steps += 1
        current_phase = state["phase"]
        current_round = state["round"]

        # Mark that phase_started hasn't been emitted yet for this phase
        services._phase_started_emitted = False

        # Hold the previous phase's narration on screen long enough to be
        # read before this phase emits its own. Phases that already took
        # >= MIN_PHASE_NARRATION_HOLD_SECONDS pay nothing.
        await _wait_for_min_narration_hold(services)

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

        # Backup: ensure phase_started fires even if the handler emitted
        # no events (so the narration banner always shows).
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

        if services.phase_delay_seconds > 0:
            await asyncio.sleep(services.phase_delay_seconds)

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


_PHASE_NARRATION: dict[str, tuple[str, str]] = {
    # phase.value -> (kind, text). {round} placeholder gets replaced.
    "setup_game":       ("info", "对局准备中…"),
    "night_start":      ("info", "第 {round} 夜 · 天黑请闭眼"),
    "night_wolf":       ("wolf", "狼人请睁眼，选择今夜的目标"),
    "night_seer":       ("good", "预言家请睁眼，选择一名玩家查验"),
    "night_witch":      ("good", "女巫请睁眼，是否使用解药与毒药"),
    "night_guard":      ("good", "守卫请守护一名玩家"),
    "night_hunter":     ("good", "猎人请睁眼，是否发动技能"),
    "night_resolve":    ("info", "天将亮起 · 裁判结算夜晚行动"),
    "sheriff_election": ("gold", "第 {round} 天 · 警长竞选阶段开始"),
    "day_speech":       ("info", "第 {round} 天 · 进入发言阶段"),
    "day_vote":         ("info", "进入放逐投票，请投出你的一票"),
    "day_resolve":      ("info", "裁判结算投票"),
    "pending_skills":   ("info", "出局玩家依次结算死亡技能"),
    # check_win is a fast pass-through — no narration; game_over has its own
    # GAME_ENDED event which the frontend already renders as victory banner.
}


def _ensure_phase_started(services: SessionServices, state: GameState, conn: sqlite3.Connection, phase: Phase, round_no: int) -> None:
    """Emit phase_started (and a player-facing narration) when entering a phase."""
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
    narration = _PHASE_NARRATION.get(phase.value)
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
