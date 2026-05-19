"""Human player input awaiter.

When a phase handler needs a decision and the actor is the human-controlled seat,
it asks `HumanAwaiter.wait_for_action(...)` which:
- emits an `awaiting_human` event via the EventBus (so the frontend can render an
  action panel for the correct seat),
- awaits an `asyncio.Future` that the API endpoint `/api/games/{gid}/human_action`
  fulfills with `submit(...)`,
- falls back to `local_args` on timeout (the standard LLM-failure fallback path).

This module is intentionally engine-internal — server/api.py just calls
`HumanAwaiter.submit(...)` to inject the human's choice.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

_log = logging.getLogger(__name__)


@dataclass(slots=True)
class _Pending:
    future: asyncio.Future
    tool_name: str
    actor_id: int
    phase: str
    timeout_seconds: float


class HumanAwaiter:
    """Per-game registry of pending human-input futures.

    Only one outstanding request per (actor_id, tool_name) — the engine is
    sequential per game anyway. Submit a result and the awaiter resolves it
    without applying any validation here (validation/resolution happens in the
    standard phase-handler pipeline).
    """

    def __init__(self) -> None:
        self._pending: dict[str, _Pending] = {}
        self._lock = asyncio.Lock()

    @staticmethod
    def _key(actor_id: int, tool_name: str) -> str:
        return f"{actor_id}:{tool_name}"

    async def wait_for_action(
        self,
        *,
        actor_id: int,
        tool_name: str,
        phase: str,
        local_args: dict,
        timeout_seconds: float = 60.0,
    ) -> dict:
        """Block until the human submits an action or timeout fires.

        Returns the submitted args dict, or `local_args` on timeout.
        """
        key = self._key(actor_id, tool_name)
        loop = asyncio.get_running_loop()
        async with self._lock:
            old = self._pending.pop(key, None)
            if old is not None and not old.future.done():
                old.future.cancel()
            future: asyncio.Future = loop.create_future()
            self._pending[key] = _Pending(
                future=future,
                tool_name=tool_name,
                actor_id=actor_id,
                phase=phase,
                timeout_seconds=timeout_seconds,
            )
        try:
            args = await asyncio.wait_for(future, timeout=timeout_seconds)
            if not isinstance(args, dict):
                _log.warning("human submit returned non-dict for %s, falling back", key)
                return local_args
            return args
        except asyncio.TimeoutError:
            _log.info("human input timeout for actor %s tool %s, using fallback", actor_id, tool_name)
            return local_args
        except asyncio.CancelledError:
            return local_args
        finally:
            async with self._lock:
                self._pending.pop(key, None)

    def pending_snapshot(self) -> list[dict]:
        """Return a serializable list of currently awaiting actions (for reconnect)."""
        return [
            {"actor_id": p.actor_id, "tool_name": p.tool_name, "phase": p.phase}
            for p in self._pending.values()
        ]

    async def submit(self, *, actor_id: int, tool_name: str, args: dict) -> bool:
        """Resolve a pending future. Returns True if a future was waiting."""
        key = self._key(actor_id, tool_name)
        async with self._lock:
            pending = self._pending.get(key)
            if pending is None or pending.future.done():
                return False
            pending.future.set_result(args)
            return True

    async def cancel_all(self) -> None:
        async with self._lock:
            for pending in self._pending.values():
                if not pending.future.done():
                    pending.future.cancel()
            self._pending.clear()
