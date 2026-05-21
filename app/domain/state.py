from __future__ import annotations

from copy import deepcopy
from random import Random
from typing import TypedDict
from uuid import uuid4

from app.domain.actions import ResolvedAction
from app.domain.config import RuntimeConfig
from app.domain.events import GameEvent
from app.domain.roles import Faction, GameStatus, Phase, Role, ROLE_TO_FACTION


class PlayerState(TypedDict):
    id: int
    role: Role
    faction: Faction
    alive: bool
    can_vote: bool
    is_sheriff: bool
    idiot_revealed: bool
    death_round: int | None
    death_cause: str | None
    private_memory: list[dict]


class PendingSkill(TypedDict):
    kind: str
    actor_id: int
    context: dict


class PhaseResult(TypedDict, total=False):
    state_patch: dict
    events: list[GameEvent]
    persisted_event_count: int
    pending_skills: list[PendingSkill]
    next_phase_override: Phase | None
    snapshots: list[dict]
    actions: list[ResolvedAction]
    skip_phase: bool


class GameState(TypedDict):
    game_id: str
    config_id: str
    runtime: RuntimeConfig
    phase_index: int
    phase: Phase
    round: int
    day_index: int
    status: GameStatus
    players: dict[int, PlayerState]
    sheriff_id: int | None
    winner: str | None
    ended: bool
    public_history: list[dict]
    private_history: list[dict]
    dead_history: list[dict]
    pending_skills: list[PendingSkill]
    night_actions: dict
    night_result: dict
    seer_checks: list[dict]
    witch_antidote_used: bool
    witch_poison_used: bool
    speech_order: list[int]
    speech_log: list[dict]
    vote_round: int
    vote_candidates: list[int]
    vote_records: dict[int, int | None]
    exile_tie_count: int
    sheriff_speech_clockwise: bool | None
    llm_stats: dict
    seed: int
    graph_artifacts: dict[str, str | None]
    # Primary human seat for legacy single-human modes (personal mode,
    # confirm_identity flow). None in god/observer mode and in multi-
    # human lobby games where there's no single "host" seat distinction.
    human_seat: int | None
    # Full set of seats controlled by humans. Single-human modes set
    # this to {human_seat}. Multi-human lobby games can have 2..12
    # entries. Empty set = pure AI game (god/observer view).
    human_seats: set[int]


def alive_player_ids(state: GameState) -> list[int]:
    return [player_id for player_id, player in state["players"].items() if player["alive"]]


def living_wolves(state: GameState) -> list[int]:
    return [
        player_id
        for player_id, player in state["players"].items()
        if player["alive"] and player["role"] == Role.WOLF
    ]



def build_players(runtime: RuntimeConfig, *, seed: int) -> dict[int, PlayerState]:
    roles: list[Role] = []
    for spec in runtime["roles"]:  # type: ignore[index]
        roles.extend([spec["role"]] * spec["count"])
    Random(seed).shuffle(roles)
    players: dict[int, PlayerState] = {}
    for idx, role in enumerate(roles, start=1):
        players[idx] = PlayerState(
            id=idx,
            role=role,
            faction=ROLE_TO_FACTION[role],
            alive=True,
            can_vote=True,
            is_sheriff=False,
            idiot_revealed=False,
            death_round=None,
            death_cause=None,
            private_memory=[],
        )
    return players


def init_game_state(
    runtime: RuntimeConfig,
    *,
    game_id: str | None = None,
    seed: int = 0,
    graph_artifacts: dict[str, str | None] | None = None,
    human_seat: int | None = None,
    human_seats: set[int] | None = None,
) -> GameState:
    phase = runtime["phase_order"][0]
    return GameState(
        game_id=game_id or str(uuid4()),
        config_id=runtime["config_id"],
        runtime=deepcopy(runtime),
        phase_index=0,
        phase=phase,
        round=1,
        day_index=1,
        status=GameStatus.RUNNING,
        players=build_players(runtime, seed=seed),
        sheriff_id=None,
        winner=None,
        ended=False,
        public_history=[],
        private_history=[],
        dead_history=[],
        pending_skills=[],
        night_actions={},
        night_result={},
        seer_checks=[],
        witch_antidote_used=False,
        witch_poison_used=False,
        speech_order=[],
        speech_log=[],
        vote_round=1,
        vote_candidates=[],
        vote_records={},
        exile_tie_count=0,
        sheriff_speech_clockwise=None,
        llm_stats={},
        seed=seed,
        graph_artifacts=graph_artifacts or {},
        human_seat=human_seat,
        human_seats=set(human_seats) if human_seats is not None else (
            {human_seat} if human_seat is not None else set()
        ),
    )


def apply_state_patch(state: GameState, patch: dict) -> GameState:
    updated = deepcopy(state)
    _deep_merge(updated, patch)
    return updated


def _deep_merge(target: dict, patch: dict) -> None:
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            _deep_merge(target[key], value)
        else:
            target[key] = value


def next_phase(state: GameState) -> Phase:
    idx = state["phase_index"] + 1
    if idx >= len(state["runtime"]["phase_order"]):
        return Phase.GAME_OVER
    return state["runtime"]["phase_order"][idx]


def snapshot_state(state: GameState) -> dict:
    return {
        "game_id": state["game_id"],
        "config_id": state["config_id"],
        "phase": state["phase"],
        "phase_index": state["phase_index"],
        "round": state["round"],
        "day_index": state["day_index"],
        "status": state["status"],
        "sheriff_id": state["sheriff_id"],
        "winner": state["winner"],
        "players": {
            player_id: {
                "alive": player["alive"],
                "role": player["role"],
                "faction": player["faction"],
                "can_vote": player["can_vote"],
                "is_sheriff": player["is_sheriff"],
                "idiot_revealed": player["idiot_revealed"],
                "death_round": player["death_round"],
                "death_cause": player["death_cause"],
            }
            for player_id, player in state["players"].items()
        },
        "pending_skills": deepcopy(state["pending_skills"]),
        "night_actions": deepcopy(state["night_actions"]),
        "night_result": deepcopy(state["night_result"]),
        "seer_checks": deepcopy(state["seer_checks"]),
        "witch_antidote_used": state["witch_antidote_used"],
        "witch_poison_used": state["witch_poison_used"],
        "vote_round": state["vote_round"],
        "vote_candidates": deepcopy(state["vote_candidates"]),
        "vote_records": deepcopy(state["vote_records"]),
        "exile_tie_count": state["exile_tie_count"],
        "sheriff_speech_clockwise": state["sheriff_speech_clockwise"],
        "seed": state["seed"],
    }
