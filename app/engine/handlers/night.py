"""Night phase handlers: wolf, seer, witch, resolve."""
from __future__ import annotations

import asyncio as _asyncio
import logging
from time import monotonic as _monotonic
from typing import TYPE_CHECKING

from app.domain.events import GameEvent
from app.domain.roles import EventScope, EventType, Phase, Role
from app.domain.state import (
    GameState,
    PendingSkill,
    PhaseResult,
    alive_player_ids,
    living_wolves,
)
from app.engine.event_helpers import action_source, emit_event, emit_speaking_started
from app.engine.llm_bridge import llm_death_speech, llm_decide
from app.engine.registry import phase
from app.services.decisions import resolve_action, validate_tool_call

if TYPE_CHECKING:
    from app.engine.session import SessionServices

_log = logging.getLogger(__name__)

# Every night role phase (wolf / seer / witch / guard) sits inside a
# 15..30s window so the village reads each role being summoned and
# silenced at a consistent cadence — dead-role phases still tick the
# same beat so observers can't infer who's out from timing.
NIGHT_PHASE_MIN_SECONDS = 15.0
NIGHT_PHASE_MAX_SECONDS = 30.0


async def _hold_night_phase(start_time: float) -> None:
    """Sleep up to NIGHT_PHASE_MIN_SECONDS so the phase rhythm is
    consistent. Human awaiter timeouts are capped at MAX_SECONDS in
    llm_bridge — this only handles the lower bound."""
    elapsed = _monotonic() - start_time
    if elapsed < NIGHT_PHASE_MIN_SECONDS:
        await _asyncio.sleep(NIGHT_PHASE_MIN_SECONDS - elapsed)


@phase(Phase.NIGHT_START, narration=("info", "第 {round} 夜 · 天黑请闭眼"))
def handle_night_start(state: GameState, services: SessionServices) -> PhaseResult:
    # Pacing (天黑请闭眼 holds for 5s before night_wolf) is enforced
    # generically by the session loop via MIN_PHASE_NARRATION_HOLD_SECONDS.
    return PhaseResult(
        state_patch={"night_actions": {}, "night_result": {}, "vote_records": {}, "vote_candidates": []},
        events=[],
    )


@phase(
    Phase.NIGHT_WOLF,
    narration=("wolf", "狼人请睁眼 · 互相确认同伴，商议今晚的击杀目标"),
    requires_role=Role.WOLF,
)
async def handle_night_wolf(state: GameState, services: SessionServices) -> PhaseResult:
    # Fire phase_started + "狼人请睁眼" narration BEFORE any LLM / awaiter
    # blocking, so the banner is visible to every player the moment this
    # phase begins (not deferred until the first emit_event).
    from app.engine.session import _ensure_phase_started
    _ensure_phase_started(services, state, services.conn, state["phase"], state["round"])
    phase_start = _monotonic()

    wolves = living_wolves(state)
    targets = [pid for pid in alive_player_ids(state) if pid not in wolves]
    if not wolves or not targets:
        # Even with no wolves alive, hold the phase 15s so the village
        # can't infer "all wolves dead" from a missing role-call beat.
        await _hold_night_phase(phase_start)
        return PhaseResult(state_patch={"night_actions": {"wolf_votes": {}, "wolf_target": None}}, events=[])

    # If any wolf is human-controlled, they pick the target by default
    # (rather than letting a seat-order accident hand it to an AI wolf).
    # The human's panel offers a "让 AI 决定" delegation button — if they
    # use it, the awaiter returns __delegate_to_ai__ and we re-decide
    # below as if the lead wolf were AI.
    human_seats = state.get("human_seats") or set()
    human_wolves = [w for w in wolves if w in human_seats]
    lead_wolf = human_wolves[0] if human_wolves else wolves[0]
    events: list[GameEvent] = []
    fallback_target = services.rng.choice(targets)
    proposed_target = await llm_decide(
        state, services,
        actor_id=lead_wolf,
        role=Role.WOLF,
        phase=state["phase"],
        tool_name="wolf_kill_proposal",
        local_args={"target_id": fallback_target},
    )
    # Human delegated to AI — re-run the decision with bypass_human so
    # llm_decide skips the awaiter and uses the LLM (or local random).
    if isinstance(proposed_target, dict) and proposed_target.get("__delegate_to_ai__"):
        proposed_target = await llm_decide(
            state, services,
            actor_id=lead_wolf,
            role=Role.WOLF,
            phase=state["phase"],
            tool_name="wolf_kill_proposal",
            local_args={"target_id": fallback_target},
            bypass_human=True,
        )
    proposed = {
        "actor_id": lead_wolf,
        "phase": state["phase"],
        "tool_name": "wolf_kill_proposal",
        "raw_args": proposed_target,
        "source": _action_source(services, state["phase"]),
    }
    validated = validate_tool_call(
        state=state, runtime=state["runtime"],
        actor_id=lead_wolf, role=Role.WOLF, phase=state["phase"],
        proposed=proposed,
    )
    if not validated["is_valid"]:
        _log.warning(
            "invalid wolf_kill_proposal for player %s: %s – using random target",
            lead_wolf, validated.get("validation_errors", []),
        )
        selected = services.rng.choice(targets)
        votes = {lead_wolf: selected}
        emit_event(services, state, events, EventType.WOLF_TARGET_SELECTED,
                   {"votes": votes, "target_id": selected},
                   scope=EventScope.WOLF_TEAM, targets=set(wolves))
        await _hold_night_phase(phase_start)
        return PhaseResult(
            state_patch={"night_actions": {"wolf_votes": votes, "wolf_target": selected}},
            events=events, persisted_event_count=len(events),
        )

    action = resolve_action(validated)
    selected = action["args"]["target_id"]
    votes = {wolf_id: selected for wolf_id in wolves}
    emit_event(services, state, events, EventType.WOLF_TARGET_SELECTED,
               {"votes": votes, "target_id": selected},
               scope=EventScope.WOLF_TEAM, targets=set(wolves))
    await _hold_night_phase(phase_start)
    return PhaseResult(
        state_patch={"night_actions": {"wolf_votes": votes, "wolf_target": selected}},
        actions=[action], events=events, persisted_event_count=len(events),
    )


@phase(
    Phase.NIGHT_SEER,
    narration=("good", "预言家请睁眼 · 请选择查验目标"),
    requires_role=Role.SEER,
)
async def handle_night_seer(state: GameState, services: SessionServices) -> PhaseResult:
    from app.engine.session import _ensure_phase_started
    _ensure_phase_started(services, state, services.conn, state["phase"], state["round"])
    phase_start = _monotonic()

    seer_id = _find_alive_role(state, Role.SEER)
    if seer_id is None:
        # Seer is dead — go through the silence so the village can't infer.
        await _hold_night_phase(phase_start)
        return PhaseResult(events=[])
    checked = {entry["target_id"] for entry in state["seer_checks"]}
    candidates = [pid for pid in alive_player_ids(state) if pid != seer_id and pid not in checked]
    if not candidates:
        candidates = [pid for pid in alive_player_ids(state) if pid != seer_id]
    proposed_args = await llm_decide(
        state, services,
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
        state=state, runtime=state["runtime"],
        actor_id=seer_id, role=Role.SEER, phase=state["phase"],
        proposed=proposed,
    )
    if not validated["is_valid"]:
        _log.warning("invalid seer_check for player %s: %s – skipping", seer_id, validated.get("validation_errors", []))
        await _hold_night_phase(phase_start)
        return PhaseResult(events=[])
    action = resolve_action(validated)
    target = action["args"]["target_id"]
    result = "wolf" if state["players"][target]["role"] == Role.WOLF else "good"
    checks = list(state["seer_checks"]) + [{"target_id": target, "result": result, "round": state["round"]}]
    events: list[GameEvent] = []
    emit_event(services, state, events, EventType.SEER_CHECKED,
               {"target_id": target, "result": result},
               scope=EventScope.ROLE_PRIVATE, targets={seer_id})
    await _hold_night_phase(phase_start)
    return PhaseResult(
        state_patch={"seer_checks": checks},
        actions=[action], events=events, persisted_event_count=len(events),
    )


@phase(
    Phase.NIGHT_WITCH,
    narration=("good", "女巫请睁眼 · 是否使用解药救人或毒药杀人"),
    requires_role=Role.WITCH,
)
async def handle_night_witch(state: GameState, services: SessionServices) -> PhaseResult:
    # Fire "女巫请睁眼" narration BEFORE any LLM / awaiter — the witch's
    # antidote/poison choices can each take seconds, and we want the
    # village banner to appear the moment the phase starts.
    from app.engine.session import _ensure_phase_started
    _ensure_phase_started(services, state, services.conn, state["phase"], state["round"])
    phase_start = _monotonic()

    witch_id = _find_alive_role(state, Role.WITCH)
    wolf_target = state["night_actions"].get("wolf_target")
    if witch_id is None:
        # Witch dead — hold the silence so observers can't infer it.
        await _hold_night_phase(phase_start)
        return PhaseResult(events=[])

    actions = []
    witch_events: list[GameEvent] = []
    night_actions_patch = {**state["night_actions"]}

    # --- Decision 1: Antidote ---
    use_antidote = False
    if not state["witch_antidote_used"] and wolf_target is not None:
        can_save_self = state["round"] <= 1 and bool(state["runtime"]["rule_flags"].get("witch_can_self_save_first_night", False))
        # First night self-save is mandatory; otherwise 35% chance to save others
        if wolf_target == witch_id and can_save_self:
            local_args = {"use_antidote": True}
        else:
            local_use = wolf_target != witch_id or can_save_self
            local_args = {"use_antidote": local_use and services.rng.random() < 0.35}
        # Carry the night's kill target into local_args so the human witch
        # panel can render the real seat ("今晚的死亡目标是 N 号"). Without
        # this the UI fell back to "?" since the panel reads target_id off
        # request.local_args.
        local_args["target_id"] = wolf_target

        llm_args = await llm_decide(
            state, services,
            actor_id=witch_id, role=Role.WITCH, phase=state["phase"],
            tool_name="witch_antidote", local_args=local_args,
        )
        proposed = {
            "actor_id": witch_id, "phase": state["phase"],
            "tool_name": "witch_antidote", "raw_args": llm_args,
            "source": _action_source(services, state["phase"]),
        }
        validated = validate_tool_call(
            state=state, runtime=state["runtime"],
            actor_id=witch_id, role=Role.WITCH, phase=state["phase"],
            proposed=proposed,
        )
        if not validated["is_valid"]:
            _log.warning("invalid witch_antidote for player %s: %s – fallback to no antidote",
                         witch_id, validated.get("validation_errors", []))
            validated["args"] = {"use_antidote": False}
        action = resolve_action(validated)
        actions.append(action)
        use_antidote = bool(action["args"].get("use_antidote", False))

        if use_antidote:
            emit_event(services, state, witch_events, EventType.WITCH_USED_ANTIDOTE,
                       {"target_id": wolf_target, "player_id": witch_id},
                       scope=EventScope.ROLE_PRIVATE, targets={witch_id})

    night_actions_patch["witch_use_antidote"] = use_antidote

    # --- Decision 2: Poison ---
    poison_target = None
    if not state["witch_poison_used"] and not use_antidote:
        candidates = [pid for pid in alive_player_ids(state) if pid != witch_id]
        local_poison_target = services.rng.choice(candidates) if candidates and services.rng.random() < 0.15 else None

        llm_args = await llm_decide(
            state, services,
            actor_id=witch_id, role=Role.WITCH, phase=state["phase"],
            tool_name="witch_poison", local_args={"target_id": local_poison_target},
            prompt_key_override="witch_poison.j2",
        )
        proposed = {
            "actor_id": witch_id, "phase": state["phase"],
            "tool_name": "witch_poison", "raw_args": llm_args,
            "source": _action_source(services, state["phase"]),
        }
        validated = validate_tool_call(
            state=state, runtime=state["runtime"],
            actor_id=witch_id, role=Role.WITCH, phase=state["phase"],
            proposed=proposed,
        )
        if not validated["is_valid"]:
            _log.warning("invalid witch_poison for player %s: %s – fallback to no poison",
                         witch_id, validated.get("validation_errors", []))
            validated["args"] = {"target_id": None}
        action = resolve_action(validated)
        actions.append(action)
        poison_target = action["args"].get("target_id")

        if poison_target is not None:
            emit_event(services, state, witch_events, EventType.WITCH_USED_POISON,
                       {"target_id": poison_target, "player_id": witch_id},
                       scope=EventScope.ROLE_PRIVATE, targets={witch_id})

    night_actions_patch["witch_poison_target"] = poison_target

    patch = {
        "night_actions": night_actions_patch,
        "witch_antidote_used": state["witch_antidote_used"] or use_antidote,
        "witch_poison_used": state["witch_poison_used"] or (poison_target is not None),
    }
    await _hold_night_phase(phase_start)
    return PhaseResult(state_patch=patch, actions=actions, events=witch_events, persisted_event_count=len(witch_events))


@phase(
    Phase.NIGHT_HUNTER,
    narration=("good", "猎人请睁眼 · 确认你今晚的开枪状态"),
    requires_role=Role.HUNTER,
)
async def handle_night_hunter(state: GameState, services: SessionServices) -> PhaseResult:
    """Hunter's nightly ceremony — confirms shoot state, no action.

    Standard 12-人 script: the judge wakes the hunter every night and
    silently tells them their "shoot state" (poisoned by witch → can't
    shoot; otherwise → can shoot on death). The hunter does NOT actually
    fire at night — that only happens via pending_skills on death.

    This phase exists purely for rhythm: every role gets its slot so
    observers can't infer "hunter dead/alive" from a missing beat. AI
    plays no part. Human hunter sees the banner but no panel.

    Optional private narration to the human hunter telling them their
    shoot state (poisoned → 不能开枪; otherwise → 可以开枪) — leverages
    the fact that night_witch already ran and set witch_poison_target.
    """
    from app.engine.session import _ensure_phase_started
    _ensure_phase_started(services, state, services.conn, state["phase"], state["round"])
    phase_start = _monotonic()

    hunter_id = _find_alive_role(state, Role.HUNTER)
    if hunter_id is None:
        await _hold_night_phase(phase_start)
        return PhaseResult(events=[])

    # Private status hint to the hunter: tonight you {can|cannot} shoot
    # if you die. Poisoned → can't shoot (unless rule_flag allows).
    poison_target = state["night_actions"].get("witch_poison_target")
    can_shoot_if_poisoned = state["runtime"]["rule_flags"].get("hunter_can_shoot_if_poisoned", False)
    poisoned_tonight = poison_target == hunter_id and not can_shoot_if_poisoned
    events: list[GameEvent] = []
    emit_event(
        services, state, events, EventType.NARRATION,
        {
            "text": "你今晚不能开枪（被女巫毒杀时无法开枪）" if poisoned_tonight
                    else "你今晚可以开枪",
            "kind": "info",
            "round": state["round"],
            "phase": state["phase"].value,
        },
        scope=EventScope.ROLE_PRIVATE, targets={hunter_id},
    )
    await _hold_night_phase(phase_start)
    return PhaseResult(events=events, persisted_event_count=len(events))


@phase(
    Phase.NIGHT_IDIOT_REVEAL,
    narration=("good", "白痴请睁眼 · 确认你的身份"),
    requires_role=Role.IDIOT,
)
async def handle_night_idiot_reveal(state: GameState, services: SessionServices) -> PhaseResult:
    """First-night idiot wake-up ceremony.

    Standard script: judge wakes the idiot only on night 1 to confirm
    their role. No action — just a rhythm beat + private reminder of
    the idiot's ability so the human idiot knows they survive an exile.

    Skipped entirely on round >= 2 (no banner, no hold).
    """
    if state["round"] >= 2:
        return PhaseResult(skip_phase=True)

    from app.engine.session import _ensure_phase_started
    _ensure_phase_started(services, state, services.conn, state["phase"], state["round"])
    phase_start = _monotonic()

    idiot_id = _find_alive_role(state, Role.IDIOT)
    if idiot_id is None:
        # Idiot already dead before round 1 ends? Shouldn't happen on
        # night 1, but hold the rhythm anyway.
        await _hold_night_phase(phase_start)
        return PhaseResult(events=[])

    events: list[GameEvent] = []
    emit_event(
        services, state, events, EventType.NARRATION,
        {
            "text": "你的身份是白痴 · 白天被投票放逐时可以翻牌存活，但之后失去投票权",
            "kind": "info",
            "round": state["round"],
            "phase": state["phase"].value,
        },
        scope=EventScope.ROLE_PRIVATE, targets={idiot_id},
    )
    await _hold_night_phase(phase_start)
    return PhaseResult(events=events, persisted_event_count=len(events))


@phase(Phase.NIGHT_RESOLVE, narration=("info", "天将亮起 · 裁判结算夜晚行动"))
async def handle_night_resolve(state: GameState, services: SessionServices) -> PhaseResult:
    wolf_target = state["night_actions"].get("wolf_target")
    use_antidote = bool(state["night_actions"].get("witch_use_antidote"))
    poison_target = state["night_actions"].get("witch_poison_target")

    deaths: list[tuple[int, str]] = []
    seen: set[int] = set()
    if wolf_target is not None and not use_antidote:
        deaths.append((wolf_target, "wolf"))
        seen.add(wolf_target)
    if poison_target is not None and poison_target not in seen:
        deaths.append((poison_target, "poison"))
        seen.add(poison_target)

    patch: dict = {"night_result": {"deaths": [pid for pid, _ in deaths]}}
    events: list[GameEvent] = []
    pending: list[PendingSkill] = list(state["pending_skills"])
    players_patch: dict[int, dict] = {}
    dead_history = list(state["dead_history"])

    for player_id, cause in deaths:
        if not state["players"][player_id]["alive"] or player_id in players_patch:
            continue
        players_patch[player_id] = {
            "alive": False, "death_round": state["round"],
            "death_cause": cause, "is_sheriff": False,
        }
        dead_history.append({"player_id": player_id, "cause": cause, "round": state["round"]})
        # Night deaths announce publicly WITHOUT the cause — the crowd
        # learns "X 号死亡" at dawn but not who killed them. The actual
        # cause is still known to the perpetrator's role via existing
        # private events (wolf_target_selected → wolf team,
        # witch_used_poison → witch). Frontend recovers cause from those
        # for the right viewer.
        emit_event(services, state, events, EventType.PLAYER_DIED,
                   {"player_id": player_id})
        _queue_death_skills(state, pending, player_id, cause)

    patch["players"] = players_patch
    if any(state["players"][pid]["is_sheriff"] for pid, _ in deaths):
        patch["sheriff_id"] = None
    patch["dead_history"] = dead_history
    patch["pending_skills"] = pending

    # NOTE: Death speeches for night deaths are NOT collected here —
    # they're emitted by handle_day_announce AFTER the dawn "X 名
    # 玩家出局" narration so the read order matches the village's
    # experience: announcement first, then last words.

    return PhaseResult(state_patch=patch, events=events, persisted_event_count=len(events))


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _find_alive_role(state: GameState, role: Role) -> int | None:
    for player_id, player in state["players"].items():
        if player["alive"] and player["role"] == role:
            return player_id
    return None


_action_source = action_source  # backward-compat alias for imports from other handlers


def _queue_death_skills(state: GameState, pending: list[PendingSkill], player_id: int, cause: str) -> None:
    player = state["players"][player_id]
    if player["role"] == Role.HUNTER:
        can_shoot_if_poisoned = state["runtime"]["rule_flags"].get("hunter_can_shoot_if_poisoned", False)
        if cause != "poison" or can_shoot_if_poisoned:
            pending.append({"kind": "hunter_shot", "actor_id": player_id, "context": {"cause": cause}})
    if player["is_sheriff"]:
        pending.append({"kind": "sheriff_transfer", "actor_id": player_id, "context": {"cause": cause}})


async def _collect_death_speeches(
    state: GameState,
    services: "SessionServices",
    dead_player_ids: list[int],
    *,
    death_causes: dict[int, str] | None = None,
) -> list[GameEvent]:
    """Collect death speeches (遗言) for newly dead players.

    Standard 12-人 ruleset (用户约定):
      * Night-1 deaths (collected at DAY_ANNOUNCE of round 1) → 完整遗言
      * Any DAY_RESOLVE (放逐) death                          → 完整遗言
      * Later-night deaths (DAY_ANNOUNCE of round >= 2)       → 不发表遗言
    """
    from app.engine.event_helpers import emit_narration

    events: list[GameEvent] = []
    # Death speeches fire either:
    #   * during DAY_ANNOUNCE (the dawn re-airs night kills, then speeches)
    #   * during DAY_RESOLVE (the exiled player gives their last words)
    if state["phase"] not in (Phase.DAY_ANNOUNCE, Phase.DAY_RESOLVE):
        return events
    is_post_night = state["phase"] == Phase.DAY_ANNOUNCE
    # Subsequent-night deaths stay silent — only night 1 gets the slot.
    if is_post_night and state["round"] >= 2:
        return events

    for player_id in dead_player_ids:
        # Give the previous intro banner (dawn "天亮了 · X 号死亡" on
        # DAY_ANNOUNCE, or the exile "X 号被放逐" on DAY_RESOLVE) time
        # to be read before this 遗言 banner replaces it. Without this,
        # the dawn banner is overwritten within milliseconds.
        from app.engine.session import _wait_for_min_narration_hold
        await _wait_for_min_narration_hold(services)

        role = state["players"][player_id]["role"]
        cause = (death_causes or {}).get(player_id) or state["players"][player_id].get("death_cause")
        # Phase-style intro narration so the frontend pins this as the
        # big PhaseFlash banner during the 遗言 window — without
        # intro=True the "X 号玩家发表遗言" line is rendered only as a
        # small ticker, easily missed under the death-overlay (so the
        # village sees the speech start with no announcement).
        emit_narration(
            services, state, events,
            f"{player_id} 号玩家发表遗言",
            kind="info", glyph="🪦", intro=True,
        )
        emit_speaking_started(services, state, events, player_id=player_id)
        proposed_args = await llm_death_speech(
            state, services,
            actor_id=player_id, role=role, phase=state["phase"],
            local_args={"public_speech": f"玩家{player_id}（{role.value}）的遗言", "internal_thought": ""},
        )
        speech = proposed_args.get("public_speech", "")
        if speech:
            # `cause` intentionally NOT included in the public event data —
            # night-death cause is hidden from the village; including it
            # here would leak via the public death_speech event.
            emit_event(services, state, events, EventType.DEATH_SPEECH,
                       {"player_id": player_id, "speech": speech})
    return events
