"""Phase handlers — registered via @phase decorator at import time.

Each handler module decorates its handlers with `@phase(...)` from
`app.engine.registry`, populating `PHASE_REGISTRY` as a side effect.

Importing this package guarantees every built-in handler is on the
registry. External plugins can import `app.engine.registry` and use
the same decorator to add their own phases without touching this
package.
"""
from __future__ import annotations

# Importing each handler module runs the @phase decorators, populating
# PHASE_REGISTRY. Order doesn't matter — registration is by id.
from . import day, night, setup, sheriff, skills  # noqa: F401

# Legacy export: build PHASE_HANDLERS from the registry for any
# callers that still expect a {Phase: handler} dict. Engine itself
# now reads from PHASE_REGISTRY directly.
from app.domain.roles import Phase
from app.engine.registry import PHASE_REGISTRY


def _build_legacy_handlers() -> dict:
    out = {}
    for phase_id, spec in PHASE_REGISTRY.items():
        try:
            out[Phase(phase_id)] = spec.handler
        except ValueError:
            # Plugin phase id not in the Phase enum — engine still
            # finds it via PHASE_REGISTRY directly.
            pass
    return out


PHASE_HANDLERS = _build_legacy_handlers()

__all__ = ["PHASE_HANDLERS", "PHASE_REGISTRY"]
