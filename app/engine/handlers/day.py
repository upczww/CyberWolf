"""Day phase handlers: announce, speech, vote, resolve."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from time import monotonic
from typing import TYPE_CHECKING

from app.domain.events import GameEvent
from app.domain.roles import EventType, Role
from app.domain.state import (
    GameState,
    PendingSkill,
    PhaseResult,
    alive_player_ids,
    apply_state_patch,
)
from app.engine.event_helpers import action_source as _action_source, emit_event, emit_narration, emit_speaking_started, make_event
from app.engine.llm_bridge import llm_decide, llm_speech
from app.engine.pacing import hold_visible_action, phase_has_time, set_phase_deadline
from app.engine.registry import phase
from app.services.decisions import resolve_action, validate_tool_call

from app.domain.roles import Phase as _PhaseEnum

if TYPE_CHECKING:
    from app.engine.session import SessionServices

_log = logging.getLogger(__name__)
TZ_CN = timezone(timedelta(hours=8))


@phase(_PhaseEnum.DAY_ANNOUNCE)
# day_announce intentionally has no static narration in PhaseSpec — the
# handler emits a dynamic intro narration ("天亮了 · 第N天, ...") with
# actual dawn content via emit_narration(intro=True).
async def handle_day_announce(state: GameState, services: SessionServices) -> PhaseResult:
    deaths = state["night_result"].get("deaths", [])
    events: list[GameEvent] = []
    # Public dawn announcement — village learns WHO died, not how.
    # Marked as `intro=True` so the frontend pins it as the big
    # PhaseFlash banner for the day_announce phase ("天亮了，..."), not
    # a small ticker line buried in the corner.
    if not deaths:
        emit_narration(
            services, state, events,
            f"天亮了 · 第 {state['round']} 天，昨晚是平安夜，无人出局",
            kind="good", glyph="☀", intro=True,
        )
    else:
        names = "、".join(f"{pid} 号" for pid in deaths)
        emit_narration(
            services, state, events,
            f"天亮了 · 第 {state['round']} 天，{names} 死亡",
            kind="wolf", glyph="☀", intro=True,
        )
        # Then collect last words from each fallen seat (per-player
        # narration banner + 90s death_speech awaiter). Standard rule
        # gates these to round 1 — _collect_death_speeches enforces.
        from app.engine.handlers.night import _collect_death_speeches
        # Pull causes for any of these seats from dead_history (most
        # recent record per pid wins). We don't expose cause in the
        # awaiter prompt — this is just metadata for downstream tools.
        cause_by_pid: dict[int, str] = {}
        for entry in reversed(state.get("dead_history", [])):
            pid = int(entry.get("player_id", -1))
            if pid in deaths and pid not in cause_by_pid:
                cause_by_pid[pid] = str(entry.get("cause", ""))
        speech_events = await _collect_death_speeches(
            state, services, list(deaths), death_causes=cause_by_pid,
        )
        events.extend(speech_events)
    return PhaseResult(events=events, persisted_event_count=len(events))


@phase(_PhaseEnum.DAY_SPEECH, narration=("info", "第 {round} 天 · 进入发言阶段"))
async def handle_day_speech(state: GameState, services: SessionServices) -> PhaseResult:
    speeches = list(state["speech_log"])
    events: list[GameEvent] = []
    actions: list = []

    # Sheriff (if alive) picks today's speech direction. Human sheriff
    # gets an awaiter; AI sheriff uses the alternating heuristic via
    # _determine_speech_order (which we call after we stash the choice).
    sheriff_id = state.get("sheriff_id")
    sheriff_alive = sheriff_id is not None and state["players"].get(sheriff_id, {}).get("alive", False)
    direction_clockwise: bool | None = None
    if sheriff_alive:
        human_seats = state.get("human_seats") or set()
        is_human_sheriff = sheriff_id in human_seats or state.get("human_seat") == sheriff_id
        if is_human_sheriff:
            # Default = alternate (same as the AI heuristic) so a timed-
            # out sheriff still produces a sensible order.
            day_index = state.get("day_index", 1)
            default_clockwise = day_index % 2 == 1
            decided = await llm_decide(
                state, services,
                actor_id=sheriff_id, role=state["players"][sheriff_id]["role"],
                phase=state["phase"], tool_name="sheriff_pick_direction",
                local_args={"clockwise": default_clockwise},
            )
            direction_clockwise = bool(decided.get("clockwise", default_clockwise))
        else:
            # AI sheriff just alternates each day for simplicity.
            day_index = state.get("day_index", 1)
            direction_clockwise = day_index % 2 == 1
        # Stash on state so _determine_speech_order picks it up.
        state = apply_state_patch(state, {"sheriff_speech_clockwise": direction_clockwise})
        emit_event(services, state, events, EventType.SHERIFF_DIRECTION,
                   {"player_id": sheriff_id, "clockwise": direction_clockwise})
        emit_event(services, state, events, EventType.NARRATION,
                   {"text": f"警长指定本日发言方向：{'顺时针（警左起）' if direction_clockwise else '逆时针（警右起）'}",
                    "kind": "gold",
                    "round": state["round"], "phase": state["phase"].value})

    order = _determine_speech_order(state)

    # Announce speech order
    emit_event(services, state, events, EventType.SPEECH_ORDER_ANNOUNCED,
               {"order": order, "sheriff_id": state.get("sheriff_id"),
                "clockwise": direction_clockwise})

    # Re-arm the phase ceiling to fit every speaker's full turn (90s
    # speech cap + buffer) so no one is truncated in a human game. AI
    # speakers finish in seconds, so this never slows an AI round.
    set_phase_deadline(services, 20.0 + len(order) * 95.0)

    for player_id in order:
        if not phase_has_time(services):
            break
        visible_started = monotonic()
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
        await hold_visible_action(visible_started, services)

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


@phase(_PhaseEnum.DAY_VOTE, narration=("info", "投票放逐 · 请投出你的一票"))
async def handle_day_vote(state: GameState, services: SessionServices) -> PhaseResult:
    """Day vote with tie-break PK per standard 12-人 ruleset.

    Round 1: every alive voter picks one alive non-self target.
    Tally (sheriff weight 1.5×). If one clear winner → exile them.

    If tied: the tied seats give a PK speech (extra public_speech each),
    then round 2 — only NON-tied voters re-vote among the tied targets.
    If round 2 still ties, no one is exiled.
    """
    events: list[GameEvent] = []
    actions: list = []
    sheriff_id = state.get("sheriff_id")
    voters = [pid for pid, player in state["players"].items() if player["alive"] and player["can_vote"]]

    # Re-arm the ceiling to fit every voter's full turn (120s vote cap +
    # buffer). Ceiling only — AI voters resolve instantly.
    set_phase_deadline(services, 20.0 + len(voters) * 130.0)

    # --- Round 1 ---
    votes, sd_result = await _collect_day_votes(
        state, services, voters,
        candidates=alive_player_ids(state),
        events=events, actions=actions,
    )
    if sd_result is not None:
        return sd_result

    tally = _weighted_tally(votes, sheriff_id=sheriff_id)
    chosen, tied = _resolve_winner(tally)
    went_to_pk = False

    if chosen is None and len(tied) >= 2:
        went_to_pk = True
        # Re-arm for the PK round: each tied seat re-speaks (95s) + the
        # non-tied voters re-vote (130s each). Fresh ceiling so the
        # round-1 budget already spent doesn't starve the PK.
        revote_count = len([v for v in voters if v not in tied])
        set_phase_deadline(services, 20.0 + len(tied) * 95.0 + revote_count * 130.0)
        # Tied — PK round. Announce + each tied seat speaks again, then
        # voters who weren't tied re-vote among the tied seats only.
        emit_event(services, state, events, EventType.NARRATION,
                   {"text": f"投票平票 · {', '.join(f'{pid} 号' for pid in tied)} 进入加赛 PK",
                    "kind": "info", "round": state["round"], "phase": state["phase"].value})

        # PK speeches
        from app.engine.llm_bridge import llm_speech
        for pid in tied:
            visible_started = monotonic()
            role = state["players"][pid]["role"]
            emit_speaking_started(services, state, events, player_id=pid)
            speech_args = await llm_speech(
                state, services,
                actor_id=pid, role=role, phase=state["phase"],
                local_args={"public_speech": f"玩家{pid}平票补充发言", "internal_thought": ""},
            )
            speech = speech_args.get("public_speech", "")
            if speech:
                emit_event(services, state, events, EventType.PUBLIC_SPEECH_MADE,
                           {"player_id": pid, "speech": speech, "tie_breaker": True})
            # Same visible-hold as the normal speech loop so AI PK
            # speeches don't flash past faster than a human can read.
            await hold_visible_action(visible_started, services)

        # Round 2 — only non-tied alive voters; pick among tied seats.
        revote_voters = [v for v in voters if v not in tied]
        emit_event(services, state, events, EventType.NARRATION,
                   {"text": "PK 后再次投票 · 仅未在台上的玩家可投",
                    "kind": "info", "round": state["round"], "phase": state["phase"].value})
        round2_votes, sd_result = await _collect_day_votes(
            state, services, revote_voters,
            candidates=tied,
            events=events, actions=actions,
            tie_breaker=True,
        )
        if sd_result is not None:
            return sd_result

        # Merge into the votes dict for record (round-1 + round-2). The
        # final VOTE_RESOLVED carries round-2 votes since that decides
        # the outcome; round-1 lives in state.vote_records.
        round2_tally = _weighted_tally(round2_votes, sheriff_id=sheriff_id)
        chosen2, tied2 = _resolve_winner(round2_tally)
        votes = round2_votes  # decisive round for the emit
        if chosen2 is not None:
            chosen = chosen2
        else:
            # Still tied — no exile this day.
            chosen = None

    emit_event(services, state, events, EventType.VOTE_RESOLVED,
               {"votes": votes, "chosen": chosen})
    if chosen is None and went_to_pk:
        narration_text = "PK 后再次平票 · 无人被放逐"
    elif chosen is None:
        narration_text = "投票平票 · 无人被放逐"
    else:
        narration_text = f"投票结束 · {chosen} 号被放逐"
    emit_event(services, state, events, EventType.NARRATION,
               {"text": narration_text,
                "kind": "wolf" if chosen is not None else "info",
                "round": state["round"], "phase": state["phase"].value})
    return PhaseResult(
        state_patch={"vote_records": votes, "vote_candidates": [chosen] if chosen is not None else []},
        actions=actions, events=events, persisted_event_count=len(events),
    )


async def _collect_day_votes(
    state: GameState,
    services: SessionServices,
    voters: list[int],
    *,
    candidates: list[int],
    events: list[GameEvent],
    actions: list,
    tie_breaker: bool = False,
) -> tuple[dict[int, int | None], PhaseResult | None]:
    """Run one round of day-vote collection.

    Returns (votes_dict, None) on success. If a wolf self-destructed
    mid-round, returns ({}, PhaseResult) so the caller can short-
    circuit. The candidate list is the universe each voter can pick
    from (and must not be self); pass alive_player_ids(state) for the
    first round, or the tied-seat list for the PK re-vote.
    """
    votes: dict[int, int | None] = {}
    for voter in voters:
        pick_from = [c for c in candidates if c != voter]
        if not pick_from:
            votes[voter] = None
            continue
        local_args: dict = {"target_id": services.rng.choice(pick_from)}
        if tie_breaker:
            # Surface the tied seat list to the human's vote panel so the
            # candidates grid stays constrained to PK contestants.
            local_args["candidates"] = list(pick_from)
        if not phase_has_time(services):
            votes[voter] = local_args["target_id"]
            continue
        proposed_args = await llm_decide(
            state, services,
            actor_id=voter, role=state["players"][voter]["role"],
            phase=state["phase"], tool_name="vote_target",
            local_args=local_args,
        )
        if proposed_args.get("_wolf_self_destruct"):
            from app.engine.handlers.skills import build_self_destruct_result
            result = build_self_destruct_result(state, voter)
            merged = dict(result)
            merged["events"] = list(events) + result.get("events", [])
            merged["persisted_event_count"] = len(events)
            return {}, PhaseResult(**merged)
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
        target = action["args"].get("target_id")
        # If the human picked a non-candidate (shouldn't happen since we
        # constrain via local_args.candidates), coerce to a valid pick.
        if target not in pick_from:
            target = services.rng.choice(pick_from)
        votes[voter] = target
    return votes, None


def _weighted_tally(votes: dict[int, int | None], *, sheriff_id: int | None) -> dict[int, float]:
    tally: dict[int, float] = {}
    for voter_id, target in votes.items():
        if target is None:
            continue
        weight = 1.5 if voter_id == sheriff_id else 1.0
        tally[target] = tally.get(target, 0) + weight
    return tally


def _resolve_winner(tally: dict[int, float]) -> tuple[int | None, list[int]]:
    """Pick the single winner of a vote, or return the tied set."""
    if not tally:
        return None, []
    top = max(tally.values())
    tied = sorted([pid for pid, score in tally.items() if score == top])
    if len(tied) == 1:
        return tied[0], tied
    return None, tied


@phase(_PhaseEnum.DAY_RESOLVE, narration=("info", "裁判结算白天投票"))
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


