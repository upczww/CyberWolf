from __future__ import annotations

from typing import TypedDict

from app.domain.roles import Faction, Phase, Role


class PublicContext(TypedDict):
    game_id: str
    phase: Phase
    round: int
    alive_players: list[int]
    public_history: list[dict]
    public_summary: str


class FactionContext(TypedDict):
    faction: Faction
    shared_memory: list[dict]
    visible_teammates: list[int]


class RolePrivateContext(TypedDict):
    player_id: int
    role: Role
    private_memory: list[dict]
    role_specific_state: dict


class GodContext(TypedDict):
    full_state: dict
    hidden_roles: dict[int, Role]
    debug_notes: list[dict]


class PromptContext(TypedDict):
    public: PublicContext
    faction: FactionContext | None
    private: RolePrivateContext
