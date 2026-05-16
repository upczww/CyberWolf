from __future__ import annotations

import json
import ssl
from dataclasses import dataclass
from typing import Any, Protocol
from urllib.error import HTTPError
from urllib import request

from app.config import LLMSettings
from app.domain.config import ToolSpec


class LLMProvider(Protocol):
    def build_payload(
        self,
        *,
        settings: LLMSettings,
        messages: list[dict[str, Any]],
        tools: list[ToolSpec],
        force_tool: bool,
    ) -> dict[str, Any]: ...

    def parse_response(self, payload: dict[str, Any]) -> tuple[str | None, dict[str, Any] | None, str | None]: ...

    def post_json(self, settings: LLMSettings, payload: dict[str, Any]) -> dict[str, Any]: ...


@dataclass(slots=True)
class OpenAICompatibleProvider:
    def build_payload(
        self,
        *,
        settings: LLMSettings,
        messages: list[dict[str, Any]],
        tools: list[ToolSpec],
        force_tool: bool,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": settings.model_id,
            "messages": messages,
            "tools": [to_openai_tool(tool) for tool in tools],
        }
        if force_tool and tools:
            payload["tool_choice"] = "required"
        return payload

    def parse_response(self, payload: dict[str, Any]) -> tuple[str | None, dict[str, Any] | None, str | None]:
        choices = payload.get("choices", [])
        if not choices:
            return None, None, None
        message = choices[0].get("message", {})
        tool_calls = message.get("tool_calls") or []
        if tool_calls:
            function_call = tool_calls[0].get("function", {})
            args = function_call.get("arguments") or "{}"
            return function_call.get("name"), json.loads(args), message.get("content")
        return None, None, message.get("content")

    def post_json(self, settings: LLMSettings, payload: dict[str, Any]) -> dict[str, Any]:
        body = json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if settings.api_key:
            headers[settings.api_key_header] = f"{settings.api_key_prefix}{settings.api_key}"
        if settings.extra_headers:
            headers.update(settings.extra_headers)
        req = request.Request(
            settings.api_url,
            data=body,
            headers=headers,
            method="POST",
        )
        ssl_context = ssl.create_default_context() if settings.verify_ssl else ssl._create_unverified_context()
        try:
            with request.urlopen(req, timeout=settings.timeout_seconds, context=ssl_context) as resp:  # noqa: S310
                return json.loads(resp.read().decode("utf-8"))
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"HTTP {exc.code}: {body}") from exc


@dataclass(slots=True)
class DeepSeekProvider(OpenAICompatibleProvider):
    def build_payload(
        self,
        *,
        settings: LLMSettings,
        messages: list[dict[str, Any]],
        tools: list[ToolSpec],
        force_tool: bool,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": settings.model_id,
            "messages": messages,
            "tools": [to_deepseek_strict_tool(tool) for tool in tools],
            "reasoning_effort": "high",
            "thinking": {"type": "enabled"},
        }
        return payload

    def post_json(self, settings: LLMSettings, payload: dict[str, Any]) -> dict[str, Any]:
        if "/beta/" not in settings.api_url and not settings.api_url.rstrip("/").endswith("/beta/chat/completions"):
            beta_url = settings.api_url.replace("/chat/completions", "/beta/chat/completions")
            settings = LLMSettings(
                provider_name=settings.provider_name,
                api_key=settings.api_key,
                api_url=beta_url,
                model_id=settings.model_id,
                api_key_header=settings.api_key_header,
                api_key_prefix=settings.api_key_prefix,
                extra_headers=settings.extra_headers,
                verify_ssl=settings.verify_ssl,
                timeout_seconds=settings.timeout_seconds,
                max_retries=settings.max_retries,
                retry_backoff_seconds=settings.retry_backoff_seconds,
                max_concurrency=settings.max_concurrency,
                max_calls_per_game=settings.max_calls_per_game,
                enabled_phase_names=settings.enabled_phase_names,
            )
        return OpenAICompatibleProvider.post_json(self, settings, payload)


PROVIDERS: dict[str, LLMProvider] = {
    "openai_compatible": OpenAICompatibleProvider(),
    "zhipu_openai_compatible": OpenAICompatibleProvider(),
    "deepseek": DeepSeekProvider(),
    "deepseek_openai_compatible": DeepSeekProvider(),
}


def get_provider(name: str) -> LLMProvider:
    return PROVIDERS.get(name, PROVIDERS["openai_compatible"])


def to_openai_tool(tool: ToolSpec) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": tool["name"],
            "description": tool["description"],
            "parameters": tool["input_schema"],
        },
    }


def to_deepseek_strict_tool(tool: ToolSpec) -> dict[str, Any]:
    payload = to_openai_tool(tool)
    payload["function"]["strict"] = True
    payload["function"]["parameters"] = normalize_deepseek_schema(payload["function"]["parameters"])
    return payload


def normalize_deepseek_schema(schema: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(schema)
    if normalized.get("type") == "object":
        properties = dict(normalized.get("properties", {}))
        normalized["properties"] = {
            name: normalize_deepseek_schema(prop) if isinstance(prop, dict) else prop
            for name, prop in properties.items()
        }
        normalized["required"] = list(properties.keys())
        normalized["additionalProperties"] = False
    elif normalized.get("type") == "array" and isinstance(normalized.get("items"), dict):
        normalized["items"] = normalize_deepseek_schema(normalized["items"])
    elif isinstance(normalized.get("type"), list):
        normalized["anyOf"] = [{"type": item} for item in normalized.pop("type")]
    return normalized
