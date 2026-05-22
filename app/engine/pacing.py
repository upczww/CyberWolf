from __future__ import annotations

import asyncio
from time import monotonic
from typing import Any

from app.domain.roles import Phase


MIN_VISIBLE_ACTION_HOLD_SECONDS = 1.2

_PHASE_MAX_SECONDS: dict[str, float] = {
    Phase.SETUP_GAME.value: 30.0,
    Phase.NIGHT_START.value: 15.0,
    Phase.NIGHT_WOLF.value: 30.0,
    Phase.NIGHT_SEER.value: 30.0,
    Phase.NIGHT_WITCH.value: 60.0,
    Phase.NIGHT_GUARD.value: 30.0,
    Phase.NIGHT_RESOLVE.value: 30.0,
    Phase.SHERIFF_ELECTION.value: 180.0,
    Phase.DAY_ANNOUNCE.value: 30.0,
    Phase.DAY_SPEECH.value: 180.0,
    Phase.DAY_VOTE.value: 120.0,
    Phase.DAY_RESOLVE.value: 30.0,
    Phase.PENDING_SKILLS.value: 60.0,
    Phase.CHECK_WIN.value: 10.0,
    Phase.GAME_OVER.value: 10.0,
}


def _phase_value(phase: Phase | str) -> str:
    return phase.value if isinstance(phase, Phase) else str(phase)


def phase_max_seconds(phase: Phase | str) -> float:
    return _PHASE_MAX_SECONDS.get(_phase_value(phase), 60.0)


def start_phase_budget(services: Any, phase: Phase | str) -> None:
    now = monotonic()
    services._phase_started_at = now
    services._phase_deadline_at = now + phase_max_seconds(phase)


def set_phase_deadline(services: Any, seconds_from_now: float) -> None:
    """Re-arm the current phase's deadline.

    Used by multi-actor phases (day_speech / day_vote / sheriff_election)
    to scale the ceiling by participant count so no speaker or voter is
    truncated by the static per-phase max. The budget is a CEILING, not
    a floor: AI actors finish in well under their slice, so a generous
    ceiling never slows an AI game — it only guarantees a human actor
    gets their full per-tool thinking window. Individual LLM calls are
    independently bounded by ``LLMSettings.timeout_seconds``, so a large
    ceiling cannot let a single hung call run away.
    """
    services._phase_deadline_at = monotonic() + max(0.0, float(seconds_from_now))


def phase_remaining_seconds(services: Any) -> float | None:
    deadline = getattr(services, "_phase_deadline_at", None)
    if deadline is None:
        return None
    return max(0.0, float(deadline) - monotonic())


def phase_has_time(services: Any, *, minimum_seconds: float = 0.25) -> bool:
    remaining = phase_remaining_seconds(services)
    return remaining is None or remaining > minimum_seconds


async def hold_visible_action(
    started_at: float,
    services: Any,
    *,
    min_seconds: float = MIN_VISIBLE_ACTION_HOLD_SECONDS,
) -> None:
    elapsed = monotonic() - started_at
    remaining_hold = min_seconds - elapsed
    if remaining_hold <= 0:
        return
    phase_remaining = phase_remaining_seconds(services)
    if phase_remaining is not None:
        remaining_hold = min(remaining_hold, phase_remaining)
    if remaining_hold > 0:
        await asyncio.sleep(remaining_hold)
