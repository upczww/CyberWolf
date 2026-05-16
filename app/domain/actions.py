from __future__ import annotations

from typing import Literal, TypedDict

from app.domain.roles import Phase


class ProposedAction(TypedDict):
    actor_id: int
    phase: Phase
    tool_name: str
    raw_args: dict
    source: Literal["llm", "fallback"]


class ValidatedAction(TypedDict):
    actor_id: int
    phase: Phase
    action_type: str
    args: dict
    is_valid: bool
    validation_errors: list[str]


class ResolvedAction(TypedDict):
    actor_id: int
    phase: Phase
    action_type: str
    args: dict
    effects: list[dict]
