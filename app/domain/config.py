from __future__ import annotations

from typing import Literal, TypedDict

from app.domain.roles import Phase, Role, WinRule


class RoleSpec(TypedDict):
    role: Role
    count: int
    enabled: bool


class RuleFlags(TypedDict, total=False):
    sheriff_enabled: bool
    witch_can_self_save_first_night: bool
    hunter_can_shoot_if_poisoned: bool
    idiot_survives_exile: bool
    second_tie_enters_night: bool


class PromptProfile(TypedDict, total=False):
    prompt_set: str
    max_public_speech_chars: int
    include_internal_thought: bool
    templates: dict[str, str]
    output_modes: dict[str, str]


class ToolProfile(TypedDict, total=False):
    enabled_tools: list[str]
    disabled_tools: list[str]
    tool_overrides: dict[str, dict]


class GameConfig(TypedDict):
    config_id: str
    name: str
    player_count: int
    roles: list[RoleSpec]
    rule_flags: RuleFlags
    phase_order: list[Phase]
    win_rule: WinRule
    prompt_profile: PromptProfile
    tool_profile: ToolProfile


class RuntimeConfig(TypedDict):
    config_id: str
    name: str
    player_count: int
    roles: list[RoleSpec]
    enabled_roles: set[Role]
    enabled_tools: set[str]
    phase_order: list[Phase]
    rule_flags: RuleFlags
    prompt_profile: PromptProfile
    tool_profile: ToolProfile


class ToolSpec(TypedDict):
    name: str
    description: str
    input_schema: dict
    enabled_roles: list[Role]
    enabled_phases: list[Phase]
    output_mode: Literal["tool_call"]
