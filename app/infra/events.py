from __future__ import annotations

from collections.abc import Callable

from app.domain.events import GameEvent


Listener = Callable[[GameEvent], None]


class EventBus:
    def __init__(self) -> None:
        self._listeners: list[Listener] = []

    def subscribe(self, listener: Listener) -> None:
        self._listeners.append(listener)

    def publish(self, event: GameEvent) -> None:
        for listener in self._listeners:
            listener(event)
