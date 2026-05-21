from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from app.domain.config import GameConfig, PromptProfile, RoleSpec, RuntimeConfig, ToolProfile
from app.domain.roles import Phase, Role, WinRule
from app.services.llm import enabled_tools

try:
    import yaml
except ImportError:  # pragma: no cover - optional dependency
    yaml = None


def _load_raw_config(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".json":
        return json.loads(text)
    if yaml is None:
        raise RuntimeError("PyYAML is required to load YAML configs.")
    return yaml.safe_load(text)


def _as_role_specs(items: list[dict[str, Any]]) -> list[RoleSpec]:
    return [
        RoleSpec(role=Role(item["role"]), count=int(item["count"]), enabled=bool(item.get("enabled", True)))
        for item in items
    ]


def _as_prompt_profile(raw: dict[str, Any] | None) -> PromptProfile:
    return PromptProfile(**(raw or {}))


def _as_tool_profile(raw: dict[str, Any] | None) -> ToolProfile:
    return ToolProfile(**(raw or {}))


def load_game_config(path: Path) -> GameConfig:
    raw = _load_raw_config(path)
    config = GameConfig(
        config_id=raw["config_id"],
        name=raw["name"],
        player_count=int(raw["player_count"]),
        roles=_as_role_specs(raw["roles"]),
        rule_flags=raw.get("rule_flags", {}),
        phase_order=[Phase(item) for item in raw["phase_order"]],
        win_rule=WinRule(raw["win_rule"]),
        prompt_profile=_as_prompt_profile(raw.get("prompt_profile")),
        tool_profile=_as_tool_profile(raw.get("tool_profile")),
    )
    validate_game_config(config)
    return config


def validate_game_config(config: GameConfig) -> None:
    total = sum(spec["count"] for spec in config["roles"] if spec["enabled"])
    if total != config["player_count"]:
        raise ValueError(f"enabled role count {total} does not match player_count {config['player_count']}")
    required = {Phase.SETUP_GAME, Phase.CHECK_WIN, Phase.GAME_OVER}
    missing = required - set(config["phase_order"])
    if missing:
        raise ValueError(f"phase_order missing required phases: {sorted(item.value for item in missing)}")


def build_phase_order(config: GameConfig) -> list[Phase]:
    phases = list(config["phase_order"])
    roles = {spec["role"] for spec in config["roles"] if spec["enabled"]}
    flags = config["rule_flags"]

    if Role.GUARD not in roles:
        phases = [phase for phase in phases if phase != Phase.NIGHT_GUARD]
    if Role.HUNTER not in roles:
        phases = [phase for phase in phases if phase != Phase.NIGHT_HUNTER]
    if not flags.get("sheriff_enabled", True):
        phases = [phase for phase in phases if phase != Phase.SHERIFF_ELECTION]
    return phases


def compile_runtime_config(config: GameConfig) -> RuntimeConfig:
    enabled_role_set = {spec["role"] for spec in config["roles"] if spec["enabled"]}
    runtime = RuntimeConfig(
        config_id=config["config_id"],
        name=config["name"],
        player_count=config["player_count"],
        roles=deepcopy(config["roles"]),
        enabled_roles=enabled_role_set,
        enabled_tools=set(),
        phase_order=build_phase_order(config),
        rule_flags=deepcopy(config["rule_flags"]),
        prompt_profile=deepcopy(config["prompt_profile"]),
        tool_profile=deepcopy(config.get("tool_profile", {})),
    )
    runtime["enabled_tools"] = {tool["name"] for role in enabled_role_set for phase in runtime["phase_order"] for tool in enabled_tools(runtime, role, phase)}
    return runtime
