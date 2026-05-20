from __future__ import annotations

from enum import StrEnum


class Role(StrEnum):
    WOLF = "wolf"
    SEER = "seer"
    WITCH = "witch"
    HUNTER = "hunter"
    IDIOT = "idiot"
    GUARD = "guard"
    VILLAGER = "villager"


class Faction(StrEnum):
    WOLF = "wolf"
    GOOD = "good"


class Phase(StrEnum):
    SETUP_GAME = "setup_game"
    NIGHT_START = "night_start"
    NIGHT_WOLF = "night_wolf"
    NIGHT_SEER = "night_seer"
    NIGHT_WITCH = "night_witch"
    NIGHT_GUARD = "night_guard"
    NIGHT_RESOLVE = "night_resolve"
    DAY_ANNOUNCE = "day_announce"
    SHERIFF_ELECTION = "sheriff_election"
    DAY_SPEECH = "day_speech"
    DAY_VOTE = "day_vote"
    DAY_RESOLVE = "day_resolve"
    PENDING_SKILLS = "pending_skills"
    CHECK_WIN = "check_win"
    GAME_OVER = "game_over"


class EventScope(StrEnum):
    PUBLIC = "public"
    WOLF_TEAM = "wolf_team"
    ROLE_PRIVATE = "role_private"
    GOD = "god"
    SYSTEM = "system"


class EventType(StrEnum):
    PHASE_STARTED = "phase_started"
    PHASE_ENDED = "phase_ended"
    PLAYER_DIED = "player_died"
    WOLF_TARGET_SELECTED = "wolf_target_selected"
    SEER_CHECKED = "seer_checked"
    WITCH_USED_ANTIDOTE = "witch_used_antidote"
    WITCH_USED_POISON = "witch_used_poison"
    PUBLIC_SPEECH_MADE = "public_speech_made"
    SPEAKING_STARTED = "speaking_started"
    VOTE_CAST = "vote_cast"
    VOTE_RESOLVED = "vote_resolved"
    SKILL_TRIGGERED = "skill_triggered"
    SHERIFF_TRANSFERRED = "sheriff_transferred"
    SHERIFF_ELECTED = "sheriff_elected"
    SPEECH_ORDER_ANNOUNCED = "speech_order_announced"
    DEATH_SPEECH = "death_speech"
    SHERIFF_CAMPAIGN = "sheriff_campaign"
    SHERIFF_DECLARE = "sheriff_declare"
    SHERIFF_DIRECTION = "sheriff_direction"
    WOLF_SELF_DESTRUCT = "wolf_self_destruct"
    GAME_ENDED = "game_ended"
    ERROR_RAISED = "error_raised"
    AWAITING_HUMAN = "awaiting_human"
    HUMAN_SUBMITTED = "human_submitted"
    NARRATION = "narration"  # backend-authored player-facing narration text


class WinRule(StrEnum):
    SLAUGHTER_SIDE = "slaughter_side"


class GameStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


ROLE_TO_FACTION: dict[Role, Faction] = {
    Role.WOLF: Faction.WOLF,
    Role.SEER: Faction.GOOD,
    Role.WITCH: Faction.GOOD,
    Role.HUNTER: Faction.GOOD,
    Role.IDIOT: Faction.GOOD,
    Role.GUARD: Faction.GOOD,
    Role.VILLAGER: Faction.GOOD,
}
