from __future__ import annotations

from app.domain.context import FactionContext, PromptContext, PublicContext, RolePrivateContext
from app.domain.roles import Faction, Role
from app.domain.state import GameState, alive_player_ids, living_wolves, snapshot_state


def build_public_context(state: GameState) -> PublicContext:
    return PublicContext(
        game_id=state["game_id"],
        phase=state["phase"],
        round=state["round"],
        alive_players=alive_player_ids(state),
        public_history=list(state["public_history"]),
        public_summary=_public_summary(state),
    )


def build_faction_context(state: GameState, *, player_id: int) -> FactionContext | None:
    player = state["players"][player_id]
    if player["faction"] == Faction.WOLF:
        teammates = [wolf_id for wolf_id in living_wolves(state) if wolf_id != player_id]
        return FactionContext(
            faction=Faction.WOLF,
            shared_memory=[event for event in state["private_history"] if event.get("scope") == "wolf_team"],
            visible_teammates=teammates,
        )
    return None


def build_private_context(state: GameState, *, player_id: int) -> RolePrivateContext:
    player = state["players"][player_id]
    return RolePrivateContext(
        player_id=player_id,
        role=player["role"],
        private_memory=list(player["private_memory"]),
        role_specific_state=_role_specific_state(state, player_id),
    )


def build_prompt_context(state: GameState, *, player_id: int) -> PromptContext:
    return PromptContext(
        public=build_public_context(state),
        faction=build_faction_context(state, player_id=player_id),
        private=build_private_context(state, player_id=player_id),
    )


def _role_specific_state(state: GameState, player_id: int) -> dict:
    player = state["players"][player_id]
    if player["role"] == Role.SEER:
        checks = [entry for entry in state["seer_checks"] if isinstance(entry, dict)]
        return {"seer_checks": checks}
    if player["role"] == Role.WITCH:
        antidote_this_night = bool(state["night_actions"].get("witch_use_antidote"))
        if antidote_this_night:
            antidote_status = "本晚你已使用了解药，不能再使用毒药。"
        else:
            antidote_status = "本晚你未使用解药，可以使用毒药。"
        witch_state: dict = {
            "antidote_used": state["witch_antidote_used"],
            "poison_used": state["witch_poison_used"],
            "antidote_used_this_night": antidote_this_night,
            "antidote_status": antidote_status,
        }
        # After antidote used (ever), witch is no longer told who was killed
        if not state["witch_antidote_used"]:
            witch_state["wolf_target"] = state["night_actions"].get("wolf_target")
        return witch_state
    if player["role"] == Role.HUNTER:
        return {"can_shoot": player["alive"] or player["death_cause"] in {"wolf", "exile"}}
    if player["role"] == Role.IDIOT:
        return {"idiot_revealed": player["idiot_revealed"], "can_vote": player["can_vote"]}
    return {}


def _public_summary(state: GameState) -> dict:
    alive = alive_player_ids(state)
    dead = [
        {
            "player_id": player_id,
            "death_round": player["death_round"],
            "death_cause": player["death_cause"],
        }
        for player_id, player in state["players"].items()
        if not player["alive"]
    ]
    recent_public_events = [
        {
            "phase": item.get("phase"),
            "event_type": item.get("event_type"),
            "data": item.get("data"),
        }
        for item in state["public_history"][-12:]
    ]
    recent_speeches = [
        {
            "player_id": item.get("player_id"),
            "round": item.get("round"),
            "content": item.get("content"),
        }
        for item in state["speech_log"][-12:]
    ]
    return {
        "round": state["round"],
        "phase": state["phase"].value,
        "alive_players": alive,
        "dead_players": dead,
        "sheriff_id": state["sheriff_id"],
        "last_night_deaths": state["night_result"].get("deaths", []),
        "last_vote_records": state["vote_records"],
        "last_vote_candidates": state["vote_candidates"],
        "recent_public_events": recent_public_events,
        "recent_speeches": recent_speeches,
    }
