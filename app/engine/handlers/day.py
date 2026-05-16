"""Day phase handlers: announce, speech, vote, resolve."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from app.domain.events import GameEvent
from app.domain.roles import EventType, Role
from app.domain.state import (
    GameState,
    PendingSkill,
    PhaseResult,
    alive_player_ids,
)
from app.engine.event_helpers import action_source as _action_source, emit_event, emit_speaking_started, make_event
from app.engine.llm_bridge import llm_decide, llm_speech
from app.services.decisions import resolve_action, validate_tool_call

if TYPE_CHECKING:
    from app.engine.session import SessionServices

_log = logging.getLogger(__name__)
TZ_CN = timezone(timedelta(hours=8))


def handle_day_announce(state: GameState, services: SessionServices) -> PhaseResult:
    deaths = state["night_result"].get("deaths", [])
    return PhaseResult(
        events=[
            make_event(state, EventType.PHASE_STARTED, {"deaths": deaths}, content="event.day_announce")
        ]
    )


async def handle_day_speech(state: GameState, services: SessionServices) -> PhaseResult:
    speeches = list(state["speech_log"])
    events: list[GameEvent] = []
    order = _determine_speech_order(state)
    actions = []

    # Announce speech order
    emit_event(services, state, events, EventType.SPEECH_ORDER_ANNOUNCED,
               {"order": order, "sheriff_id": state.get("sheriff_id")})

    for player_id in order:
        role = state["players"][player_id]["role"]
        emit_speaking_started(services, state, events, player_id=player_id)
        proposed_args = await llm_speech(
            state, services,
            actor_id=player_id, role=role, phase=state["phase"],
            local_args={
                "public_speech": f"player {player_id} ({role.value}) gives a short public speech",
                "internal_thought": "",
            },
        )
        # Wolf self-destruct check
        if proposed_args.get("_wolf_self_destruct"):
            from app.engine.handlers.skills import build_self_destruct_result
            result = build_self_destruct_result(state, player_id)
            merged = dict(result)
            merged["events"] = events + result.get("events", [])
            merged["persisted_event_count"] = len(events)
            return PhaseResult(**merged)

        proposed = {
            "actor_id": player_id, "phase": state["phase"],
            "tool_name": "public_speech", "raw_args": proposed_args,
            "source": _action_source(services, state["phase"]),
        }
        validated = validate_tool_call(
            state=state, runtime=state["runtime"],
            actor_id=player_id, role=role, phase=state["phase"],
            proposed=proposed,
        )
        if not validated["is_valid"]:
            _log.warning("invalid public_speech for player %s in %s: %s – using fallback",
                         player_id, state["phase"].value, validated.get("validation_errors", []))
            proposed["raw_args"] = {
                "public_speech": f"player {player_id} ({role.value}) gives a short public speech",
                "internal_thought": "",
            }
            validated = validate_tool_call(
                state=state, runtime=state["runtime"],
                actor_id=player_id, role=role, phase=state["phase"],
                proposed=proposed,
            )
        action = resolve_action(validated)
        actions.append(action)
        content = action["args"]["public_speech"]
        speeches.append({"player_id": player_id, "round": state["round"], "content": content})
        emit_event(services, state, events, EventType.PUBLIC_SPEECH_MADE,
                   {"player_id": player_id, "speech": content})

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
        actions=actions, events=events, persisted_event_count=len(events),
    )


async def handle_day_vote(state: GameState, services: SessionServices) -> PhaseResult:
    voters = [pid for pid, player in state["players"].items() if player["alive"] and player["can_vote"]]
    votes: dict[int, int | None] = {}
    actions = []
    events: list[GameEvent] = []

    for voter in voters:
        candidates = [pid for pid in alive_player_ids(state) if pid != voter]
        if not candidates:
            votes[voter] = None
            continue
        proposed_args = await llm_decide(
            state, services,
            actor_id=voter, role=state["players"][voter]["role"],
            phase=state["phase"], tool_name="vote_target",
            local_args={"target_id": services.rng.choice(candidates)},
        )
        if proposed_args.get("_wolf_self_destruct"):
            from app.engine.handlers.skills import build_self_destruct_result
            result = build_self_destruct_result(state, voter)
            merged = dict(result)
            merged["events"] = events + result.get("events", [])
            merged["persisted_event_count"] = len(events)
            return PhaseResult(**merged)
        proposed = {
            "actor_id": voter, "phase": state["phase"],
            "tool_name": "vote_target", "raw_args": proposed_args,
            "source": _action_source(services, state["phase"]),
        }
        validated = validate_tool_call(
            state=state, runtime=state["runtime"],
            actor_id=voter, role=state["players"][voter]["role"],
            phase=state["phase"], proposed=proposed,
        )
        if not validated["is_valid"]:
            _log.warning("invalid vote_target for player %s: %s – abstaining",
                         voter, validated.get("validation_errors", []))
            votes[voter] = None
            continue
        action = resolve_action(validated)
        actions.append(action)
        target = action["args"]["target_id"]
        votes[voter] = target
        emit_event(services, state, events, EventType.VOTE_CAST,
                   {"voter_id": voter, "target_id": target})

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
            chosen = votes[sheriff_id]
        else:
            chosen = services.rng.choice(tied)
    emit_event(services, state, events, EventType.VOTE_RESOLVED,
               {"votes": votes, "chosen": chosen})
    return PhaseResult(
        state_patch={"vote_records": votes, "vote_candidates": [chosen] if chosen is not None else []},
        actions=actions, events=events, persisted_event_count=len(events),
    )


async def handle_day_resolve(state: GameState, services: SessionServices) -> PhaseResult:
    if not state["vote_candidates"]:
        return PhaseResult(state_patch={"round": state["round"] + 1, "day_index": state["day_index"] + 1}, events=[])
    target = state["vote_candidates"][0]
    player = state["players"][target]
    events: list[GameEvent] = []
    players_patch: dict[int, dict] = {}
    dead_history = list(state["dead_history"])
    pending: list[PendingSkill] = list(state["pending_skills"])

    if player["role"] == Role.IDIOT and not player["idiot_revealed"] and state["runtime"]["rule_flags"].get("idiot_survives_exile", False):
        players_patch[target] = {"idiot_revealed": True, "can_vote": False}
        emit_event(services, state, events, EventType.SKILL_TRIGGERED,
                   {"actor_id": target, "skill": "idiot_reveal"},
                   content="event.idiot_revealed")
    else:
        players_patch[target] = {"alive": False, "death_round": state["round"], "death_cause": "exile", "is_sheriff": False}
        dead_history.append({"player_id": target, "cause": "exile", "round": state["round"]})
        emit_event(services, state, events, EventType.PLAYER_DIED,
                   {"player_id": target, "cause": "exile"})
        from app.engine.handlers.night import _queue_death_skills
        _queue_death_skills(state, pending, target, "exile")

        # Death speech for exiled player
        from app.engine.handlers.night import _collect_death_speeches
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
        events=events, persisted_event_count=len(events),
    )


# ---------------------------------------------------------------------------
# Speech order logic
# ---------------------------------------------------------------------------


def _determine_speech_order(state: GameState) -> list[int]:
    """Determine speech order based on werewolf rules."""
    alive = alive_player_ids(state)
    if len(alive) <= 1:
        return alive

    sheriff_id = state.get("sheriff_id")
    day_index = state.get("day_index", 1)
    night_deaths = state.get("night_result", {}).get("deaths", [])

    if sheriff_id is not None and sheriff_id in state["players"]:
        if day_index <= 1 and state.get("sheriff_speech_clockwise") is not None:
            clockwise = state["sheriff_speech_clockwise"]
        else:
            clockwise = day_index % 2 == 1
        ordered = _build_ring_order(alive, start_ref=sheriff_id, clockwise=clockwise, speak_last=sheriff_id)
    else:
        if night_deaths:
            start_ref = night_deaths[0]
        else:
            now = datetime.now(TZ_CN)
            minute = now.minute
            digit_sum = (minute // 10) + (minute % 10)
            total = len(alive)
            start_idx = digit_sum % total
            start_ref = alive[start_idx]
        clockwise = datetime.now().minute % 2 == 1
        ordered = _build_ring_order(alive, start_ref=start_ref, clockwise=clockwise, speak_last=None)

    return ordered


def _build_ring_order(
    alive: list[int], *, start_ref: int, clockwise: bool, speak_last: int | None,
) -> list[int]:
    """Build a ring order from alive players starting next to start_ref."""
    sorted_alive = sorted(alive)
    n = len(sorted_alive)

    if start_ref not in sorted_alive:
        start_idx = 0
        for i, pid in enumerate(sorted_alive):
            if pid > start_ref:
                start_idx = i
                break
    else:
        start_idx = sorted_alive.index(start_ref)

    result = []
    for offset in range(1, n + 1):
        if clockwise:
            idx = (start_idx + offset) % n
        else:
            idx = (start_idx - offset) % n
        pid = sorted_alive[idx]
        if pid == speak_last:
            continue
        result.append(pid)

    if speak_last is not None and speak_last in sorted_alive:
        result.append(speak_last)
    return result


