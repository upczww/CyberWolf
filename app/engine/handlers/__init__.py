"""Phase handlers registry.

Each handler takes (state, services) -> PhaseResult.
"""
from __future__ import annotations

from app.domain.roles import Phase
from app.domain.state import PhaseResult

from .day import handle_day_announce, handle_day_resolve, handle_day_speech, handle_day_vote
from .night import handle_night_hunter, handle_night_resolve, handle_night_seer, handle_night_start, handle_night_witch, handle_night_wolf
from .setup import handle_setup_game
from .sheriff import handle_sheriff_election
from .skills import handle_check_win, handle_game_over, handle_pending_skills

PHASE_HANDLERS = {
    Phase.SETUP_GAME: handle_setup_game,
    Phase.NIGHT_START: handle_night_start,
    Phase.NIGHT_WOLF: handle_night_wolf,
    Phase.NIGHT_SEER: handle_night_seer,
    Phase.NIGHT_WITCH: handle_night_witch,
    Phase.NIGHT_HUNTER: handle_night_hunter,
    Phase.NIGHT_RESOLVE: handle_night_resolve,
    Phase.DAY_ANNOUNCE: handle_day_announce,
    Phase.SHERIFF_ELECTION: handle_sheriff_election,
    Phase.DAY_SPEECH: handle_day_speech,
    Phase.DAY_VOTE: handle_day_vote,
    Phase.DAY_RESOLVE: handle_day_resolve,
    Phase.PENDING_SKILLS: handle_pending_skills,
    Phase.CHECK_WIN: handle_check_win,
    Phase.GAME_OVER: handle_game_over,
}

__all__ = ["PHASE_HANDLERS"]
