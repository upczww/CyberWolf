"""Pending skills, check_win, game_over, and self-destruct handlers."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.domain.events import GameEvent
from app.domain.roles import EventType, GameStatus, Phase
from app.domain.state import (
    GameState,
    PhaseResult,
    alive_player_ids,
    apply_state_patch,
)
from app.engine.event_helpers import emit_event, make_event
from app.engine.llm_bridge import llm_decide
from app.engine.rules import check_win
from app.services.decisions import resolve_action, validate_tool_call

if TYPE_CHECKING:
    from app.engine.session import SessionServices

_log = logging.getLogger(__name__)


async def handle_pending_skills(state: GameState, services: SessionServices) -> PhaseResult:
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
            proposed_args = await llm_decide(
                state, services,
                actor_id=actor_id, role=state["players"][actor_id]["role"],
                phase=state["phase"], tool_name="hunter_shoot",
                local_args={"target_id": services.rng.choice(candidates)},
                prompt_key_override="hunter_shoot.j2",
            )
            action = _validate_or_raise(
                state, services,
                actor_id=actor_id, role=state["players"][actor_id]["role"],
                phase=state["phase"], tool_name="hunter_shoot",
                args=proposed_args,
            )
            target = action["args"]["target_id"]
            if target is None:
                continue  # Hunter chose not to shoot (shouldn't happen, but guard)
            players_patch[target] = {"alive": False, "death_round": state["round"], "death_cause": "hunter_shot"}
            dead_history.append({"player_id": target, "cause": "hunter_shot", "round": state["round"]})
            emit_event(services, state, events, EventType.PLAYER_DIED,
                       {"player_id": target, "cause": "hunter_shot"})
            emit_event(services, state, events, EventType.SKILL_TRIGGERED,
                       {"actor_id": actor_id, "target_id": target},
                       content="event.hunter_shot")
            # Queue death skills for the hunted target (e.g. sheriff transfer)
            from app.engine.handlers.night import _queue_death_skills
            _queue_death_skills(state, pending, target, "hunter_shot")

        elif skill["kind"] == "sheriff_transfer":
            actor_id = skill["actor_id"]
            candidates = [pid for pid in alive_player_ids(state) if pid != actor_id and pid not in players_patch]
            proposed_args = await llm_decide(
                state, services,
                actor_id=actor_id, role=state["players"][actor_id]["role"],
                phase=state["phase"], tool_name="sheriff_transfer",
                local_args={"target_id": services.rng.choice(candidates) if candidates else None},
                prompt_key_override="sheriff_transfer.j2",
            )
            action = _validate_or_raise(
                state, services,
                actor_id=actor_id, role=state["players"][actor_id]["role"],
                phase=state["phase"], tool_name="sheriff_transfer",
                args=proposed_args,
            )
            new_sheriff = action["args"]["target_id"]
            # Validate new sheriff is not already dead in this batch
            if new_sheriff is not None and new_sheriff in players_patch and not players_patch[new_sheriff].get("alive", True):
                new_sheriff = None  # Can't transfer to dead player
            if new_sheriff is not None:
                players_patch[new_sheriff] = {**players_patch.get(new_sheriff, {}), "is_sheriff": True}
            emit_event(services, state, events, EventType.SHERIFF_TRANSFERRED,
                       {"actor_id": actor_id, "target_id": new_sheriff})
            # Update sheriff_id in state patch but continue processing remaining skills
            state = apply_state_patch(state, {"sheriff_id": new_sheriff})

    return PhaseResult(
        state_patch={"players": players_patch, "dead_history": dead_history, "pending_skills": pending, "sheriff_id": state.get("sheriff_id")},
        events=events, persisted_event_count=len(events), next_phase_override=Phase.CHECK_WIN,
    )


def handle_check_win(state: GameState, services: SessionServices) -> PhaseResult:
    winner, reason = check_win(state, state["runtime"])
    if winner is not None:
        return PhaseResult(
            state_patch={"winner": winner, "ended": True, "status": GameStatus.COMPLETED},
            next_phase_override=Phase.GAME_OVER,
            events=[make_event(state, EventType.GAME_ENDED, {"winner": winner, "reason": reason})],
        )
    if state["phase_index"] + 1 < len(state["runtime"]["phase_order"]) and state["runtime"]["phase_order"][state["phase_index"] + 1] == Phase.GAME_OVER:
        return PhaseResult(next_phase_override=Phase.NIGHT_START)
    return PhaseResult(events=[])


def handle_game_over(state: GameState, services: SessionServices) -> PhaseResult:
    return PhaseResult(state_patch={"ended": True, "status": GameStatus.COMPLETED})


def build_self_destruct_result(state: GameState, wolf_id: int) -> PhaseResult:
    """Build PhaseResult for a wolf self-destructing during a day phase."""
    current_phase = state["phase"]
    events: list[GameEvent] = []
    players_patch: dict[int, dict] = {
        wolf_id: {"alive": False, "death_round": state["round"], "death_cause": "self_destruct", "is_sheriff": False},
    }
    state_patch: dict = {"players": players_patch}

    dead_history = list(state["dead_history"])
    dead_history.append({"player_id": wolf_id, "cause": "self_destruct", "round": state["round"]})
    state_patch["dead_history"] = dead_history

    if current_phase == Phase.SHERIFF_ELECTION:
        state_patch["sheriff_id"] = None
    if state["players"][wolf_id]["is_sheriff"]:
        state_patch["sheriff_id"] = None

    # Queue death skills (e.g. sheriff transfer if wolf was sheriff)
    pending = list(state["pending_skills"])
    from app.engine.handlers.night import _queue_death_skills
    _queue_death_skills(state, pending, wolf_id, "self_destruct")
    state_patch["pending_skills"] = pending

    events.append(make_event(state, EventType.WOLF_SELF_DESTRUCT, {"player_id": wolf_id}))

    state_patch["round"] = state["round"] + 1
    state_patch["day_index"] = state["day_index"] + 1

    return PhaseResult(
        state_patch=state_patch, events=events,
        next_phase_override=Phase.PENDING_SKILLS,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _validate_or_raise(state, services, *, actor_id, role, phase, tool_name, args):
    from app.engine.handlers.night import _action_source
    proposed = {
        "actor_id": actor_id, "phase": phase,
        "tool_name": tool_name, "raw_args": args,
        "source": _action_source(services, phase),
    }
    validated = validate_tool_call(
        state=state, runtime=state["runtime"],
        actor_id=actor_id, role=role, phase=phase,
        proposed=proposed,
    )
    if not validated["is_valid"]:
        errors = validated.get("validation_errors", [])
        if services.llm_client is not None:
            _log.warning("invalid %s args for player %s in %s: %s – using fallback",
                         tool_name, actor_id, phase.value, errors)
            validated = validated.copy()
            validated["is_valid"] = True
            validated["validation_errors"] = []
            fallback_args = dict(args)
            if tool_name in {"wolf_kill_proposal", "seer_check", "vote_target", "hunter_shoot"}:
                candidates = [pid for pid in alive_player_ids(state) if pid != actor_id]
                fallback_args["target_id"] = candidates[0] if candidates else None
            validated["args"] = fallback_args
        else:
            raise RuntimeError(f"invalid {tool_name} args for player {actor_id}: {errors}")
    # Final guard: ensure target_id is valid for target-based tools
    action = resolve_action(validated)
    if tool_name in {"wolf_kill_proposal", "seer_check", "vote_target", "hunter_shoot", "sheriff_transfer"}:
        target = action["args"].get("target_id")
        if target is not None and target not in state["players"]:
            candidates = [pid for pid in alive_player_ids(state) if pid != actor_id]
            action["args"]["target_id"] = candidates[0] if candidates else None
    return action
