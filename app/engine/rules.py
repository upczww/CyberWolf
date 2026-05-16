from __future__ import annotations

from app.domain.config import RuntimeConfig
from app.domain.roles import Faction, Role, ROLE_TO_FACTION
from app.domain.state import GameState


GOD_ROLES: set[Role] = {Role.SEER, Role.WITCH, Role.HUNTER, Role.IDIOT}
VILLAGER_ROLES: set[Role] = {Role.VILLAGER}


def check_win(state: GameState, runtime: RuntimeConfig) -> tuple[str | None, str | None]:
    """Returns (winner, reason). winner is 'good'/'wolf'/None. reason is a human-readable string."""
    alive = [player for player in state["players"].values() if player["alive"]]

    if not alive:
        return None, None

    alive_roles = [player["role"] for player in alive]
    alive_wolves = sum(1 for role in alive_roles if role == Role.WOLF)

    # All wolves dead -> good wins
    if alive_wolves == 0:
        return "good", "all_wolves_dead"

    # Only wolves alive -> wolf wins
    if alive_wolves == len(alive):
        return "wolf", "wolves_majority"

    # Slaughter-side (屠边): check if all gods OR all villagers are dead
    # Revealed idiot still counts as alive god for this check
    alive_gods = sum(1 for role in alive_roles if role in GOD_ROLES)
    alive_villagers = sum(1 for role in alive_roles if role in VILLAGER_ROLES)

    if alive_gods == 0:
        return "wolf", "slaughter_gods"

    if alive_villagers == 0:
        return "wolf", "slaughter_villagers"

    return None, None
