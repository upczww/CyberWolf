"""Sheriff election handler."""
from __future__ import annotations

import logging
from random import Random
from typing import TYPE_CHECKING, TypeGuard

from app.domain.events import GameEvent
from app.domain.roles import EventType, Faction, Phase, Role
from app.domain.state import (
    GameState,
    PhaseResult,
    alive_player_ids,
)
from app.engine.event_helpers import emit_event, emit_speaking_started
from app.engine.llm_bridge import llm_decide, llm_speech, _build_cache_friendly_system_and_user
from app.engine.registry import phase
from app.services.context_builder import build_prompt_context
from app.services.decisions import resolve_action, validate_tool_call
from app.services.llm import TOOL_REGISTRY, build_phase_messages
from app.services.prompts import build_prompt_inputs

if TYPE_CHECKING:
    from app.engine.session import SessionServices

_log = logging.getLogger(__name__)


@phase(
    Phase.SHERIFF_ELECTION,
    narration=("gold", "第 {round} 天 · 警长竞选阶段开始"),
    requires_flag="sheriff_enabled",
)
async def handle_sheriff_election(state: GameState, services: SessionServices) -> PhaseResult:
    if state["round"] > 1 or state["sheriff_id"] is not None or not state["runtime"]["rule_flags"].get("sheriff_enabled", True):
        return PhaseResult(events=[], skip_phase=True)

    alive = alive_player_ids(state)
    events: list[GameEvent] = []
    actions = []

    # Phase 1: Declare candidacy
    living_wolves_list = [pid for pid in alive if state["players"][pid]["faction"] == Faction.WOLF]
    designated_wolf = services.rng.choice(living_wolves_list) if living_wolves_list else None

    # Phase 1 — collect candidacy decisions silently. No per-declarer
    # SHERIFF_DECLARE event; the aggregated SHERIFF_ELECTED below carries
    # the full candidates list so the frontend learns who ran for sheriff
    # only once the candidacy window has closed.
    candidates: list[int] = []
    for player_id in alive:
        if state["players"][player_id]["faction"] == Faction.WOLF:
            wants_to_run = player_id == designated_wolf
        else:
            wants_to_run = await _decide_candidacy(state, services, player_id)
        if wants_to_run:
            candidates.append(player_id)

    if not candidates:
        emit_event(services, state, events, EventType.SHERIFF_ELECTED,
                   {"player_id": None, "candidates": [], "votes": {}, "reason": "no candidates"})
        emit_event(services, state, events, EventType.NARRATION,
                   {"text": "无人参选 · 警徽流落", "kind": "info",
                    "round": state["round"], "phase": state["phase"].value})
        return PhaseResult(actions=actions, events=events, persisted_event_count=len(events))

    if len(candidates) == 1:
        sheriff_id = candidates[0]
        players_patch = {sheriff_id: {"is_sheriff": True}}
        emit_event(services, state, events, EventType.SHERIFF_ELECTED,
                   {"player_id": sheriff_id, "candidates": list(candidates),
                    "votes": {}, "unopposed": True})
        emit_event(services, state, events, EventType.NARRATION,
                   {"text": f"{sheriff_id} 号自动当选警长", "kind": "gold",
                    "round": state["round"], "phase": state["phase"].value})
        direction = await _sheriff_pick_direction(state, services, sheriff_id)
        emit_event(services, state, events, EventType.SHERIFF_DIRECTION,
                   {"player_id": sheriff_id, "clockwise": direction})
        return PhaseResult(
            state_patch={"sheriff_id": sheriff_id, "players": players_patch, "sheriff_speech_clockwise": direction},
            actions=actions, events=events, persisted_event_count=len(events),
        )

    # Phase 2: Campaign speeches
    speech_order = list(candidates)
    services.rng.shuffle(speech_order)
    for player_id in speech_order:
        role = state["players"][player_id]["role"]
        emit_speaking_started(services, state, events, player_id=player_id)
        proposed_args = await llm_speech(
            state, services,
            actor_id=player_id, role=role, phase=state["phase"],
            local_args={"public_speech": f"玩家{player_id}竞选警长", "internal_thought": ""},
        )
        speech = proposed_args.get("public_speech", "")
        if speech:
            emit_event(services, state, events, EventType.SHERIFF_CAMPAIGN,
                       {"player_id": player_id, "speech": speech})

    # Phase 3: Vote — only NON-candidates vote
    voters = [pid for pid in alive if pid not in candidates]
    votes: dict[int, int] = {}
    for voter in voters:
        voter_candidates = list(candidates)
        if not voter_candidates:
            votes[voter] = None
            continue
        proposed_args = await llm_decide(
            state, services,
            actor_id=voter, role=state["players"][voter]["role"],
            phase=state["phase"], tool_name="vote_target",
            # Carry the candidate list into the awaiter so the human's
            # frontend can constrain the vote UI to candidates only.
            local_args={
                "target_id": services.rng.choice(voter_candidates),
                "candidates": list(voter_candidates),
            },
            prompt_key_override="sheriff_vote.j2",
            decision_note=(
                "现在是警长竞选投票，不是竞选发言。"
                f"你必须从候选人 {voter_candidates} 中选择一人，把 target_id 设置为候选人的编号。"
                "不要输出普通文本，不要发表演讲。"
            ),
        )
        if proposed_args.get("_wolf_self_destruct"):
            from app.engine.handlers.skills import build_self_destruct_result
            result = build_self_destruct_result(state, voter)
            merged = dict(result)
            merged["events"] = events + result.get("events", [])
            merged["actions"] = actions + result.get("actions", [])
            merged["persisted_event_count"] = len(events)
            return PhaseResult(**merged)
        action = _validate_or_raise(
            state, services, actor_id=voter,
            role=state["players"][voter]["role"], phase=state["phase"],
            tool_name="vote_target", args=proposed_args,
        )
        actions.append(action)
        target = action["args"].get("target_id")
        if target not in candidates:
            target = services.rng.choice(candidates) if candidates else None
        votes[voter] = target

    # Phase 4: Tally with tie-breaking
    sheriff_id, votes = await _resolve_sheriff_election(
        state, services, votes, candidates, voters, events, actions,
    )
    if _is_phase_result(votes):
        return votes
    if sheriff_id is None:
        emit_event(services, state, events, EventType.SHERIFF_ELECTED,
                   {"player_id": None, "candidates": list(candidates),
                    "votes": votes, "tie": True})
        emit_event(services, state, events, EventType.NARRATION,
                   {"text": "警长竞选平票 · 警徽撕毁", "kind": "info",
                    "round": state["round"], "phase": state["phase"].value})
        return PhaseResult(actions=actions, events=events, persisted_event_count=len(events))

    players_patch = {sheriff_id: {"is_sheriff": True}}
    emit_event(services, state, events, EventType.SHERIFF_ELECTED,
               {"player_id": sheriff_id, "candidates": list(candidates), "votes": votes})
    emit_event(services, state, events, EventType.NARRATION,
               {"text": f"{sheriff_id} 号当选警长", "kind": "gold",
                "round": state["round"], "phase": state["phase"].value})

    direction = await _sheriff_pick_direction(state, services, sheriff_id)
    emit_event(services, state, events, EventType.SHERIFF_DIRECTION,
               {"player_id": sheriff_id, "clockwise": direction})

    return PhaseResult(
        state_patch={"sheriff_id": sheriff_id, "players": players_patch, "sheriff_speech_clockwise": direction},
        actions=actions, events=events, persisted_event_count=len(events),
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


async def _resolve_sheriff_election(
    state: GameState,
    services: "SessionServices",
    votes: dict[int, int],
    candidates: list[int],
    voters: list[int],
    events: list[GameEvent],
    actions: list,
) -> tuple[int | None, dict[int, int] | PhaseResult]:
    """Resolve with tie-breaking: extra speech + re-vote."""
    sheriff_id = _resolve_sheriff_vote(votes, services.rng, candidates=candidates)
    if sheriff_id is not None:
        return sheriff_id, votes

    # Tie — extra speech round
    tally: dict[int, int] = {}
    for target in votes.values():
        if target is not None and target in candidates:
            tally[target] = tally.get(target, 0) + 1
    if not tally:
        return None, votes
    top = max(tally.values())
    tied = sorted(pid for pid, count in tally.items() if count == top)

    for player_id in tied:
        role = state["players"][player_id]["role"]
        emit_speaking_started(services, state, events, player_id=player_id)
        proposed_args = await llm_speech(
            state, services,
            actor_id=player_id, role=role, phase=state["phase"],
            local_args={"public_speech": f"玩家{player_id}平票补充发言", "internal_thought": ""},
        )
        speech = proposed_args.get("public_speech", "")
        if speech:
            emit_event(services, state, events, EventType.SHERIFF_CAMPAIGN,
                       {"player_id": player_id, "speech": speech, "tie_breaker": True})

    # Re-vote among tied candidates
    new_votes: dict[int, int] = {}
    for voter in voters:
        voter_candidates = [pid for pid in tied if pid != voter] or list(tied)
        if not voter_candidates:
            new_votes[voter] = None
            continue
        proposed_args = await llm_decide(
            state, services,
            actor_id=voter, role=state["players"][voter]["role"],
            phase=state["phase"], tool_name="vote_target",
            local_args={
                "target_id": services.rng.choice(voter_candidates),
                "candidates": list(voter_candidates),
            },
            prompt_key_override="sheriff_vote.j2",
            decision_note=(
                "现在是警长平票后的再次投票，不是补充发言。"
                f"你必须从平票候选人 {voter_candidates} 中选择一人，把 target_id 设置为候选人的编号。"
                "不要输出普通文本，不要发表演讲。"
            ),
        )
        if proposed_args.get("_wolf_self_destruct"):
            from app.engine.handlers.skills import build_self_destruct_result
            result = build_self_destruct_result(state, voter)
            merged = dict(result)
            merged["events"] = events + result.get("events", [])
            merged["actions"] = actions + result.get("actions", [])
            merged["persisted_event_count"] = len(events)
            return None, PhaseResult(**merged)
        action = _validate_or_raise(
            state, services, actor_id=voter,
            role=state["players"][voter]["role"], phase=state["phase"],
            tool_name="vote_target", args=proposed_args,
        )
        actions.append(action)
        target = action["args"].get("target_id")
        if target not in tied:
            target = services.rng.choice(tied) if tied else None
        new_votes[voter] = target

    sheriff_id = _resolve_sheriff_vote(new_votes, services.rng, candidates=tied)
    if sheriff_id is not None:
        return sheriff_id, new_votes
    return None, new_votes


def _resolve_sheriff_vote(votes: dict[int, int], rng: Random, *, candidates: list[int] | None = None) -> int | None:
    if not votes:
        return None
    tally: dict[int, int] = {}
    for target in votes.values():
        if target is None:
            continue
        if candidates is not None and target not in candidates:
            continue
        tally[target] = tally.get(target, 0) + 1
    if not tally:
        return None
    top = max(tally.values())
    tied = sorted(pid for pid, count in tally.items() if count == top)
    if len(tied) == 1:
        return tied[0]
    return rng.choice(tied)


async def _decide_candidacy(state: GameState, services: "SessionServices", player_id: int) -> bool:
    """Decide whether a player wants to run for sheriff."""
    role = state["players"][player_id]["role"]
    # Human seat gets to choose directly via the awaiter (separate tool name so
    # the frontend can show a dedicated yes/no UI without conflicting with the
    # later vote_target prompt).
    human_seats = state.get("human_seats") or set()
    is_human = player_id in human_seats or state.get("human_seat") == player_id
    if is_human and services.human_awaiter is not None:
        from app.engine.llm_bridge import _await_human_action
        result = await _await_human_action(
            state, services,
            actor_id=player_id, role=role, phase=state["phase"],
            tool_name="sheriff_candidacy", local_args={"target_id": None},
        )
        target = result.get("target_id")
        return target is not None and int(target) == player_id
    if services.llm_client is None or services.llm_settings is None:
        weights: dict[Role, float] = {
            Role.WOLF: 0.6, Role.SEER: 0.98, Role.WITCH: 0.3,
            Role.HUNTER: 0.65, Role.IDIOT: 0.08, Role.GUARD: 0.5, Role.VILLAGER: 0.05,
        }
        return services.rng.random() < weights.get(role, 0.5)

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

    from app.engine.llm_bridge import _call_llm, _persist_llm_call
    result = await _call_llm(services, messages, tools)
    _persist_llm_call(services, state, actor_id=player_id, phase=Phase.SHERIFF_ELECTION, prompt_key="sheriff_candidacy", result=result)

    if not result.success or result.tool_args is None:
        return False
    target_id = result.tool_args.get("target_id")
    return target_id is not None and int(target_id) == player_id


async def _sheriff_pick_direction(state: GameState, services: "SessionServices", sheriff_id: int) -> bool:
    """True=clockwise, False=counter-clockwise."""
    return services.rng.random() < 0.5


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
        human_seats = state.get("human_seats") or set()
        is_human = actor_id in human_seats or state.get("human_seat") == actor_id
        if services.llm_client is not None or is_human:
            _log.warning("invalid %s args for player %s in %s: %s – using fallback",
                         tool_name, actor_id, phase.value, errors)
            validated = validated.copy()
            validated["is_valid"] = True
            validated["validation_errors"] = []
            fallback_args = dict(args)
            if tool_name in {"wolf_kill_proposal", "seer_check", "vote_target", "hunter_shoot"}:
                candidates = [pid for pid in alive_player_ids(state) if pid != actor_id]
                fallback_args["target_id"] = services.rng.choice(candidates) if candidates else None
            validated["args"] = fallback_args
        else:
            raise RuntimeError(f"invalid {tool_name} args for player {actor_id}: {errors}")
    return resolve_action(validated)


def _is_phase_result(value: object) -> TypeGuard[PhaseResult]:
    if not isinstance(value, dict):
        return False
    return any(key in value for key in ("state_patch", "events", "persisted_event_count", "next_phase_override"))
