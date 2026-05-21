"""Phase registry built on `transitions.State`.

Each game phase is a `PhaseState` — a subclass of `transitions.State`
that carries everything the engine needs at runtime:

  * `on_enter` callback fires the handler (via `GameSession._on_enter_phase`).
  * Custom attrs (`handler`, `narration`, `requires_role`, `requires_flag`)
    hold the metadata previously in a parallel `PhaseSpec` dataclass.

Result: the `transitions` library's `State` infrastructure IS the
phase registry. There is no parallel dict-of-dataclasses to maintain.

Built-in phases (defined in `app/engine/handlers/*.py`) populate the
registry at import time via the `@phase(...)` decorator. External
plugins can register new phases by importing this module and applying
the same decorator.
"""
from __future__ import annotations

from typing import Awaitable, Callable, TYPE_CHECKING

from transitions.extensions.asyncio import AsyncState

from app.domain.roles import Phase, Role

if TYPE_CHECKING:
    from app.domain.state import GameState, PhaseResult
    from app.engine.session import SessionServices

HandlerFn = Callable[["GameState", "SessionServices"], Awaitable["PhaseResult"]]


# Shared on_enter callback name. The model (GameSession) implements
# `_on_enter_phase` — a single generic dispatcher that reads the
# current PhaseState's `handler` and runs it.
_ON_ENTER_CALLBACK = "_on_enter_phase"


class PhaseState(AsyncState):
    """transitions State subclass with engine-specific metadata.

    Attributes:
      handler:       async function (state, services) -> PhaseResult.
      narration:     optional (kind, text_template) — the intro
                     PhaseFlash for this phase. `{round}` is substituted
                     by the engine before emit. None = silent phase.
      requires_role: if set, the phase is auto-pruned from `phase_order`
                     when this role isn't enabled in the current ruleset.
      requires_flag: if set, the phase is auto-pruned when the rule
                     flag is falsy (e.g. sheriff_election needs
                     sheriff_enabled).
    """

    def __init__(
        self,
        name: str,
        *,
        handler: HandlerFn,
        narration: tuple[str, str] | None = None,
        requires_role: Role | None = None,
        requires_flag: str | None = None,
    ) -> None:
        super().__init__(name, on_enter=[_ON_ENTER_CALLBACK])
        self.handler = handler
        self.narration = narration
        self.requires_role = requires_role
        self.requires_flag = requires_flag


# Mutable registry of phase id -> PhaseState. Populated at import time
# by the @phase decorator. The engine and config_loader both read from
# here; `GameSession` also passes these instances directly into the
# AsyncMachine, so transitions library uses our subclass instead of
# constructing bare State objects.
PHASE_REGISTRY: dict[str, PhaseState] = {}


def phase(
    id: str | Phase,
    *,
    narration: tuple[str, str] | None = None,
    requires_role: Role | None = None,
    requires_flag: str | None = None,
) -> Callable[[HandlerFn], HandlerFn]:
    """Decorator that registers a phase handler as a PhaseState.

    Usage:
        @phase(Phase.NIGHT_WOLF, narration=("wolf", "狼人请睁眼..."))
        async def handle_night_wolf(state, services): ...

    Multiple calls with the same id replace the previous registration
    (last-wins) — handy for plugins that override a built-in phase.
    """
    id_str = id.value if isinstance(id, Phase) else str(id)

    def wrap(fn: HandlerFn) -> HandlerFn:
        PHASE_REGISTRY[id_str] = PhaseState(
            name=id_str,
            handler=fn,
            narration=narration,
            requires_role=requires_role,
            requires_flag=requires_flag,
        )
        return fn

    return wrap


def get_spec(phase_id: str | Phase) -> PhaseState | None:
    key = phase_id.value if isinstance(phase_id, Phase) else str(phase_id)
    return PHASE_REGISTRY.get(key)


def prune_phases(
    phase_ids: list,
    *,
    enabled_roles: set[Role],
    rule_flags: dict,
) -> list:
    """Drop phases whose `requires_role` / `requires_flag` aren't met.

    Reads the PhaseState attributes attached at decoration time. Phase
    ids not present in the registry pass through unchanged.
    """
    result = []
    for pid in phase_ids:
        spec = get_spec(pid)
        if spec is None:
            result.append(pid)
            continue
        if spec.requires_role is not None and spec.requires_role not in enabled_roles:
            continue
        if spec.requires_flag is not None and not rule_flags.get(spec.requires_flag, True):
            continue
        result.append(pid)
    return result
