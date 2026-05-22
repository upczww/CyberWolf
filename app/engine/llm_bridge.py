"""Unified LLM decision pipeline.

Merges _llm_tool_or_local, _llm_speech_or_local, and _llm_death_speech_or_local
into a single parameterized function, eliminating ~300 lines of duplication.
"""
from __future__ import annotations

import asyncio
import json
import logging
from time import monotonic
from typing import TYPE_CHECKING, Any

from app.domain.events import GameEvent
from app.domain.roles import EventScope, EventType, Phase, Role
from app.domain.state import GameState
from app.services.context_builder import build_prompt_context
from app.services.llm import TOOL_REGISTRY, LLMCallResult, build_phase_messages, enabled_tools
from app.services.prompts import (
    build_prompt_inputs,
    load_prompt_template,
    render_prompt_template,
    resolve_prompt_template,
    split_rendered_template,
)
from app.engine.pacing import phase_remaining_seconds

if TYPE_CHECKING:
    from app.engine.session import SessionServices

_log = logging.getLogger(__name__)

_COMMON_RULES = """你是一名狼人杀游戏玩家，正在进行一局12人标准局（预女猎白+警长）。你必须严格遵循游戏规则，根据你的身份、已知信息以及场上形势，做出合理决策和发言。

核心行为准则：
· 你的唯一目标是帮助己方阵营获胜。无论是发言、投票还是使用技能，都应为胜利服务。
· 你只能根据游戏规则允许你获知的信息（如夜晚睁眼看到的信息、主持人通报的死亡信息、放逐结果等）来行动，不能使用上帝视角。
· 发言要符合逻辑，尽量模仿真实玩家的风格，可适当带情绪，但不得辱骂或人身攻击。
· 投票必须给出清晰的对象，不能模糊。
· 如果你已出局，请遵守遗言规则，之后不能再参与发言和投票（白痴翻牌后发言除外）。"""


async def llm_decide(
    state: GameState,
    services: "SessionServices",
    *,
    actor_id: int,
    role: Role,
    phase: Phase,
    tool_name: str,
    local_args: dict,
    prompt_key_override: str | None = None,
    decision_note: str | None = None,
    bypass_human: bool = False,
) -> dict:
    """Unified LLM tool call with retry and wolf self-destruct support.

    Returns normal args dict, or {"_wolf_self_destruct": True} if wolf chose to self-destruct.
    Falls back to local_args on failure.

    ``bypass_human=True`` skips the human-awaiter routing even when the
    actor IS the human. Used by handlers that need to re-decide after a
    human explicitly delegated to AI (e.g. wolf-kill panel "让 AI 决定").
    """
    if not bypass_human and _is_human_actor(state, actor_id) and services.human_awaiter is not None:
        return await _await_human_action(
            state, services,
            actor_id=actor_id, role=role, phase=phase,
            tool_name=tool_name, local_args=local_args,
        )
    if services.llm_client is None or services.llm_settings is None:
        return local_args
    if phase.value not in services.llm_settings.enabled_phase_names:
        return local_args
    if services.total_llm_calls >= services.llm_settings.max_calls_per_game:
        _log.warning(
            "LLM call limit reached before %s/%s for player %s: %s/%s — using fallback",
            phase.value, tool_name, actor_id,
            services.total_llm_calls, services.llm_settings.max_calls_per_game,
        )
        return local_args

    remaining = phase_remaining_seconds(services)
    if remaining is not None and remaining <= 0.25:
        return local_args

    # Build prompt
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

    # Build tool list (primary + optional wolf_self_destruct)
    tools = [tool for tool in enabled_tools(state["runtime"], role, phase) if tool["name"] == tool_name]
    is_wolf_day = role == Role.WOLF and phase in (
        Phase.DAY_SPEECH, Phase.DAY_VOTE, Phase.SHERIFF_ELECTION,
    )
    if is_wolf_day:
        sd_tool = [t for t in TOOL_REGISTRY.values() if t["name"] == "wolf_self_destruct"]
        tools.extend(sd_tool)

    # First attempt
    result = await _call_llm(services, messages, tools)
    _persist_llm_call(services, state, actor_id=actor_id, phase=phase, prompt_key=prompt_key, result=result)

    # Check wolf self-destruct
    if is_wolf_day and result.success and result.tool_name == "wolf_self_destruct":
        return {"_wolf_self_destruct": True}

    # Retry on failure
    if not result.success or result.tool_name != tool_name or result.tool_args is None:
        failure_reason = _failure_reason(result, tool_name)
        result = await _retry_once(
            services, state, messages, tools,
            actor_id=actor_id, phase=phase, prompt_key=prompt_key,
            tool_name=tool_name, failure_reason=failure_reason, result=result,
        )
        if result is None:
            return local_args
        # Check self-destruct on retry
        if is_wolf_day and result.success and result.tool_name == "wolf_self_destruct":
            return {"_wolf_self_destruct": True}
        if not result.success or result.tool_name != tool_name or result.tool_args is None:
            _log.warning(
                "LLM tool call failed for P%s %s/%s after retry: %s — using fallback",
                actor_id, phase.value, tool_name, failure_reason,
            )
            return local_args

    _append_llm_messages(state, actor_id=actor_id, request_messages=messages, result=result)
    return result.tool_args


async def llm_speech(
    state: GameState,
    services: "SessionServices",
    *,
    actor_id: int,
    role: Role,
    phase: Phase,
    local_args: dict,
) -> dict:
    """LLM speech call — delegates to llm_decide with tool_name='public_speech'."""
    return await llm_decide(
        state, services,
        actor_id=actor_id,
        role=role,
        phase=phase,
        tool_name="public_speech",
        local_args=local_args,
    )


def _is_human_actor(state: GameState, actor_id: int) -> bool:
    human_seats = state.get("human_seats")
    if human_seats and actor_id in human_seats:
        return True
    # Legacy single-human fallback for state dicts that pre-date human_seats.
    return state.get("human_seat") == actor_id


async def _await_human_action(
    state: GameState,
    services: "SessionServices",
    *,
    actor_id: int,
    role: Role,
    phase: Phase,
    tool_name: str,
    local_args: dict,
    timeout_seconds: float = 60.0,
) -> dict:
    """Emit an awaiting_human event and wait for the API to submit a result."""
    awaiter = services.human_awaiter
    if awaiter is None:
        return local_args
    timeout_seconds = _human_timeout_seconds(tool_name, phase)
    remaining = phase_remaining_seconds(services)
    if remaining is not None:
        timeout_seconds = max(0.1, min(timeout_seconds, remaining))

    # Phase narration ("女巫请睁眼", "预言家请睁眼"...) must fire BEFORE we
    # publish awaiting_human and block on the awaiter — otherwise the
    # human only sees their action panel modal while the previous
    # phase's banner is still on screen, with no indication that a new
    # phase has started. _ensure_phase_started is a no-op if it has
    # already fired for this phase.
    from app.engine.session import _ensure_phase_started
    _ensure_phase_started(services, state, services.conn, phase, state["round"])

    # Emit awaiting_human (private to the actor) so the frontend can render the action panel
    payload = {
        "actor_id": actor_id,
        "tool_name": tool_name,
        "phase": phase.value,
        "round": state["round"],
        "role": role.value,
        "timeout_seconds": timeout_seconds,
        "local_args": local_args,
    }
    event = GameEvent(
        game_id=state["game_id"], phase=state["phase"],
        scope=EventScope.ROLE_PRIVATE, target_players={actor_id},
        event_type=EventType.AWAITING_HUMAN,
        content=f"event.{EventType.AWAITING_HUMAN.value}",
        data=payload,
    )
    services.event_bus.publish(event)
    try:
        args = await awaiter.wait_for_action(
            actor_id=actor_id, tool_name=tool_name, phase=phase.value,
            local_args=local_args, timeout_seconds=timeout_seconds,
            role=role.value, round_no=state["round"],
        )
    finally:
        services.event_bus.publish(GameEvent(
            game_id=state["game_id"], phase=state["phase"],
            scope=EventScope.ROLE_PRIVATE, target_players={actor_id},
            event_type=EventType.HUMAN_SUBMITTED,
            content=f"event.{EventType.HUMAN_SUBMITTED.value}",
            data={"actor_id": actor_id, "tool_name": tool_name},
        ))
    return args


def _human_timeout_seconds(tool_name: str, phase: Phase) -> float:
    """Longer thinking windows for the human-controlled local seat."""
    if tool_name == "confirm_identity":
        return 30.0  # short — just enough to read the identity card
    if tool_name in {"public_speech", "death_speech"}:
        # Hard 90s cap on every player's speech (per-player house rule).
        return 90.0
    if tool_name == "vote_target":
        return 120.0
    # Night role-call tools all share the 15–30s phase budget enforced
    # in handle_night_*. Capping the awaiter at 30s keeps the phase
    # from running past its window even if the human is deciding.
    if tool_name in {
        "wolf_kill_proposal",
        "seer_check",
        "witch_antidote",
        "witch_poison",
        "guard_protect",
    }:
        return 30.0
    if tool_name == "hunter_shoot":
        return 30.0  # also a single-target reveal-style choice
    if tool_name == "sheriff_candidacy":
        return 30.0
    if tool_name == "sheriff_pick_direction":
        return 20.0  # quick 顺/逆 pick
    if phase in {Phase.DAY_SPEECH, Phase.SHERIFF_ELECTION}:
        return 90.0  # speech-phase fallback also capped at 90s
    return 30.0


async def llm_death_speech(
    state: GameState,
    services: "SessionServices",
    *,
    actor_id: int,
    role: Role,
    phase: Phase,
    local_args: dict,
) -> dict:
    """Death speech — bypasses phase-based tool filtering."""
    if _is_human_actor(state, actor_id) and services.human_awaiter is not None:
        return await _await_human_action(
            state, services,
            actor_id=actor_id, role=role, phase=phase,
            tool_name="death_speech", local_args=local_args,
        )
    if services.llm_client is None or services.llm_settings is None:
        return local_args
    if services.total_llm_calls >= services.llm_settings.max_calls_per_game:
        return local_args
    remaining = phase_remaining_seconds(services)
    if remaining is not None and remaining <= 0.25:
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
    tools = [t for t in TOOL_REGISTRY.values() if t["name"] == "public_speech"]

    result = await _call_llm(services, messages, tools)
    _persist_llm_call(services, state, actor_id=actor_id, phase=phase, prompt_key="death_speech", result=result)

    if not result.success or result.tool_name != "public_speech" or result.tool_args is None:
        return local_args
    return result.tool_args


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


async def _call_llm(services: "SessionServices", messages: list[dict], tools: list) -> LLMCallResult:
    """Execute a single LLM call with semaphore."""
    services.total_llm_calls += 1
    started = monotonic()

    async def invoke() -> LLMCallResult:
        if services.llm_semaphore is None:
            return await services.llm_client.call_with_tools(messages=messages, tools=tools, force_tool=True)
        async with services.llm_semaphore:
            return await services.llm_client.call_with_tools(messages=messages, tools=tools, force_tool=True)

    remaining = phase_remaining_seconds(services)
    if remaining is not None and remaining <= 0.25:
        return LLMCallResult(
            success=False,
            tool_name=None,
            tool_args=None,
            content=None,
            request_payload={},
            response_payload=None,
            latency_ms=0,
            error_message="phase_budget_exhausted",
        )
    try:
        if remaining is not None:
            return await asyncio.wait_for(invoke(), timeout=remaining)
        return await invoke()
    except asyncio.TimeoutError:
        return LLMCallResult(
            success=False,
            tool_name=None,
            tool_args=None,
            content=None,
            request_payload={},
            response_payload=None,
            latency_ms=int((monotonic() - started) * 1000),
            error_message="phase_budget_timeout",
        )


async def _retry_once(
    services: "SessionServices",
    state: GameState,
    messages: list[dict],
    tools: list,
    *,
    actor_id: int,
    phase: Phase,
    prompt_key: str,
    tool_name: str,
    failure_reason: str,
    result: LLMCallResult,
) -> LLMCallResult | None:
    """Retry once on failure. Returns new result or None if can't retry."""
    if services.total_llm_calls >= services.llm_settings.max_calls_per_game:
        return None
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
    new_result = await _call_llm(services, retry_messages, tools)
    _persist_llm_call(
        services, state, actor_id=actor_id, phase=phase,
        prompt_key=f"{prompt_key}:retry", result=new_result,
    )
    return new_result


def _failure_reason(result: LLMCallResult, expected_tool: str) -> str:
    if not result.success:
        return result.error_message or "LLM call failed"
    if result.tool_name != expected_tool:
        return f"called wrong tool '{result.tool_name}' instead of '{expected_tool}'"
    if result.tool_args is None:
        return "called tool without arguments"
    return "unknown failure"


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


def _persist_llm_call(
    services: "SessionServices",
    state: GameState,
    *,
    actor_id: int,
    phase: Phase,
    prompt_key: str,
    result: LLMCallResult,
) -> None:
    if services.llm_settings is None:
        return
    from app.infra.repositories.llm_calls import insert_llm_call

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
