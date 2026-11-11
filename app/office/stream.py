"""Flux d'événements du bureau virtuel.

Le flux est alimenté de deux façons complémentaires :

- **EventBus en mémoire** : quand le serveur tourne dans le même processus que
  le Manager, `attach_bus` branche directement les événements publiés ;
- **journal SQLite** : quand le gateway Telegram tourne dans un autre processus,
  les événements déjà persistés sont relus depuis la base.

Les identifiants d'événements sont uniques et croissants : un événement reçu
par les deux chemins n'est présenté qu'une seule fois.
"""

from __future__ import annotations

import threading
import time

from app.domain.models import Event
from app.events.bus import EventBus
from app.store.sqlite_store import SqliteStore


class OfficeEventStream:
    """File d'attente thread-safe des événements réels d'une mission."""

    def __init__(self, store: SqliteStore, mission_id: str) -> None:
        self.store = store
        self.mission_id = mission_id
        self._condition = threading.Condition()
        self._events: dict[int, Event] = {}

    def attach_bus(self, bus: EventBus) -> None:
        bus.subscribe(self._on_bus_event)

    def _on_bus_event(self, event: Event) -> None:
        if event.mission_id != self.mission_id or event.id is None:
            return
        with self._condition:
            self._events[int(event.id)] = event
            self._condition.notify_all()

    def _poll_store(self) -> None:
        for event in self.store.list_events(self.mission_id):
            if event.id is None:
                continue
            self._events.setdefault(int(event.id), event)

    def initial(self) -> list[Event]:
        with self._condition:
            self._poll_store()
            events = sorted(self._events.values(), key=lambda item: item.id or 0)
        return events

    def wait(self, after_id: int, timeout: float = 1.0) -> list[Event]:
        """Attend de nouveaux événements, sans jamais bloquer indéfiniment."""

        deadline = time.monotonic() + max(timeout, 0.0)
        with self._condition:
            self._poll_store()
            while not any((event.id or 0) > after_id for event in self._events.values()):
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                self._condition.wait(remaining)
                self._poll_store()
            events = [
                event
                for event in self._events.values()
                if (event.id or 0) > after_id
            ]
        events.sort(key=lambda item: item.id or 0)
        return events
