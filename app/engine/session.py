from __future__ import annotations

import asyncio
import inspect
import json
import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

TZ_CN = timezone(timedelta(hours=8))
from random import Random
from time import monotonic
from typing import Any, TypeGuard

from app.config import AppPaths, LLMSettings, get_paths
from app.domain.events import GameEvent
from app.domain.roles import EventScope, EventType, Faction, GameStatus, Phase, Role
from app.domain.state import (
    GameState,
    PhaseResult,
    PendingSkill,
    alive_player_ids,
    apply_state_patch,
    living_wolves,
    next_phase,
    snapshot_state,
)
from app.engine.rules import check_win
from app.infra.events import EventBus
from app.infra.repositories.events import insert_events
from app.infra.repositories.games import finalize_game, insert_game_players
from app.infra.repositories.llm_calls import insert_llm_call
from app.infra.repositories.metrics import insert_game_metrics
from app.infra.repositories.snapshots import insert_snapshot
from app.services.context_builder import build_prompt_context
from app.services.decisions import resolve_action, validate_tool_call
from app.services.llm import LLMCallResult, LLMClient, TOOL_REGISTRY, build_phase_messages, enabled_tools
from app.services.prompts import build_prompt_inputs, load_prompt_template, render_prompt_template, resolve_prompt_template, split_rendered_template

_COMMON_RULES = """你是一名狼人杀游戏玩家，正在进行一局12人标准局（预女猎白+警长）。你必须严格遵循游戏规则，根据你的身份、已知信息以及场上形势，做出合理决策和发言。

核心行为准则：
· 你的唯一目标是帮助己方阵营获胜。无论是发言、投票还是使用技能，都应为胜利服务。
· 你只能根据游戏规则允许你获知的信息（如夜晚睁眼看到的信息、主持人通报的死亡信息、放逐结果等）来行动，不能使用上帝视角。
· 发言要符合逻辑，尽量模仿真实玩家的风格，可适当带情绪，但不得辱骂或人身攻击。
· 投票必须给出清晰的对象，不能模糊。
· 如果你已出局，请遵守遗言规则，之后不能再参与发言和投票（白痴翻牌后发言除外）。"""


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
    llm_callback: Any = None  # Optional callable(phase, player_id, tool_name, tool_args, content)


async def run_game_session(
    state: GameState,
    *,
    conn: sqlite3.Connection,
    event_bus: EventBus | None = None,
    llm_settings: LLMSettings | None = None,
    llm_callback: Any = None,
    max_steps: int = 200,
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
    )
    insert_game_players(conn, game_id=state["game_id"], state=state)

    steps = 0
    while not state["ended"] and steps < max_steps:
        steps += 1
        current_phase = state["phase"]
        current_round = state["round"]
        insert_snapshot(
            conn,
            game_id=state["game_id"],
            seq=services.event_seq,
            round_no=current_round,
            phase=current_phase.value,
            snapshot_type="phase_start",
            state_json=snapshot_state(state),
        )
        start_event = _phase_event(state, EventType.PHASE_STARTED)
        services.event_seq = _publish_and_persist(services, state, [start_event], round_no=current_round)

        try:
            result = await handle_phase(state, services)
        except Exception as exc:
            logging.getLogger(__name__).exception("phase %s failed for game %s", current_phase.value, state["game_id"])
            state = apply_state_patch(
                state,
                {
                    "status": GameStatus.FAILED,
                    "ended": True,
                    "winner": None,
                },
            )
            error_event = GameEvent(
                game_id=state["game_id"],
                phase=current_phase,
                scope=EventScope.SYSTEM,
                target_players=set(),
                event_type=EventType.ERROR_RAISED,
                content=_event_content_key(EventType.ERROR_RAISED),
                data={"phase": current_phase.value, "round": current_round, "error": str(exc)},
            )
            services.event_seq = _publish_and_persist(services, state, [error_event], round_no=current_round)
            break

        # If handler signals skip, suppress phase_started/phase_ended and snapshots
        if result.get("skip_phase"):
            # Delete the already-persisted phase_started event
            conn.execute("DELETE FROM game_events WHERE game_id = ? AND seq = ?", (state["game_id"], services.event_seq - 1))
            conn.execute("DELETE FROM state_snapshots WHERE game_id = ? AND seq = ?", (state["game_id"], services.event_seq - 1))
            services.event_seq -= 1
            state = _apply_phase_result(state, result)
            continue
        end_event = GameEvent(
            game_id=state["game_id"],
            phase=current_phase,
            scope=EventScope.SYSTEM,
            target_players=set(),
            event_type=EventType.PHASE_ENDED,
            content=_event_content_key(EventType.PHASE_ENDED),
            data={"phase": current_phase.value, "round": current_round},
        )
        events = result.get("events", [])
        persisted_event_count = int(result.get("persisted_event_count", 0))
        persisted_events = events[persisted_event_count:] + [end_event]
        services.event_seq = _publish_and_persist(services, state, persisted_events, round_no=current_round)
        state = _apply_phase_result(state, result)
        insert_snapshot(
            conn,
            game_id=state["game_id"],
            seq=services.event_seq,
            round_no=current_round,
            phase=current_phase.value,
            snapshot_type="phase_end",
            state_json=snapshot_state(state),
        )

        _save_player_contexts(services, state)

        if state["ended"]:
            break

    if not state["ended"]:
        state = apply_state_patch(
            state,
            {
                "status": GameStatus.FAILED,
                "ended": True,
                "winner": None,
            },
        )
        error_event = GameEvent(
            game_id=state["game_id"],
            phase=state["phase"],
            scope=EventScope.SYSTEM,
            target_players=set(),
            event_type=EventType.ERROR_RAISED,
            content=_event_content_key(EventType.ERROR_RAISED),
            data={"max_steps": max_steps},
        )
        services.event_seq = _publish_and_persist(services, state, [error_event], round_no=state["round"])

    finalize_game(conn, state=state, end_reason="completed" if state["status"] == GameStatus.COMPLETED else "failed")
    insert_game_metrics(
        conn,
        game_id=state["game_id"],
        total_events=max(services.event_seq - 1, 0),
        total_llm_calls=services.total_llm_calls,
        total_fallbacks=services.total_fallbacks,
        duration_ms=int((monotonic() - started) * 1000),
        notes={"llm_enabled": services.llm_client is not None},
    )
    return state


async def handle_phase(state: GameState, services: SessionServices) -> PhaseResult:
    handler = _PHASE_HANDLERS.get(state["phase"], _handle_noop)
    result = handler(state, services)
    if inspect.isawaitable(result):
        return await result
    await asyncio.sleep(0)
    return result


def _event_content_key(event_type: EventType) -> str:
    return f"event.{event_type.value}"


def _phase_event(state: GameState, event_type: EventType) -> GameEvent:
    return GameEvent(
        game_id=state["game_id"],
        phase=state["phase"],
        scope=EventScope.SYSTEM,
        target_players=set(),
        event_type=event_type,
        content=_event_content_key(event_type),
        data={"phase": state["phase"].value, "round": state["round"]},
    )


def _publish_and_persist(services: SessionServices, state: GameState, events: list[GameEvent], *, round_no: int) -> int:
    next_seq = insert_events(
        services.conn,
        game_id=state["game_id"],
        round_no=round_no,
        start_seq=services.event_seq,
        events=events,
    )
    for event in events:
        services.event_bus.publish(event)
    return next_seq


def _append_live_event(
    services: SessionServices,
    state: GameState,
    events: list[GameEvent],
    event: GameEvent,
    *,
    round_no: int,
) -> None:
    events.append(event)
    services.event_seq = _publish_and_persist(services, state, [event], round_no=round_no)


def _append_speaking_started(
    services: SessionServices,
    state: GameState,
    events: list[GameEvent],
    *,
    player_id: int,
) -> None:
    _append_live_event(
        services,
        state,
        events,
        GameEvent(
            game_id=state["game_id"],
            phase=state["phase"],
            scope=EventScope.PUBLIC,
            target_players=set(),
            event_type=EventType.SPEAKING_STARTED,
            content=_event_content_key(EventType.SPEAKING_STARTED),
            data={"player_id": player_id},
        ),
        round_no=state["round"],
    )


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


def _handle_noop(state: GameState, services: SessionServices) -> PhaseResult:
    return PhaseResult(events=[], state_patch={})


def _handle_setup_game(state: GameState, services: SessionServices) -> PhaseResult:
    return PhaseResult(
        events=[
            GameEvent(
                game_id=state["game_id"],
                phase=state["phase"],
                scope=EventScope.GOD,
                target_players=set(),
                event_type=EventType.PHASE_STARTED,
                content="event.game_setup_completed",
                data={"players": len(state["players"])},
            )
        ]
    )


def _handle_night_start(state: GameState, services: SessionServices) -> PhaseResult:
    return PhaseResult(state_patch={"night_actions": {}, "night_result": {}, "vote_records": {}, "vote_candidates": []}, events=[])


async def _handle_night_wolf(state: GameState, services: SessionServices) -> PhaseResult:
    wolves = living_wolves(state)
    targets = [pid for pid in alive_player_ids(state) if pid not in wolves]
    if not wolves or not targets:
        return PhaseResult(state_patch={"night_actions": {"wolf_votes": {}, "wolf_target": None}}, events=[])

    # Use ONE LLM call for the lead wolf to decide the target (wolves act together at night)
    lead_wolf = wolves[0]
    proposed_target = await _llm_tool_or_local(
        state,
        services,
        actor_id=lead_wolf,
        role=Role.WOLF,
        phase=state["phase"],
        tool_name="wolf_kill_proposal",
        local_args={"target_id": services.rng.choice(targets)},
    )
    proposed = {
        "actor_id": lead_wolf,
        "phase": state["phase"],
        "tool_name": "wolf_kill_proposal",
        "raw_args": proposed_target,
        "source": _action_source(services, state["phase"]),
    }
    validated = validate_tool_call(
        state=state,
        runtime=state["runtime"],
        actor_id=lead_wolf,
        role=Role.WOLF,
        phase=state["phase"],
        proposed=proposed,
    )
    if not validated["is_valid"]:
        logging.getLogger(__name__).warning(
            "invalid wolf_kill_proposal for player %s: %s – using random target",
            lead_wolf, validated.get("validation_errors", []),
        )
        selected = services.rng.choice(targets)
        return PhaseResult(
            state_patch={"night_actions": {"wolf_votes": {lead_wolf: selected}, "wolf_target": selected}},
            events=[
                GameEvent(
                    game_id=state["game_id"],
                    phase=state["phase"],
                    scope=EventScope.WOLF_TEAM,
                    target_players=set(wolves),
                    event_type=EventType.WOLF_TARGET_SELECTED,
                    content=_event_content_key(EventType.WOLF_TARGET_SELECTED),
                    data={"votes": {lead_wolf: selected}, "target_id": selected},
                )
            ],
        )
    action = resolve_action(validated)
    selected = action["args"]["target_id"]
    # All wolves "vote" the same (they decided together)
    votes = {wolf_id: selected for wolf_id in wolves}
    return PhaseResult(
        state_patch={"night_actions": {"wolf_votes": votes, "wolf_target": selected}},
        actions=[action],
        events=[
            GameEvent(
                game_id=state["game_id"],
                phase=state["phase"],
                scope=EventScope.WOLF_TEAM,
                target_players=set(wolves),
                event_type=EventType.WOLF_TARGET_SELECTED,
                content=_event_content_key(EventType.WOLF_TARGET_SELECTED),
                data={"votes": votes, "target_id": selected},
            )
        ],
    )


async def _handle_night_seer(state: GameState, services: SessionServices) -> PhaseResult:
    seer_id = _find_alive_role(state, Role.SEER)
    if seer_id is None:
        return PhaseResult(events=[])
    checked = {entry["target_id"] for entry in state["seer_checks"]}
    candidates = [pid for pid in alive_player_ids(state) if pid != seer_id and pid not in checked]
    if not candidates:
        candidates = [pid for pid in alive_player_ids(state) if pid != seer_id]
    proposed_args = await _llm_tool_or_local(
        state,
        services,
        actor_id=seer_id,
        role=Role.SEER,
        phase=state["phase"],
        tool_name="seer_check",
        local_args={"target_id": services.rng.choice(candidates)},
    )
    proposed = {
        "actor_id": seer_id,
        "phase": state["phase"],
        "tool_name": "seer_check",
        "raw_args": proposed_args,
        "source": _action_source(services, state["phase"]),
    }
    validated = validate_tool_call(
        state=state,
        runtime=state["runtime"],
        actor_id=seer_id,
        role=Role.SEER,
        phase=state["phase"],
        proposed=proposed,
    )
    if not validated["is_valid"]:
        logging.getLogger(__name__).warning(
            "invalid seer_check for player %s: %s – skipping",
            seer_id, validated.get("validation_errors", []),
        )
        return PhaseResult(events=[])
    action = resolve_action(validated)
    target = action["args"]["target_id"]
    result = "wolf" if state["players"][target]["role"] == Role.WOLF else "good"
    checks = list(state["seer_checks"]) + [{"target_id": target, "result": result, "round": state["round"]}]
    return PhaseResult(
        state_patch={"seer_checks": checks},
        actions=[action],
        events=[
            GameEvent(
                game_id=state["game_id"],
                phase=state["phase"],
                scope=EventScope.ROLE_PRIVATE,
                target_players={seer_id},
                event_type=EventType.SEER_CHECKED,
                content=_event_content_key(EventType.SEER_CHECKED),
                data={"target_id": target, "result": result},
            )
        ],
    )


async def _handle_night_witch(state: GameState, services: SessionServices) -> PhaseResult:
    witch_id = _find_alive_role(state, Role.WITCH)
    wolf_target = state["night_actions"].get("wolf_target")
    if witch_id is None:
        return PhaseResult(events=[])
    if wolf_target is None:
        # No one died — witch only gets poison option
        wolf_target = None

    actions = []
    witch_events: list[GameEvent] = []
    night_actions_patch = {**state["night_actions"]}

    # --- Decision 1: Antidote (only if antidote available and someone was killed) ---
    use_antidote = False
    if not state["witch_antidote_used"] and wolf_target is not None:
        can_save_self = bool(state["runtime"]["rule_flags"].get("witch_can_self_save_first_night", False))
        # Local fallback: decide based on probability
        local_use = wolf_target != witch_id or can_save_self
        local_args = {"use_antidote": local_use and services.rng.random() < 0.35}

        llm_args = await _llm_tool_or_local(
            state,
            services,
            actor_id=witch_id,
            role=Role.WITCH,
            phase=state["phase"],
            tool_name="witch_antidote",
            local_args=local_args,
        )
        proposed = {
            "actor_id": witch_id,
            "phase": state["phase"],
            "tool_name": "witch_antidote",
            "raw_args": llm_args,
            "source": _action_source(services, state["phase"]),
        }
        validated = validate_tool_call(
            state=state,
            runtime=state["runtime"],
            actor_id=witch_id,
            role=Role.WITCH,
            phase=state["phase"],
            proposed=proposed,
        )
        if not validated["is_valid"]:
            logging.getLogger(__name__).warning(
                "invalid witch_antidote for player %s: %s – fallback to no antidote",
                witch_id, validated.get("validation_errors", []),
            )
            validated["args"] = {"use_antidote": False}
        action = resolve_action(validated)
        actions.append(action)
        use_antidote = bool(action["args"].get("use_antidote", False))

        if use_antidote:
            witch_events.append(
                GameEvent(
                    game_id=state["game_id"],
                    phase=state["phase"],
                    scope=EventScope.ROLE_PRIVATE,
                    target_players={witch_id},
                    event_type=EventType.WITCH_USED_ANTIDOTE,
                    content=_event_content_key(EventType.WITCH_USED_ANTIDOTE),
                    data={"target_id": wolf_target, "player_id": witch_id},
                )
            )

    night_actions_patch["witch_use_antidote"] = use_antidote

    # --- Decision 2: Poison (only if poison available AND not using antidote tonight) ---
    poison_target = None
    if not state["witch_poison_used"] and not use_antidote:
        candidates = [pid for pid in alive_player_ids(state) if pid != witch_id]
        local_poison_target = services.rng.choice(candidates) if candidates and services.rng.random() < 0.15 else None

        llm_args = await _llm_tool_or_local(
            state,
            services,
            actor_id=witch_id,
            role=Role.WITCH,
            phase=state["phase"],
            tool_name="witch_poison",
            local_args={"target_id": local_poison_target},
            prompt_key_override="witch_poison.j2",
        )
        proposed = {
            "actor_id": witch_id,
            "phase": state["phase"],
            "tool_name": "witch_poison",
            "raw_args": llm_args,
            "source": _action_source(services, state["phase"]),
        }
        validated = validate_tool_call(
            state=state,
            runtime=state["runtime"],
            actor_id=witch_id,
            role=Role.WITCH,
            phase=state["phase"],
            proposed=proposed,
        )
        if not validated["is_valid"]:
            logging.getLogger(__name__).warning(
                "invalid witch_poison for player %s: %s – fallback to no poison",
                witch_id, validated.get("validation_errors", []),
            )
            validated["args"] = {"target_id": None}
        action = resolve_action(validated)
        actions.append(action)
        poison_target = action["args"].get("target_id")

        if poison_target is not None:
            witch_events.append(
                GameEvent(
                    game_id=state["game_id"],
                    phase=state["phase"],
                    scope=EventScope.ROLE_PRIVATE,
                    target_players={witch_id},
                    event_type=EventType.WITCH_USED_POISON,
                    content=_event_content_key(EventType.WITCH_USED_POISON),
                    data={"target_id": poison_target, "player_id": witch_id},
                )
            )

    night_actions_patch["witch_poison_target"] = poison_target

    patch = {
        "night_actions": night_actions_patch,
        "witch_antidote_used": state["witch_antidote_used"] or use_antidote,
        "witch_poison_used": state["witch_poison_used"] or (poison_target is not None),
    }
    return PhaseResult(state_patch=patch, actions=actions, events=witch_events)


async def _handle_night_resolve(state: GameState, services: SessionServices) -> PhaseResult:
    wolf_target = state["night_actions"].get("wolf_target")
    use_antidote = bool(state["night_actions"].get("witch_use_antidote"))
    poison_target = state["night_actions"].get("witch_poison_target")

    deaths: list[tuple[int, str]] = []
    if wolf_target is not None and not use_antidote:
        deaths.append((wolf_target, "wolf"))
    if poison_target is not None:
        deaths.append((poison_target, "poison"))

    patch = {"night_result": {"deaths": [player_id for player_id, _ in deaths]}}
    events: list[GameEvent] = []
    pending: list[PendingSkill] = list(state["pending_skills"])
    players_patch: dict[int, dict] = {}
    dead_history = list(state["dead_history"])

    for player_id, cause in deaths:
        if not state["players"][player_id]["alive"] or player_id in players_patch:
            continue
        players_patch[player_id] = {
            "alive": False,
            "death_round": state["round"],
            "death_cause": cause,
            "is_sheriff": False,
        }
        dead_history.append({"player_id": player_id, "cause": cause, "round": state["round"]})
        _append_live_event(
            services,
            state,
            events,
            GameEvent(
                game_id=state["game_id"],
                phase=state["phase"],
                scope=EventScope.PUBLIC,
                target_players=set(),
                event_type=EventType.PLAYER_DIED,
                content=_event_content_key(EventType.PLAYER_DIED),
                data={"player_id": player_id, "cause": cause},
            ),
            round_no=state["round"],
        )
        _queue_death_skills(state, pending, player_id, cause)

    patch["players"] = players_patch
    if any(state["players"][player_id]["is_sheriff"] for player_id, _ in deaths):
        patch["sheriff_id"] = None
    patch["dead_history"] = dead_history
    patch["pending_skills"] = pending

    # Collect death speeches (遗言) for first-night deaths
    dead_ids = [player_id for player_id, _ in deaths]
    death_causes = {player_id: cause for player_id, cause in deaths}
    speech_events = await _collect_death_speeches(state, services, dead_ids, death_causes=death_causes)
    events.extend(speech_events)

    return PhaseResult(state_patch=patch, events=events, persisted_event_count=len(events))


def _handle_day_announce(state: GameState, services: SessionServices) -> PhaseResult:
    deaths = state["night_result"].get("deaths", [])
    return PhaseResult(
        events=[
            GameEvent(
                game_id=state["game_id"],
                phase=state["phase"],
                scope=EventScope.PUBLIC,
                target_players=set(),
                event_type=EventType.PHASE_STARTED,
                content="event.day_announce",
                data={"deaths": deaths},
            )
        ]
    )


async def _handle_sheriff_election(state: GameState, services: SessionServices) -> PhaseResult:
    if state["round"] > 1 or state["sheriff_id"] is not None or not state["runtime"]["rule_flags"].get("sheriff_enabled", True):
        return PhaseResult(events=[], skip_phase=True)

    alive = alive_player_ids(state)
    events: list[GameEvent] = []
    actions = []

    # Phase 1: Declare candidacy — each player decides whether to run
    # Wolves: pre-select exactly one to run for sheriff (standard strategy)
    living_wolves_list = [pid for pid in alive if state["players"][pid]["faction"] == Faction.WOLF]
    designated_wolf = services.rng.choice(living_wolves_list) if living_wolves_list else None

    candidates: list[int] = []
    for player_id in alive:
        # Wolves: only the designated wolf runs, others skip
        if state["players"][player_id]["faction"] == Faction.WOLF:
            if player_id == designated_wolf:
                wants_to_run = True
            else:
                wants_to_run = False
        else:
            wants_to_run = await _decide_candidacy(state, services, player_id)
        if wants_to_run:
            candidates.append(player_id)
            _append_live_event(
                services,
                state,
                events,
                GameEvent(
                    game_id=state["game_id"],
                    phase=state["phase"],
                    scope=EventScope.PUBLIC,
                    target_players=set(),
                    event_type=EventType.SHERIFF_DECLARE,
                    content=_event_content_key(EventType.SHERIFF_DECLARE),
                    data={"player_id": player_id},
                ),
                round_no=state["round"],
            )

    if not candidates:
        # No one wants to run — no sheriff
        _append_live_event(
            services,
            state,
            events,
            GameEvent(
                game_id=state["game_id"],
                phase=state["phase"],
                scope=EventScope.PUBLIC,
                target_players=set(),
                event_type=EventType.SHERIFF_ELECTED,
                content=_event_content_key(EventType.SHERIFF_ELECTED),
                data={"player_id": None, "votes": {}, "reason": "no candidates"},
            ),
            round_no=state["round"],
        )
        return PhaseResult(actions=actions, events=events, persisted_event_count=len(events))

    if len(candidates) == 1:
        # Only one candidate — becomes sheriff automatically
        sheriff_id = candidates[0]
        players_patch = {sheriff_id: {"is_sheriff": True}}
        _append_live_event(
            services,
            state,
            events,
            GameEvent(
                game_id=state["game_id"],
                phase=state["phase"],
                scope=EventScope.PUBLIC,
                target_players=set(),
                event_type=EventType.SHERIFF_ELECTED,
                content=_event_content_key(EventType.SHERIFF_ELECTED),
                data={"player_id": sheriff_id, "votes": {}, "unopposed": True},
            ),
            round_no=state["round"],
        )
        # Sheriff picks speech direction
        direction = await _sheriff_pick_direction(state, services, sheriff_id)
        _append_live_event(
            services,
            state,
            events,
            GameEvent(
                game_id=state["game_id"],
                phase=state["phase"],
                scope=EventScope.PUBLIC,
                target_players=set(),
                event_type=EventType.SHERIFF_DIRECTION,
                content=_event_content_key(EventType.SHERIFF_DIRECTION),
                data={"player_id": sheriff_id, "clockwise": direction},
            ),
            round_no=state["round"],
        )
        return PhaseResult(
            state_patch={"sheriff_id": sheriff_id, "players": players_patch, "sheriff_speech_clockwise": direction},
            actions=actions,
            events=events,
            persisted_event_count=len(events),
        )

    # Phase 2: Campaign speeches — candidates speak in random order
    speech_order = list(candidates)
    services.rng.shuffle(speech_order)
    for player_id in speech_order:
        role = state["players"][player_id]["role"]
        _append_speaking_started(services, state, events, player_id=player_id)
        proposed_args = await _llm_speech_or_local(
            state,
            services,
            actor_id=player_id,
            role=role,
            phase=state["phase"],
            local_args={
                "public_speech": f"玩家{player_id}竞选警长",
                "internal_thought": "",
            },
        )
        speech = proposed_args.get("public_speech", "")
        if speech:
            _append_live_event(
                services,
                state,
                events,
                GameEvent(
                    game_id=state["game_id"],
                    phase=state["phase"],
                    scope=EventScope.PUBLIC,
                    target_players=set(),
                    event_type=EventType.SHERIFF_CAMPAIGN,
                    content=_event_content_key(EventType.SHERIFF_CAMPAIGN),
                    data={"player_id": player_id, "speech": speech},
                ),
                round_no=state["round"],
            )

    # Phase 3: Vote — only NON-candidates vote for candidates
    voters = [pid for pid in alive if pid not in candidates]
    votes: dict[int, int] = {}
    for voter in voters:
        voter_candidates = list(candidates)
        if not voter_candidates:
            votes[voter] = None
            continue
        proposed_args = await _llm_tool_or_local(
            state,
            services,
            actor_id=voter,
            role=state["players"][voter]["role"],
            phase=state["phase"],
            tool_name="vote_target",
            local_args={"target_id": services.rng.choice(voter_candidates)},
            prompt_key_override="sheriff_vote.j2",
            decision_note=(
                "现在是警长竞选投票，不是竞选发言。"
                f"你必须从候选人 {voter_candidates} 中选择一人，把 target_id 设置为候选人的编号。"
                "不要输出普通文本，不要发表演讲。"
            ),
        )
        # Check if wolf chose to self-destruct during election vote
        if proposed_args.get("_wolf_self_destruct"):
            result = _build_self_destruct_result(state, voter)
            merged = dict(result)
            merged["events"] = events + result.get("events", [])
            merged["actions"] = actions + result.get("actions", [])
            merged["persisted_event_count"] = len(events)
            return PhaseResult(**merged)
        action = _validate_or_raise(
            state,
            services,
            actor_id=voter,
            role=state["players"][voter]["role"],
            phase=state["phase"],
            tool_name="vote_target",
            args=proposed_args,
        )
        actions.append(action)
        target = action["args"].get("target_id")
        # Ensure vote is for a candidate
        if target not in candidates:
            target = services.rng.choice(candidates) if candidates else None
        votes[voter] = target

    # Phase 4: Tally — with tie-breaking (extra speech + re-vote)
    sheriff_id, votes = await _resolve_sheriff_election(
        state, services, votes, candidates, voters, events, actions,
    )
    # Self-destruct happened during tie-breaking
    if _is_phase_result(votes):
        return votes
    if sheriff_id is None:
        _append_live_event(
            services,
            state,
            events,
            GameEvent(
                game_id=state["game_id"],
                phase=state["phase"],
                scope=EventScope.PUBLIC,
                target_players=set(),
                event_type=EventType.SHERIFF_ELECTED,
                content=_event_content_key(EventType.SHERIFF_ELECTED),
                data={"player_id": None, "votes": votes, "tie": True},
            ),
            round_no=state["round"],
        )
        return PhaseResult(actions=actions, events=events, persisted_event_count=len(events))

    players_patch = {sheriff_id: {"is_sheriff": True}}
    _append_live_event(
        services,
        state,
        events,
        GameEvent(
            game_id=state["game_id"],
            phase=state["phase"],
            scope=EventScope.PUBLIC,
            target_players=set(),
            event_type=EventType.SHERIFF_ELECTED,
            content=_event_content_key(EventType.SHERIFF_ELECTED),
            data={"player_id": sheriff_id, "votes": votes},
        ),
        round_no=state["round"],
    )

    # Sheriff picks speech direction
    direction = await _sheriff_pick_direction(state, services, sheriff_id)
    _append_live_event(
        services,
        state,
        events,
        GameEvent(
            game_id=state["game_id"],
            phase=state["phase"],
            scope=EventScope.PUBLIC,
            target_players=set(),
            event_type=EventType.SHERIFF_DIRECTION,
            content=_event_content_key(EventType.SHERIFF_DIRECTION),
            data={"player_id": sheriff_id, "clockwise": direction},
        ),
        round_no=state["round"],
    )

    return PhaseResult(
        state_patch={"sheriff_id": sheriff_id, "players": players_patch, "sheriff_speech_clockwise": direction},
        actions=actions,
        events=events,
        persisted_event_count=len(events),
    )


async def _handle_day_speech(state: GameState, services: SessionServices) -> PhaseResult:
    speeches = list(state["speech_log"])
    events: list[GameEvent] = []
    order = _determine_speech_order(state)
    actions = []

    # Announce speech order (live-persist so TUI shows it immediately)
    _append_live_event(
        services,
        state,
        events,
        GameEvent(
            game_id=state["game_id"],
            phase=state["phase"],
            scope=EventScope.PUBLIC,
            target_players=set(),
            event_type=EventType.SPEECH_ORDER_ANNOUNCED,
            content=_event_content_key(EventType.SPEECH_ORDER_ANNOUNCED),
            data={"order": order, "sheriff_id": state.get("sheriff_id")},
        ),
        round_no=state["round"],
    )
    for player_id in order:
        role = state["players"][player_id]["role"].value
        _append_speaking_started(services, state, events, player_id=player_id)
        proposed_args = await _llm_speech_or_local(
            state,
            services,
            actor_id=player_id,
            role=state["players"][player_id]["role"],
            phase=state["phase"],
            local_args={
                "public_speech": f"player {player_id} ({role}) gives a short public speech",
                "internal_thought": "",
            },
        )
        # Check if wolf chose to self-destruct during speech
        if proposed_args.get("_wolf_self_destruct"):
            return _build_self_destruct_result(state, player_id)

        proposed = {
            "actor_id": player_id,
            "phase": state["phase"],
            "tool_name": "public_speech",
            "raw_args": proposed_args,
            "source": _action_source(services, state["phase"]),
        }
        validated = validate_tool_call(
            state=state,
            runtime=state["runtime"],
            actor_id=player_id,
            role=state["players"][player_id]["role"],
            phase=state["phase"],
            proposed=proposed,
        )
        if not validated["is_valid"]:
            logging.getLogger(__name__).warning(
                "invalid public_speech for player %s in %s: %s – using fallback",
                player_id, state["phase"].value, validated.get("validation_errors", []),
            )
            proposed["raw_args"] = {
                "public_speech": f"player {player_id} ({role}) gives a short public speech",
                "internal_thought": "",
            }
            validated = validate_tool_call(
                state=state,
                runtime=state["runtime"],
                actor_id=player_id,
                role=state["players"][player_id]["role"],
                phase=state["phase"],
                proposed=proposed,
            )
        action = resolve_action(validated)
        actions.append(action)
        content = action["args"]["public_speech"]
        speeches.append({"player_id": player_id, "round": state["round"], "content": content})
        if action["args"].get("internal_thought"):
            player_memory = list(state["players"][player_id]["private_memory"])
            player_memory.append(
                {"round": state["round"], "phase": state["phase"].value, "internal_thought": action["args"]["internal_thought"]}
            )
        else:
            player_memory = list(state["players"][player_id]["private_memory"])
        # Live-persist speech so TUI shows it immediately after each player
        _append_live_event(
            services,
            state,
            events,
            GameEvent(
                game_id=state["game_id"],
                phase=state["phase"],
                scope=EventScope.PUBLIC,
                target_players=set(),
                event_type=EventType.PUBLIC_SPEECH_MADE,
                content=_event_content_key(EventType.PUBLIC_SPEECH_MADE),
                data={"player_id": player_id, "speech": content},
            ),
            round_no=state["round"],
        )
    players_patch = {
        player_id: {"private_memory": list(state["players"][player_id]["private_memory"])}
        for player_id in order
    }
    for action in actions:
        thought = action["args"].get("internal_thought")
        if thought:
            actor_memory = list(players_patch[action["actor_id"]]["private_memory"])
            actor_memory.append({"round": state["round"], "phase": state["phase"].value, "internal_thought": thought})
            players_patch[action["actor_id"]]["private_memory"] = actor_memory
    return PhaseResult(
        state_patch={"speech_order": order, "speech_log": speeches, "players": players_patch},
        actions=actions,
        events=events,
        persisted_event_count=len(events),
    )


async def _handle_day_vote(state: GameState, services: SessionServices) -> PhaseResult:
    voters = [pid for pid, player in state["players"].items() if player["alive"] and player["can_vote"]]
    votes: dict[int, int | None] = {}
    actions = []
    for voter in voters:
        candidates = [pid for pid in alive_player_ids(state) if pid != voter]
        if not candidates:
            votes[voter] = None
            continue
        proposed_args = await _llm_tool_or_local(
            state,
            services,
            actor_id=voter,
            role=state["players"][voter]["role"],
            phase=state["phase"],
            tool_name="vote_target",
            local_args={"target_id": services.rng.choice(candidates)},
        )
        # Check if wolf chose to self-destruct during vote
        if proposed_args.get("_wolf_self_destruct"):
            return _build_self_destruct_result(state, voter)
        proposed = {
            "actor_id": voter,
            "phase": state["phase"],
            "tool_name": "vote_target",
            "raw_args": proposed_args,
            "source": _action_source(services, state["phase"]),
        }
        validated = validate_tool_call(
            state=state,
            runtime=state["runtime"],
            actor_id=voter,
            role=state["players"][voter]["role"],
            phase=state["phase"],
            proposed=proposed,
        )
        if not validated["is_valid"]:
            logging.getLogger(__name__).warning(
                "invalid vote_target for player %s: %s – abstaining",
                voter, validated.get("validation_errors", []),
            )
            votes[voter] = None
            continue
        action = resolve_action(validated)
        actions.append(action)
        votes[voter] = action["args"]["target_id"]
    tally: dict[int, float] = {}
    sheriff_id = state.get("sheriff_id")
    for voter_id, target in votes.items():
        if target is None:
            continue
        weight = 1.5 if voter_id == sheriff_id else 1.0
        tally[target] = tally.get(target, 0) + weight
    chosen = None
    if tally:
        top = max(tally.values())
        tied = sorted([pid for pid, score in tally.items() if score == top])
        if len(tied) == 1:
            chosen = tied[0]
        elif sheriff_id is not None and votes.get(sheriff_id) in tied:
            # Sheriff voted for one of the tied -> sheriff's pick wins
            chosen = votes[sheriff_id]
        else:
            chosen = services.rng.choice(tied)
    return PhaseResult(
        state_patch={"vote_records": votes, "vote_candidates": [chosen] if chosen is not None else []},
        actions=actions,
        events=[
            GameEvent(
                game_id=state["game_id"],
                phase=state["phase"],
                scope=EventScope.PUBLIC,
                target_players=set(),
                event_type=EventType.VOTE_RESOLVED,
                content=_event_content_key(EventType.VOTE_RESOLVED),
                data={"votes": votes, "chosen": chosen},
            )
        ],
    )


async def _handle_day_resolve(state: GameState, services: SessionServices) -> PhaseResult:
    if not state["vote_candidates"]:
        return PhaseResult(state_patch={"round": state["round"] + 1, "day_index": state["day_index"] + 1}, events=[])
    target = state["vote_candidates"][0]
    player = state["players"][target]
    events: list[GameEvent] = []
    players_patch: dict[int, dict] = {}
    dead_history = list(state["dead_history"])
    pending = list(state["pending_skills"])

    if player["role"] == Role.IDIOT and not player["idiot_revealed"] and state["runtime"]["rule_flags"].get("idiot_survives_exile", False):
        players_patch[target] = {"idiot_revealed": True, "can_vote": False}
        _append_live_event(
            services,
            state,
            events,
            GameEvent(
                game_id=state["game_id"],
                phase=state["phase"],
                scope=EventScope.PUBLIC,
                target_players=set(),
                event_type=EventType.SKILL_TRIGGERED,
                content="event.idiot_revealed",
                data={"player_id": target},
            ),
            round_no=state["round"],
        )
    else:
        players_patch[target] = {"alive": False, "death_round": state["round"], "death_cause": "exile", "is_sheriff": False}
        dead_history.append({"player_id": target, "cause": "exile", "round": state["round"]})
        _append_live_event(
            services,
            state,
            events,
            GameEvent(
                game_id=state["game_id"],
                phase=state["phase"],
                scope=EventScope.PUBLIC,
                target_players=set(),
                event_type=EventType.PLAYER_DIED,
                content=_event_content_key(EventType.PLAYER_DIED),
                data={"player_id": target, "cause": "exile"},
            ),
            round_no=state["round"],
        )
        _queue_death_skills(state, pending, target, "exile")

        # Collect death speech (遗言) for exiled player
        speech_events = await _collect_death_speeches(state, services, [target], death_causes={target: "exile"})
        events.extend(speech_events)

    return PhaseResult(
        state_patch={
            "players": players_patch,
            "dead_history": dead_history,
            "pending_skills": pending,
            "sheriff_id": None if player["is_sheriff"] else state["sheriff_id"],
            "round": state["round"] + 1,
            "day_index": state["day_index"] + 1,
        },
        events=events,
        persisted_event_count=len(events),
    )


async def _handle_pending_skills(state: GameState, services: SessionServices) -> PhaseResult:
    pending = list(state["pending_skills"])
    if not pending:
        return PhaseResult(next_phase_override=Phase.CHECK_WIN)

    players_patch: dict[int, dict] = {}
    dead_history = list(state["dead_history"])
    events: list[GameEvent] = []

    while pending:
        skill = pending.pop(0)
        if skill["kind"] == "hunter_shot":
            actor_id = skill["actor_id"]
            candidates = [pid for pid in alive_player_ids(state) if pid != actor_id and pid not in players_patch]
            if not candidates:
                continue
            proposed_args = await _llm_tool_or_local(
                state,
                services,
                actor_id=actor_id,
                role=state["players"][actor_id]["role"],
                phase=state["phase"],
                tool_name="hunter_shoot",
                local_args={"target_id": services.rng.choice(candidates)},
                prompt_key_override="hunter_shoot.j2",
            )
            action = _validate_or_raise(
                state,
                services,
                actor_id=actor_id,
                role=state["players"][actor_id]["role"],
                phase=state["phase"],
                tool_name="hunter_shoot",
                args=proposed_args,
            )
            target = action["args"]["target_id"]
            players_patch[target] = {"alive": False, "death_round": state["round"], "death_cause": "hunter_shot"}
            dead_history.append({"player_id": target, "cause": "hunter_shot", "round": state["round"]})
            events.append(
                GameEvent(
                    game_id=state["game_id"],
                    phase=state["phase"],
                    scope=EventScope.PUBLIC,
                    target_players=set(),
                    event_type=EventType.PLAYER_DIED,
                    content=_event_content_key(EventType.PLAYER_DIED),
                    data={"player_id": target, "cause": "hunter_shot"},
                )
            )
            events.append(
                GameEvent(
                    game_id=state["game_id"],
                    phase=state["phase"],
                    scope=EventScope.PUBLIC,
                    target_players=set(),
                    event_type=EventType.SKILL_TRIGGERED,
                    content="event.hunter_shot",
                    data={"actor_id": actor_id, "target_id": target},
                )
            )
        elif skill["kind"] == "sheriff_transfer":
            actor_id = skill["actor_id"]
            candidates = [pid for pid in alive_player_ids(state) if pid != actor_id]
            proposed_args = await _llm_tool_or_local(
                state,
                services,
                actor_id=actor_id,
                role=state["players"][actor_id]["role"],
                phase=state["phase"],
                tool_name="sheriff_transfer",
                local_args={"target_id": services.rng.choice(candidates) if candidates else None},
                prompt_key_override="sheriff_transfer.j2",
            )
            action = _validate_or_raise(
                state,
                services,
                actor_id=actor_id,
                role=state["players"][actor_id]["role"],
                phase=state["phase"],
                tool_name="sheriff_transfer",
                args=proposed_args,
            )
            new_sheriff = action["args"]["target_id"]
            if new_sheriff is not None:
                players_patch[new_sheriff] = {**players_patch.get(new_sheriff, {}), "is_sheriff": True}
            events.append(
                GameEvent(
                    game_id=state["game_id"],
                    phase=state["phase"],
                    scope=EventScope.PUBLIC,
                    target_players=set(),
                    event_type=EventType.SHERIFF_TRANSFERRED,
                    content=_event_content_key(EventType.SHERIFF_TRANSFERRED),
                    data={"actor_id": actor_id, "target_id": new_sheriff},
                )
            )
            return PhaseResult(
                state_patch={"players": players_patch, "dead_history": dead_history, "pending_skills": pending, "sheriff_id": new_sheriff},
                events=events,
                next_phase_override=Phase.CHECK_WIN,
            )

    return PhaseResult(
        state_patch={"players": players_patch, "dead_history": dead_history, "pending_skills": pending},
        events=events,
        next_phase_override=Phase.CHECK_WIN,
    )


def _handle_check_win(state: GameState, services: SessionServices) -> PhaseResult:
    winner, reason = check_win(state, state["runtime"])
    if winner is not None:
        return PhaseResult(
            state_patch={"winner": winner, "ended": True, "status": GameStatus.COMPLETED},
            next_phase_override=Phase.GAME_OVER,
            events=[
                GameEvent(
                    game_id=state["game_id"],
                    phase=state["phase"],
                    scope=EventScope.PUBLIC,
                    target_players=set(),
                    event_type=EventType.GAME_ENDED,
                    content=_event_content_key(EventType.GAME_ENDED),
                    data={"winner": winner, "reason": reason},
                )
            ],
        )
    if state["phase_index"] + 1 < len(state["runtime"]["phase_order"]) and state["runtime"]["phase_order"][state["phase_index"] + 1] == Phase.GAME_OVER:
        return PhaseResult(next_phase_override=Phase.NIGHT_START)
    return PhaseResult(events=[])


def _handle_game_over(state: GameState, services: SessionServices) -> PhaseResult:
    return PhaseResult(state_patch={"ended": True, "status": GameStatus.COMPLETED})


def _find_alive_role(state: GameState, role: Role) -> int | None:
    for player_id, player in state["players"].items():
        if player["alive"] and player["role"] == role:
            return player_id
    return None


def _determine_speech_order(state: GameState) -> list[int]:
    """Determine speech order based on werewolf rules.

    With sheriff: start next to sheriff, sheriff speaks last, direction alternates per day.
    Without sheriff: time-based start, direction from minute parity. If night deaths,
    start adjacent to the first dead player.
    """
    alive = alive_player_ids(state)
    if len(alive) <= 1:
        return alive

    sheriff_id = state.get("sheriff_id")
    day_index = state.get("day_index", 1)
    night_deaths = state.get("night_result", {}).get("deaths", [])

    if sheriff_id is not None and sheriff_id in state["players"]:
        # With sheriff: sheriff speaks last
        # Day 1: use sheriff's chosen direction from election
        # Later days: alternate direction
        if day_index <= 1 and state.get("sheriff_speech_clockwise") is not None:
            clockwise = state["sheriff_speech_clockwise"]
        else:
            clockwise = day_index % 2 == 1
        ordered = _build_ring_order(alive, start_ref=sheriff_id, clockwise=clockwise, speak_last=sheriff_id)
    else:
        # Without sheriff
        if night_deaths:
            # Start from alive player adjacent to first dead player
            start_ref = night_deaths[0]
        else:
            # Time-based: sum of minute digits -> player id (mod total)
            now = datetime.now(TZ_CN)
            minute = now.minute
            digit_sum = (minute // 10) + (minute % 10)
            # Use modulo to map into player range
            total = len(alive)
            start_idx = digit_sum % total
            start_ref = alive[start_idx]

        # Direction: odd minute = clockwise, even minute = counter-clockwise
        clockwise = datetime.now().minute % 2 == 1
        ordered = _build_ring_order(alive, start_ref=start_ref, clockwise=clockwise, speak_last=None)

    return ordered


async def _resolve_sheriff_election(
    state: GameState,
    services: SessionServices,
    votes: dict[int, int],
    candidates: list[int],
    voters: list[int],
    events: list[GameEvent],
    actions: list,
) -> tuple[int | None, dict[int, int] | PhaseResult]:
    """Resolve sheriff election with full tie-breaking: extra speech + re-vote.

    Returns (sheriff_id_or_None, final_votes) or (None, PhaseResult) if self-destruct happened.

    Returns (sheriff_id_or_None, final_votes).
    """
    sheriff_id = _resolve_sheriff_vote(votes, services.rng, candidates=candidates)
    if sheriff_id is not None:
        return sheriff_id, votes

    # Tie! Extra speech round for tied candidates
    tally: dict[int, int] = {}
    for target in votes.values():
        if target is not None and target in candidates:
            tally[target] = tally.get(target, 0) + 1
    if not tally:
        return None, votes
    top = max(tally.values())
    tied = sorted(pid for pid, count in tally.items() if count == top)

    # Tied candidates give extra speeches
    for player_id in tied:
        role = state["players"][player_id]["role"]
        _append_speaking_started(services, state, events, player_id=player_id)
        proposed_args = await _llm_speech_or_local(
            state,
            services,
            actor_id=player_id,
            role=role,
            phase=state["phase"],
            local_args={
                "public_speech": f"玩家{player_id}平票补充发言",
                "internal_thought": "",
            },
        )
        speech = proposed_args.get("public_speech", "")
        if speech:
            _append_live_event(
                services,
                state,
                events,
                GameEvent(
                    game_id=state["game_id"],
                    phase=state["phase"],
                    scope=EventScope.PUBLIC,
                    target_players=set(),
                    event_type=EventType.SHERIFF_CAMPAIGN,
                    content=_event_content_key(EventType.SHERIFF_CAMPAIGN),
                    data={"player_id": player_id, "speech": speech, "tie_breaker": True},
                ),
                round_no=state["round"],
            )

    # Re-vote among tied candidates only
    new_votes: dict[int, int] = {}
    for voter in voters:
        voter_candidates = [pid for pid in tied if pid != voter] or list(tied)
        if not voter_candidates:
            new_votes[voter] = None
            continue
        proposed_args = await _llm_tool_or_local(
            state,
            services,
            actor_id=voter,
            role=state["players"][voter]["role"],
            phase=state["phase"],
            tool_name="vote_target",
            local_args={"target_id": services.rng.choice(voter_candidates)},
            prompt_key_override="sheriff_vote.j2",
            decision_note=(
                "现在是警长平票后的再次投票，不是补充发言。"
                f"你必须从平票候选人 {voter_candidates} 中选择一人，把 target_id 设置为候选人的编号。"
                "不要输出普通文本，不要发表演讲。"
            ),
        )
        # Check if wolf chose to self-destruct during tie-break vote
        if proposed_args.get("_wolf_self_destruct"):
            result = _build_self_destruct_result(state, voter)
            merged = dict(result)
            merged["events"] = events + result.get("events", [])
            merged["actions"] = actions + result.get("actions", [])
            merged["persisted_event_count"] = len(events)
            return None, PhaseResult(**merged)
        action = _validate_or_raise(
            state,
            services,
            actor_id=voter,
            role=state["players"][voter]["role"],
            phase=state["phase"],
            tool_name="vote_target",
            args=proposed_args,
        )
        actions.append(action)
        target = action["args"].get("target_id")
        if target not in tied:
            target = services.rng.choice(tied) if tied else None
        new_votes[voter] = target

    # Second tally
    sheriff_id = _resolve_sheriff_vote(new_votes, services.rng, candidates=tied)
    if sheriff_id is not None:
        return sheriff_id, new_votes

    # Second tie — no sheriff this game
    return None, new_votes


def _is_phase_result(value: object) -> TypeGuard[PhaseResult]:
    if not isinstance(value, dict):
        return False
    return any(
        key in value
        for key in (
            "state_patch",
            "events",
            "persisted_event_count",
            "pending_skills",
            "next_phase_override",
            "snapshots",
            "actions",
        )
    )


def _resolve_sheriff_vote(votes: dict[int, int], rng: Random, *, candidates: list[int] | None = None) -> int | None:
    """Resolve sheriff election with tie-breaking. Returns None if no winner."""
    if not votes:
        return None
    tally: dict[int, int] = {}
    for target in votes.values():
        if target is None:
            continue
        if candidates is not None and target not in candidates:
            continue  # ignore votes for non-candidates
        tally[target] = tally.get(target, 0) + 1
    if not tally:
        return None
    top = max(tally.values())
    tied = sorted(pid for pid, count in tally.items() if count == top)
    if len(tied) == 1:
        return tied[0]
    # Tie: random pick (full re-vote would need additional game phases)
    return rng.choice(tied)


async def _decide_candidacy(
    state: GameState,
    services: SessionServices,
    player_id: int,
) -> bool:
    """Decide whether a player wants to run for sheriff. Uses LLM or role-based fallback."""
    role = state["players"][player_id]["role"]
    if services.llm_client is None or services.llm_settings is None:
        # No LLM: role-based weights
        weights: dict[Role, float] = {
            Role.WOLF: 0.6,
            Role.SEER: 0.98,
            Role.WITCH: 0.3,
            Role.HUNTER: 0.65,
            Role.IDIOT: 0.08,
            Role.GUARD: 0.5,
            Role.VILLAGER: 0.05,
        }
        return services.rng.random() < weights.get(role, 0.5)

    # Build prompt with role-specific strategy hints
    role_hints: dict[Role, str] = {
        Role.WOLF: "你是狼人。标准局中狼队通常派一人悍跳预言家抢警徽，这是核心策略。你有较大可能需要参选——即使不悍跳预言家，上警也可以扰乱好人视角。除非你判断自己绝对不适合暴露，否则应选择参选。",
        Role.SEER: "你是预言家。警徽是你的核心资源，通常必须上警争夺警徽，并用警徽流传递后续验人信息。除非出现极端情况，否则应该参选。",
        Role.WITCH: "你是女巫。女巫通常倾向隐藏，尤其首夜救人后不宜轻易暴露。只有在真预言家弱势、需要强神带队、你吃刀/银水被质疑，或局势明显需要你抢警徽时才参选。",
        Role.HUNTER: "你是猎人。猎人是强神，不怕出局，具备较明显上警倾向；如果你想明跳带队或局势混乱，可以参选。若想隐藏身份，也可以不上警。",
        Role.IDIOT: "你是白痴。白痴通常隐藏起来当普通村民打，极少上警。乱上警容易吃验吃推并浪费容错技能，默认不要参选。",
        Role.GUARD: "你是守卫。通常不建议高调参选，隐藏身份保护关键角色更重要。",
        Role.VILLAGER: "你是普通村民。村民是闭眼信息最少的牌，原则上避免盲目上警，避免扰乱预言家和强神视角。除非你有明确高端战术目的，否则不要参选。",
    }
    hint = role_hints.get(role, "")
    context = build_prompt_context(state, player_id=player_id)
    user_payload = build_prompt_inputs(
        state["runtime"], player_id=player_id, role=role,
        phase=Phase.SHERIFF_ELECTION, context=context,
    )
    static_rules = (
        "当前正在进行第一轮警长竞选。\n"
        "这是标准 12 人预女猎白局。警徽优先级通常是：预言家几乎必上警；狼队通常只派一名狼人悍跳；猎人有明显上警倾向；女巫中等偏低；白痴极少上警；普通村民原则上不上警、不添乱。\n"
        '请按你的身份和局势严格决定是否要举手参选警长，不要为了"积极发言"而盲目参选。'
    )
    tool_instruction = "You must call the only available tool: vote_target. Do not answer in plain text."
    dynamic_state = (
        f"你是玩家{player_id}，身份是{role.value}。\n"
        f"{hint}\n\n"
        f"调用 vote_target 工具：如果参选请投给自己（target_id={player_id}），如果不参选请投给任意其他存活玩家。"
    )
    system_prompts, user_content = _build_cache_friendly_system_and_user(
        user_payload, tool_instruction, static_rules, dynamic_state,
    )
    messages = build_phase_messages(system_prompts=system_prompts, user_content=user_content)
    tools = [t for t in TOOL_REGISTRY.values() if t["name"] == "vote_target"]

    services.total_llm_calls += 1
    if services.llm_semaphore is None:
        result = await services.llm_client.call_with_tools(messages=messages, tools=tools, force_tool=True)
    else:
        async with services.llm_semaphore:
            result = await services.llm_client.call_with_tools(messages=messages, tools=tools, force_tool=True)

    _persist_llm_call(
        services, state, actor_id=player_id, phase=Phase.SHERIFF_ELECTION,
        prompt_key="sheriff_candidacy", result=result,
    )

    if not result.success or result.tool_args is None:
        _raise_llm_failure(result, actor_id=player_id, phase=Phase.SHERIFF_ELECTION, expected_tool="vote_target")

    target_id = result.tool_args.get("target_id")
    return target_id is not None and int(target_id) == player_id


async def _sheriff_pick_direction(
    state: GameState,
    services: SessionServices,
    sheriff_id: int,
) -> bool:
    """Sheriff picks speech direction: True=clockwise (从左手边), False=counter-clockwise (从右手边)."""
    if services.llm_client is None or services.llm_settings is None:
        return services.rng.random() < 0.5

    # For now, use random direction with LLM too
    return services.rng.random() < 0.5


def _build_ring_order(
    alive: list[int],
    *,
    start_ref: int,
    clockwise: bool,
    speak_last: int | None,
) -> list[int]:
    """Build a ring order from alive players starting next to start_ref."""
    sorted_alive = sorted(alive)
    n = len(sorted_alive)

    if start_ref not in sorted_alive:
        # start_ref might be a dead player — find next alive in ring
        start_idx = 0
        for i, pid in enumerate(sorted_alive):
            if pid > start_ref:
                start_idx = i
                break
    else:
        start_idx = sorted_alive.index(start_ref)

    # Build ring starting from start_idx + 1 (next person after reference)
    result = []
    for offset in range(1, n + 1):
        if clockwise:
            idx = (start_idx + offset) % n
        else:
            idx = (start_idx - offset) % n
        pid = sorted_alive[idx]
        if pid == speak_last:
            continue  # will be appended at the end
        result.append(pid)

    if speak_last is not None and speak_last in sorted_alive:
        result.append(speak_last)

    return result


async def _collect_death_speeches(
    state: GameState,
    services: SessionServices,
    dead_player_ids: list[int],
    *,
    death_causes: dict[int, str] | None = None,
) -> list[GameEvent]:
    """Collect death speeches (遗言) for newly dead players.

    Rules: only first-night deaths and exiled players get last words.
    """
    events: list[GameEvent] = []
    is_first_night = state["round"] == 1

    for player_id in dead_player_ids:
        if not is_first_night and state["phase"] != Phase.DAY_RESOLVE:
            continue  # Only first-night deaths and exiles get last words

        role = state["players"][player_id]["role"]
        cause = (death_causes or {}).get(player_id) or state["players"][player_id].get("death_cause")
        _append_speaking_started(services, state, events, player_id=player_id)
        # Death speeches bypass the normal tool phase-filter since they can happen
        # in night_resolve (not a normal speech phase)
        proposed_args = await _llm_death_speech_or_local(
            state,
            services,
            actor_id=player_id,
            role=role,
            phase=state["phase"],
            local_args={
                "public_speech": f"玩家{player_id}（{role.value}）的遗言",
                "internal_thought": "",
            },
        )
        speech = proposed_args.get("public_speech", "")
        if speech:
            _append_live_event(
                services,
                state,
                events,
                GameEvent(
                    game_id=state["game_id"],
                    phase=state["phase"],
                    scope=EventScope.PUBLIC,
                    target_players=set(),
                    event_type=EventType.DEATH_SPEECH,
                    content=_event_content_key(EventType.DEATH_SPEECH),
                    data={"player_id": player_id, "speech": speech, "cause": cause},
                ),
                round_no=state["round"],
            )
    return events


def _queue_death_skills(state: GameState, pending: list[PendingSkill], player_id: int, cause: str) -> None:
    player = state["players"][player_id]
    if player["role"] == Role.HUNTER:
        can_shoot_if_poisoned = state["runtime"]["rule_flags"].get("hunter_can_shoot_if_poisoned", False)
        if cause != "poison" or can_shoot_if_poisoned:
            pending.append({"kind": "hunter_shot", "actor_id": player_id, "context": {"cause": cause}})
    if player["is_sheriff"]:
        pending.append({"kind": "sheriff_transfer", "actor_id": player_id, "context": {"cause": cause}})


def _build_self_destruct_result(state: GameState, wolf_id: int) -> PhaseResult:
    """Build PhaseResult for a wolf self-destructing during a day phase."""
    current_phase = state["phase"]
    events: list[GameEvent] = []
    players_patch: dict[int, dict] = {
        wolf_id: {"alive": False, "death_round": state["round"], "death_cause": "self_destruct", "is_sheriff": False},
    }
    state_patch: dict = {"players": players_patch}

    # Append to dead_history
    dead_history = list(state["dead_history"])
    dead_history.append({"player_id": wolf_id, "cause": "self_destruct", "round": state["round"]})
    state_patch["dead_history"] = dead_history

    # During campaign: badge is destroyed
    if current_phase == Phase.SHERIFF_ELECTION:
        state_patch["sheriff_id"] = None

    # If self-destructing wolf is sheriff, badge destroyed
    if state["players"][wolf_id]["is_sheriff"]:
        state_patch["sheriff_id"] = None

    events.append(
        GameEvent(
            game_id=state["game_id"],
            phase=current_phase,
            scope=EventScope.PUBLIC,
            target_players=set(),
            event_type=EventType.WOLF_SELF_DESTRUCT,
            content=_event_content_key(EventType.WOLF_SELF_DESTRUCT),
            data={"player_id": wolf_id},
        )
    )

    # Force enter night
    state_patch["round"] = state["round"] + 1
    state_patch["day_index"] = state["day_index"] + 1

    return PhaseResult(
        state_patch=state_patch,
        events=events,
        next_phase_override=Phase.NIGHT_START,
    )


_PHASE_HANDLERS = {
    Phase.SETUP_GAME: _handle_setup_game,
    Phase.NIGHT_START: _handle_night_start,
    Phase.NIGHT_WOLF: _handle_night_wolf,
    Phase.NIGHT_SEER: _handle_night_seer,
    Phase.NIGHT_WITCH: _handle_night_witch,
    Phase.NIGHT_RESOLVE: _handle_night_resolve,
    Phase.DAY_ANNOUNCE: _handle_day_announce,
    Phase.SHERIFF_ELECTION: _handle_sheriff_election,
    Phase.DAY_SPEECH: _handle_day_speech,
    Phase.DAY_VOTE: _handle_day_vote,
    Phase.DAY_RESOLVE: _handle_day_resolve,
    Phase.PENDING_SKILLS: _handle_pending_skills,
    Phase.CHECK_WIN: _handle_check_win,
    Phase.GAME_OVER: _handle_game_over,
}


async def _llm_tool_or_local(
    state: GameState,
    services: SessionServices,
    *,
    actor_id: int,
    role: Role,
    phase: Phase,
    tool_name: str,
    local_args: dict,
    prompt_key_override: str | None = None,
    decision_note: str | None = None,
) -> dict:
    """LLM tool call. For wolves in day phases, also offers wolf_self_destruct.
    Returns normal args dict, or {"_wolf_self_destruct": True} if wolf chose to self-destruct."""
    if services.llm_client is None or services.llm_settings is None:
        return local_args
    if phase.value not in services.llm_settings.enabled_phase_names:
        return local_args
    if services.total_llm_calls >= services.llm_settings.max_calls_per_game:
        raise RuntimeError(
            f"LLM call limit reached before {phase.value}/{tool_name} "
            f"for player {actor_id}: {services.total_llm_calls}/{services.llm_settings.max_calls_per_game}"
        )

    context = build_prompt_context(state, player_id=actor_id)
    prompt_key = prompt_key_override or resolve_prompt_template(state["runtime"], phase, role)
    user_payload = build_prompt_inputs(
        state["runtime"],
        player_id=actor_id,
        role=role,
        phase=phase,
        context=context,
    )
    template = load_prompt_template(services.paths.prompts, prompt_key)
    rendered_prompt = render_prompt_template(template, user_payload)
    if decision_note:
        rendered_prompt = f"{rendered_prompt}\n\n{decision_note}"
    static_rules, dynamic_state = split_rendered_template(rendered_prompt)
    tool_instruction = f"You must call the only available tool: {tool_name}. Do not answer in plain text."
    system_prompts, user_content = _build_cache_friendly_system_and_user(
        user_payload, tool_instruction, static_rules, dynamic_state,
    )
    messages = build_phase_messages(system_prompts=system_prompts, user_content=user_content)
    messages = _messages_with_player_history(state, actor_id=actor_id, messages=messages)

    # Build tool list: primary tool, plus wolf_self_destruct for wolves in day phases
    tools = [tool for tool in enabled_tools(state["runtime"], role, phase) if tool["name"] == tool_name]
    is_wolf_day = role == Role.WOLF and phase in (
        Phase.DAY_SPEECH, Phase.DAY_VOTE, Phase.SHERIFF_ELECTION,
    )
    if is_wolf_day:
        sd_tool = [t for t in TOOL_REGISTRY.values() if t["name"] == "wolf_self_destruct"]
        tools.extend(sd_tool)

    services.total_llm_calls += 1
    if services.llm_semaphore is None:
        result = await services.llm_client.call_with_tools(messages=messages, tools=tools, force_tool=True)
    else:
        async with services.llm_semaphore:
            result = await services.llm_client.call_with_tools(messages=messages, tools=tools, force_tool=True)
    _persist_llm_call(
        services,
        state,
        actor_id=actor_id,
        phase=phase,
        prompt_key=prompt_key,
        result=result,
    )

    # Check if wolf chose self-destruct
    if is_wolf_day and result.success and result.tool_name == "wolf_self_destruct":
        return {"_wolf_self_destruct": True}

    # If tool call failed, retry once with failure context
    if not result.success or result.tool_name != tool_name or result.tool_args is None:
        failure_reason = result.error_message or ""
        if not result.success:
            failure_reason = failure_reason or "LLM call failed"
        elif result.tool_name != tool_name:
            failure_reason = f"called wrong tool '{result.tool_name}' instead of '{tool_name}'"
        elif result.tool_args is None:
            failure_reason = "called tool without arguments"

        if services.total_llm_calls < services.llm_settings.max_calls_per_game:
            retry_messages = list(messages)
            if result.assistant_message:
                retry_messages.append(result.assistant_message)
            retry_messages.append({
                "role": "user",
                "content": (
                    f"上一轮工具调用失败：{failure_reason}。"
                    f"你必须调用 {tool_name} 工具，不要输出普通文本。"
                ),
            })
            services.total_llm_calls += 1
            if services.llm_semaphore is None:
                result = await services.llm_client.call_with_tools(messages=retry_messages, tools=tools, force_tool=True)
            else:
                async with services.llm_semaphore:
                    result = await services.llm_client.call_with_tools(messages=retry_messages, tools=tools, force_tool=True)
            _persist_llm_call(services, state, actor_id=actor_id, phase=phase, prompt_key=f"{prompt_key}:retry", result=result)

            # Check self-destruct on retry too
            if is_wolf_day and result.success and result.tool_name == "wolf_self_destruct":
                return {"_wolf_self_destruct": True}

        if not result.success or result.tool_name != tool_name or result.tool_args is None:
            logging.getLogger(__name__).warning(
                "LLM tool call failed for P%s %s/%s after retry: %s — using fallback",
                actor_id, phase.value, tool_name, failure_reason,
            )
            return local_args

    _append_llm_messages(state, actor_id=actor_id, request_messages=messages, result=result)
    return result.tool_args


async def _llm_speech_or_local(
    state: GameState,
    services: SessionServices,
    *,
    actor_id: int,
    role: Role,
    phase: Phase,
    local_args: dict,
) -> dict:
    """LLM speech call. For wolves in day phases, also offers wolf_self_destruct.
    Returns normal args dict, or {"_wolf_self_destruct": True} if wolf chose to self-destruct."""
    if services.llm_client is None or services.llm_settings is None:
        return local_args
    if phase.value not in services.llm_settings.enabled_phase_names:
        return local_args
    if services.total_llm_calls >= services.llm_settings.max_calls_per_game:
        raise RuntimeError(
            f"LLM call limit reached before {phase.value}/public_speech "
            f"for player {actor_id}: {services.total_llm_calls}/{services.llm_settings.max_calls_per_game}"
        )

    context = build_prompt_context(state, player_id=actor_id)
    prompt_key = resolve_prompt_template(state["runtime"], phase, role)
    user_payload = build_prompt_inputs(
        state["runtime"],
        player_id=actor_id,
        role=role,
        phase=phase,
        context=context,
    )
    template = load_prompt_template(services.paths.prompts, prompt_key)
    rendered_prompt = render_prompt_template(template, user_payload)
    static_rules, dynamic_state = split_rendered_template(rendered_prompt)
    tool_instruction = "You must call the only available tool: public_speech. Do not answer in plain text."
    system_prompts, user_content = _build_cache_friendly_system_and_user(
        user_payload, tool_instruction, static_rules, dynamic_state,
    )
    messages = build_phase_messages(system_prompts=system_prompts, user_content=user_content)
    messages = _messages_with_player_history(state, actor_id=actor_id, messages=messages)

    # Build tool list: always public_speech, plus wolf_self_destruct for wolves in day phases
    tools = [tool for tool in enabled_tools(state["runtime"], role, phase) if tool["name"] == "public_speech"]
    is_wolf_day = role == Role.WOLF and phase in (
        Phase.DAY_SPEECH, Phase.DAY_VOTE, Phase.SHERIFF_ELECTION,
    )
    if is_wolf_day:
        sd_tool = [t for t in TOOL_REGISTRY.values() if t["name"] == "wolf_self_destruct"]
        tools.extend(sd_tool)

    services.total_llm_calls += 1
    if services.llm_semaphore is None:
        result = await services.llm_client.call_with_tools(messages=messages, tools=tools, force_tool=True)
    else:
        async with services.llm_semaphore:
            result = await services.llm_client.call_with_tools(messages=messages, tools=tools, force_tool=True)
    _persist_llm_call(
        services,
        state,
        actor_id=actor_id,
        phase=phase,
        prompt_key=prompt_key,
        result=result,
    )

    # Check if wolf chose self-destruct
    if is_wolf_day and result.success and result.tool_name == "wolf_self_destruct":
        return {"_wolf_self_destruct": True}

    # If tool call failed, retry once with failure context
    if not result.success or result.tool_name != "public_speech" or result.tool_args is None:
        failure_reason = result.error_message or ""
        if not result.success:
            failure_reason = failure_reason or "LLM call failed"
        elif result.tool_name != "public_speech":
            failure_reason = f"called wrong tool '{result.tool_name}' instead of 'public_speech'"
        elif result.tool_args is None:
            failure_reason = "called tool without arguments"

        if services.total_llm_calls < services.llm_settings.max_calls_per_game:
            retry_messages = list(messages)
            if result.assistant_message:
                retry_messages.append(result.assistant_message)
            retry_messages.append({
                "role": "user",
                "content": (
                    f"上一轮工具调用失败：{failure_reason}。"
                    f"你必须调用 public_speech 工具，不要输出普通文本。"
                ),
            })
            services.total_llm_calls += 1
            if services.llm_semaphore is None:
                result = await services.llm_client.call_with_tools(messages=retry_messages, tools=tools, force_tool=True)
            else:
                async with services.llm_semaphore:
                    result = await services.llm_client.call_with_tools(messages=retry_messages, tools=tools, force_tool=True)
            _persist_llm_call(services, state, actor_id=actor_id, phase=phase, prompt_key="speech:retry", result=result)

            if is_wolf_day and result.success and result.tool_name == "wolf_self_destruct":
                return {"_wolf_self_destruct": True}

        if not result.success or result.tool_name != "public_speech" or result.tool_args is None:
            logging.getLogger(__name__).warning(
                "LLM speech call failed for P%s %s after retry: %s — using fallback",
                actor_id, phase.value, failure_reason,
            )
            return local_args

    _append_llm_messages(state, actor_id=actor_id, request_messages=messages, result=result)
    return result.tool_args


def _raise_llm_failure(
    result: LLMCallResult,
    *,
    actor_id: int,
    phase: Phase,
    expected_tool: str,
) -> None:
    actual_tool = result.tool_name or "-"
    reason = result.error_message or "invalid model response"
    raise RuntimeError(
        f"LLM call failed for player {actor_id} in {phase.value}: "
        f"expected tool {expected_tool}, got {actual_tool}; {reason}"
    )


async def _llm_death_speech_or_local(
    state: GameState,
    services: SessionServices,
    *,
    actor_id: int,
    role: Role,
    phase: Phase,
    local_args: dict,
) -> dict:
    """Like _llm_speech_or_local but bypasses phase-based tool filtering for death speeches."""
    if services.llm_client is None or services.llm_settings is None:
        return local_args
    if services.total_llm_calls >= services.llm_settings.max_calls_per_game:
        return local_args

    context = build_prompt_context(state, player_id=actor_id)
    user_payload = build_prompt_inputs(
        state["runtime"], player_id=actor_id, role=role, phase=phase, context=context,
    )
    static_rules = "你已出局，现在发表遗言。"
    tool_instruction = "You must call the only available tool: public_speech. Do not answer in plain text."
    dynamic_state = f"你的编号是 {actor_id}，身份是 {role.value}。"
    system_prompts, user_content = _build_cache_friendly_system_and_user(
        user_payload, tool_instruction, static_rules, dynamic_state,
    )
    messages = build_phase_messages(system_prompts=system_prompts, user_content=user_content)
    messages = _messages_with_player_history(state, actor_id=actor_id, messages=messages)
    # Always provide public_speech tool regardless of phase
    tools = [t for t in TOOL_REGISTRY.values() if t["name"] == "public_speech"]

    services.total_llm_calls += 1
    if services.llm_semaphore is None:
        result = await services.llm_client.call_with_tools(messages=messages, tools=tools, force_tool=True)
    else:
        async with services.llm_semaphore:
            result = await services.llm_client.call_with_tools(messages=messages, tools=tools, force_tool=True)
    _persist_llm_call(services, state, actor_id=actor_id, phase=phase, prompt_key="death_speech", result=result)

    if not result.success or result.tool_name != "public_speech" or result.tool_args is None:
        return local_args
    return result.tool_args


def _build_cache_friendly_system_and_user(
    user_payload: dict, tool_instruction: str, role_system: str, dynamic_state: str,
) -> tuple[list[str], str]:
    """Build system prompts and user content optimized for LLM prefix cache hits.

    Layout:
      System 1: _COMMON_RULES + public_state + tool_instruction  (shared by ALL 12 players)
      System 2: role_system                                      (shared by same-role players)
      User:     dynamic_state (private info)                      (unique per player)
    """
    visible_state = user_payload.get("visible_state")
    if visible_state:
        public_json = json.dumps(visible_state, ensure_ascii=False, sort_keys=True)
        common_system = f"{_COMMON_RULES}\n\n<public_state>\n{public_json}\n</public_state>\n\n{tool_instruction}"
    else:
        common_system = f"{_COMMON_RULES}\n\n{tool_instruction}"
    system_prompts = [common_system, role_system] if role_system else [common_system]
    return system_prompts, dynamic_state


def _messages_with_player_history(
    state: GameState,
    *,
    actor_id: int,
    messages: list[dict],
) -> list[dict]:
    history = _player_llm_messages(state, actor_id)
    if not history:
        return messages
    system_messages = [message for message in messages if message.get("role") == "system"]
    user_messages = [message for message in messages if message.get("role") != "system"]
    return system_messages + history + user_messages


def _player_llm_messages(state: GameState, actor_id: int) -> list[dict]:
    for item in reversed(state["players"][actor_id]["private_memory"]):
        if item.get("kind") == "llm_messages" and isinstance(item.get("messages"), list):
            return [dict(message) for message in item["messages"] if isinstance(message, dict)]
    return []


def _append_llm_messages(
    state: GameState,
    *,
    actor_id: int,
    request_messages: list[dict],
    result: LLMCallResult,
) -> None:
    if result.assistant_message is None:
        return
    if result.assistant_message.get("tool_calls"):
        return
    user_messages = [message for message in request_messages if message.get("role") == "user"]
    if not user_messages:
        return
    history = _player_llm_messages(state, actor_id)
    history.append(dict(user_messages[-1]))
    history.append(_sanitize_assistant_message(result.assistant_message))
    state["players"][actor_id]["private_memory"].append({"kind": "llm_messages", "messages": history[-24:]})


def _sanitize_assistant_message(message: dict[str, Any]) -> dict[str, Any]:
    allowed = {"role", "content", "reasoning_content", "tool_calls"}
    sanitized = {key: value for key, value in message.items() if key in allowed}
    sanitized.setdefault("role", "assistant")
    if "content" not in sanitized:
        sanitized["content"] = ""
    return sanitized


def _action_source(services: SessionServices, phase: Phase) -> str:
    if services.llm_client is not None and services.llm_settings is not None and phase.value in services.llm_settings.enabled_phase_names:
        return "llm"
    return "fallback"


def _raise_llm_required(services: SessionServices, phase: Phase, message: str) -> None:
    if services.llm_client is not None and services.llm_settings is not None and phase.value in services.llm_settings.enabled_phase_names:
        raise RuntimeError(f"required LLM call failed in {phase.value}: {message}")
    if services.llm_client is not None and services.llm_settings is not None:
        raise RuntimeError(f"required LLM call failed in {phase.value}: {message}")
    raise RuntimeError(f"LLM is not configured for required decision in {phase.value}: {message}")


def _validate_or_raise(
    state: GameState,
    services: SessionServices,
    *,
    actor_id: int,
    role: Role,
    phase: Phase,
    tool_name: str,
    args: dict,
):
    proposed = {
        "actor_id": actor_id,
        "phase": phase,
        "tool_name": tool_name,
        "raw_args": args,
        "source": _action_source(services, phase),
    }
    validated = validate_tool_call(
        state=state,
        runtime=state["runtime"],
        actor_id=actor_id,
        role=role,
        phase=phase,
        proposed=proposed,
    )
    if not validated["is_valid"]:
        errors = validated.get("validation_errors", [])
        if services.llm_client is not None:
            logging.getLogger(__name__).warning(
                "invalid %s args for player %s in %s: %s – using fallback",
                tool_name, actor_id, phase.value, errors,
            )
            validated = validated.copy()
            validated["is_valid"] = True
            validated["validation_errors"] = []
            # Provide safe fallback args based on tool type
            fallback_args = dict(args)  # prefer original args
            if tool_name in {"wolf_kill_proposal", "seer_check", "vote_target", "hunter_shoot"}:
                if "target_id" not in fallback_args:
                    # Pick a random valid target
                    candidates = [pid for pid in alive_player_ids(state) if pid != actor_id]
                    fallback_args["target_id"] = candidates[0] if candidates else None
            validated["args"] = fallback_args
        else:
            _raise_llm_required(
                services,
                phase,
                f"invalid {tool_name} args for player {actor_id}: {errors}",
            )
    return resolve_action(validated)


# Phases where player context is interesting (has player decisions)
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


def _persist_llm_call(
    services: SessionServices,
    state: GameState,
    *,
    actor_id: int,
    phase: Phase,
    prompt_key: str,
    result: LLMCallResult,
) -> None:
    if services.llm_settings is None:
        return
    insert_llm_call(
        services.conn,
        game_id=state["game_id"],
        player_id=actor_id,
        round_no=state["round"],
        phase=phase.value,
        model=services.llm_settings.model_id,
        tool_name=result.tool_name,
        prompt_key=prompt_key,
        request_json=result.request_payload,
        response_json=result.response_payload,
        latency_ms=result.latency_ms,
        retry_count=result.retry_count,
        fallback_level=0,
        success=result.success,
        error_message=result.error_message,
    )
    if services.llm_callback is not None and result.success:
        try:
            services.llm_callback(phase.value, actor_id, result.tool_name, result.tool_args, result.content)
        except Exception:
            pass
