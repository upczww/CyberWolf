from __future__ import annotations

import json
from pathlib import Path

from app.domain.context import PromptContext
from app.domain.config import RuntimeConfig
from app.domain.roles import Phase, Role
from app.services.llm import enabled_tools


def resolve_prompt_template(runtime: RuntimeConfig, phase: Phase, role: Role) -> str:
    templates = runtime["prompt_profile"].get("templates", {})
    role_key = f"{phase.value}:{role.value}"
    if role_key in templates:
        return templates[role_key]
    if phase.value in templates:
        return templates[phase.value]
    return "default_public_speech.j2"


def load_prompt_template(prompt_dir: Path, template_name: str) -> str:
    return (prompt_dir / template_name).read_text(encoding="utf-8")


def render_prompt_template(template: str, values: dict) -> str:
    rendered = template
    for key, value in values.items():
        if isinstance(value, str):
            text = value
        else:
            text = json.dumps(value, ensure_ascii=False, default=str)
        rendered = rendered.replace("{{ " + key + " }}", text)
        rendered = rendered.replace("{{" + key + "}}", text)
    return rendered


def split_rendered_template(rendered: str) -> tuple[str, str]:
    """Split a rendered template at the last '---' into (static_rules, dynamic_state).

    Returns ("", full_content) if no separator found.
    The static part is used as the system prompt (stable across players for cache hits).
    The dynamic part goes into the user message (different per player).
    """
    idx = rendered.rfind("\n---\n")
    if idx == -1:
        return "", rendered.strip()
    static = rendered[:idx].strip()
    dynamic = rendered[idx + len("\n---\n"):].strip()
    return static, dynamic


def build_prompt_inputs(
    runtime: RuntimeConfig,
    *,
    player_id: int,
    role: Role,
    phase: Phase,
    context: PromptContext,
) -> dict:
    return {
        "config_name": runtime["name"],
        "player_count": runtime["player_count"],
        "phase": phase.value,
        "round": context["public"]["round"],
        "player_id": player_id,
        "role": role.value,
        "visible_state": context["public"]["public_summary"],
        "public_summary": context["public"]["public_summary"],
        "private_memory": context["private"]["private_memory"],
        "role_specific_state": context["private"]["role_specific_state"],
        "visible_teammates": [] if context["faction"] is None else context["faction"]["visible_teammates"],
        "enabled_tools": [tool["name"] for tool in enabled_tools(runtime, role, phase)],
        "speech_constraints": {
            "max_chars": runtime["prompt_profile"].get("max_public_speech_chars", 180),
            "include_internal_thought": runtime["prompt_profile"].get("include_internal_thought", False),
        },
    }
