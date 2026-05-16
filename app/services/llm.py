from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from time import monotonic
from typing import Any
from urllib.error import HTTPError, URLError

from app.config import LLMSettings
from app.domain.config import RuntimeConfig, ToolSpec
from app.domain.roles import Phase, Role
from app.services.llm_provider import get_provider


TOOL_REGISTRY: dict[str, ToolSpec] = {
    "wolf_kill_proposal": ToolSpec(
        name="wolf_kill_proposal",
        description="Choose one alive non-wolf player to attack tonight.",
        input_schema={
            "type": "object",
            "properties": {"target_id": {"type": "integer"}},
            "required": ["target_id"],
            "additionalProperties": False,
        },
        enabled_roles=[Role.WOLF],
        enabled_phases=[Phase.NIGHT_WOLF],
        output_mode="tool_call",
    ),
    "seer_check": ToolSpec(
        name="seer_check",
        description="Choose one alive player to inspect.",
        input_schema={
            "type": "object",
            "properties": {"target_id": {"type": "integer"}},
            "required": ["target_id"],
            "additionalProperties": False,
        },
        enabled_roles=[Role.SEER],
        enabled_phases=[Phase.NIGHT_SEER],
        output_mode="tool_call",
    ),
    "witch_antidote": ToolSpec(
        name="witch_antidote",
        description="Decide whether to use the antidote to save the player killed by wolves tonight.",
        input_schema={
            "type": "object",
            "properties": {
                "use_antidote": {"type": "boolean"},
                "internal_thought": {"type": "string"},
            },
            "required": ["use_antidote"],
            "additionalProperties": False,
        },
        enabled_roles=[Role.WITCH],
        enabled_phases=[Phase.NIGHT_WITCH],
        output_mode="tool_call",
    ),
    "witch_poison": ToolSpec(
        name="witch_poison",
        description="Choose a player to poison tonight, or skip by setting target_id to null.",
        input_schema={
            "type": "object",
            "properties": {
                "target_id": {"type": ["integer", "null"]},
                "internal_thought": {"type": "string"},
            },
            "required": ["target_id"],
            "additionalProperties": False,
        },
        enabled_roles=[Role.WITCH],
        enabled_phases=[Phase.NIGHT_WITCH],
        output_mode="tool_call",
    ),
    "public_speech": ToolSpec(
        name="public_speech",
        description="Produce a structured public speech.",
        input_schema={
            "type": "object",
            "properties": {
                "public_speech": {"type": "string"},
                "internal_thought": {"type": "string"},
            },
            "required": ["public_speech"],
            "additionalProperties": False,
        },
        enabled_roles=[role for role in Role],
        enabled_phases=[Phase.SHERIFF_ELECTION, Phase.DAY_SPEECH],
        output_mode="tool_call",
    ),
    "vote_target": ToolSpec(
        name="vote_target",
        description="Vote to exile a target.",
        input_schema={
            "type": "object",
            "properties": {"target_id": {"type": "integer"}},
            "required": ["target_id"],
            "additionalProperties": False,
        },
        enabled_roles=[role for role in Role],
        enabled_phases=[Phase.SHERIFF_ELECTION, Phase.DAY_VOTE],
        output_mode="tool_call",
    ),
    "hunter_shoot": ToolSpec(
        name="hunter_shoot",
        description="Shoot a target on death.",
        input_schema={
            "type": "object",
            "properties": {"target_id": {"type": "integer"}},
            "required": ["target_id"],
            "additionalProperties": False,
        },
        enabled_roles=[Role.HUNTER],
        enabled_phases=[Phase.PENDING_SKILLS],
        output_mode="tool_call",
    ),
    "sheriff_transfer": ToolSpec(
        name="sheriff_transfer",
        description="Transfer or destroy the sheriff badge.",
        input_schema={
            "type": "object",
            "properties": {"target_id": {"type": ["integer", "null"]}},
            "required": ["target_id"],
            "additionalProperties": False,
        },
        enabled_roles=[role for role in Role],
        enabled_phases=[Phase.PENDING_SKILLS],
        output_mode="tool_call",
    ),
    "guard_protect": ToolSpec(
        name="guard_protect",
        description="Protect a target at night.",
        input_schema={
            "type": "object",
            "properties": {"target_id": {"type": "integer"}},
            "required": ["target_id"],
            "additionalProperties": False,
        },
        enabled_roles=[Role.GUARD],
        enabled_phases=[Phase.NIGHT_GUARD],
        output_mode="tool_call",
    ),
    "wolf_self_destruct": ToolSpec(
        name="wolf_self_destruct",
        description="Self-destruct: reveal your wolf identity to immediately end the day and enter night. During campaign: badge destroyed. During vote: skip vote. No last words.",
        input_schema={
            "type": "object",
            "properties": {"reason": {"type": "string"}},
            "required": [],
            "additionalProperties": False,
        },
        enabled_roles=[Role.WOLF],
        enabled_phases=[Phase.SHERIFF_ELECTION, Phase.DAY_SPEECH, Phase.DAY_VOTE],
        output_mode="tool_call",
    ),
}


def enabled_tools(runtime: RuntimeConfig, role: Role, phase: Phase) -> list[ToolSpec]:
    disabled = set(runtime.get("tool_profile", {}).get("disabled_tools", []))
    explicit = runtime.get("tool_profile", {}).get("enabled_tools", [])
    tools: list[ToolSpec] = []
    for name, tool in TOOL_REGISTRY.items():
        if explicit and name not in explicit:
            continue
        if name in disabled:
            continue
        if role not in tool["enabled_roles"] or phase not in tool["enabled_phases"]:
            continue
        if name == "guard_protect" and Role.GUARD not in runtime["enabled_roles"]:
            continue
        tools.append(tool)
    return tools


@dataclass(slots=True)
class LLMCallResult:
    success: bool
    tool_name: str | None
    tool_args: dict[str, Any] | None
    content: str | None
    request_payload: dict[str, Any]
    response_payload: dict[str, Any] | None
    latency_ms: int
    retry_count: int = 0
    error_message: str | None = None
    assistant_message: dict[str, Any] | None = None


class LLMClient:
    def __init__(self, settings: LLMSettings) -> None:
        self._settings = settings
        self._provider = get_provider(settings.provider_name)

    async def call_with_tools(
        self,
        *,
        messages: list[dict[str, Any]],
        tools: list[ToolSpec],
        force_tool: bool = True,
    ) -> LLMCallResult:
        payload = self._provider.build_payload(
            settings=self._settings,
            messages=messages,
            tools=tools,
            force_tool=force_tool,
        )

        started = monotonic()
        last_error: str | None = None
        last_response_payload: dict[str, Any] | None = None
        last_assistant_message: dict[str, Any] | None = None
        retry_count = 0
        allowed_tool_names = {tool["name"] for tool in tools}
        for attempt in range(self._settings.max_retries + 1):
            try:
                response_payload = await asyncio.wait_for(
                    asyncio.to_thread(self._provider.post_json, self._settings, payload),
                    timeout=self._settings.timeout_seconds,
                )
                latency_ms = int((monotonic() - started) * 1000)
                tool_name, tool_args, content = self._provider.parse_response(response_payload)
                last_response_payload = response_payload
                last_assistant_message = _extract_assistant_message(response_payload)
                invalid_tool_response = _invalid_tool_response_error(
                    force_tool=force_tool,
                    tool_name=tool_name,
                    tool_args=tool_args,
                    content=content,
                    allowed_tool_names=allowed_tool_names,
                )
                if invalid_tool_response is not None:
                    last_error = invalid_tool_response
                    if attempt >= self._settings.max_retries:
                        break
                    _append_tool_retry_instruction(payload, invalid_tool_response, allowed_tool_names)
                    retry_count += 1
                    await asyncio.sleep(self._settings.retry_backoff_seconds * (2**attempt))
                    continue
                return LLMCallResult(
                    success=True,
                    tool_name=tool_name,
                    tool_args=tool_args,
                    content=content,
                    request_payload=payload,
                    response_payload=response_payload,
                    latency_ms=latency_ms,
                    retry_count=retry_count,
                    assistant_message=last_assistant_message,
                )
            except Exception as exc:  # pragma: no cover - network path
                last_error = str(exc) or repr(exc)
                if attempt >= self._settings.max_retries or not _should_retry(exc):
                    break
                retry_count += 1
                await asyncio.sleep(self._settings.retry_backoff_seconds * (2**attempt))

        latency_ms = int((monotonic() - started) * 1000)
        return LLMCallResult(
            success=False,
            tool_name=None,
            tool_args=None,
            content=None,
            request_payload=payload,
            response_payload=last_response_payload,
            latency_ms=latency_ms,
            retry_count=retry_count,
            error_message=last_error,
            assistant_message=last_assistant_message,
        )


def _extract_assistant_message(payload: dict[str, Any]) -> dict[str, Any] | None:
    choices = payload.get("choices", [])
    if not choices:
        return None
    message = choices[0].get("message")
    return dict(message) if isinstance(message, dict) else None


def _invalid_tool_response_error(
    *,
    force_tool: bool,
    tool_name: str | None,
    tool_args: dict[str, Any] | None,
    content: str | None,
    allowed_tool_names: set[str],
) -> str | None:
    if not force_tool:
        return None
    if tool_name is None:
        if content:
            return "model answered in plain text instead of calling a tool"
        return "empty model response"
    if allowed_tool_names and tool_name not in allowed_tool_names:
        allowed = ", ".join(sorted(allowed_tool_names))
        return f"model called unexpected tool {tool_name}; allowed tools: {allowed}"
    if tool_args is None:
        return f"model called {tool_name} without JSON object arguments"
    return None


def _append_tool_retry_instruction(
    payload: dict[str, Any],
    error: str,
    allowed_tool_names: set[str],
) -> None:
    messages = payload.get("messages")
    if not isinstance(messages, list):
        return
    allowed = ", ".join(sorted(allowed_tool_names)) or "the provided tool"
    messages.append(
        {
            "role": "user",
            "content": (
                f"上一轮响应无效：{error}。必须调用工具，不要输出普通文本。"
                f"只能调用这些工具：{allowed}。"
            ),
        }
    )


def build_phase_messages(
    *,
    system_prompts: list[str],
    user_content: str,
) -> list[dict[str, Any]]:
    messages = [{"role": "system", "content": p} for p in system_prompts]
    messages.append({"role": "user", "content": user_content})
    return messages


def _should_retry(exc: Exception) -> bool:
    if isinstance(exc, HTTPError):
        return exc.code in {408, 409, 425, 429, 500, 502, 503, 504}
    if isinstance(exc, URLError):
        return True
    text = str(exc).lower()
    return "timeout" in text or "temporarily unavailable" in text or "too many requests" in text
