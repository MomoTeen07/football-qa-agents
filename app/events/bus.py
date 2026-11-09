from __future__ import annotations

from collections.abc import Callable

from app.domain.models import Event
from app.store.sqlite_store import SqliteStore

Subscriber = Callable[[Event], None]


class EventBus:
    """Journal d'événements réel du système.

    Le bureau virtuel et les rapports consommeront ces événements.
    Aucun événement décoratif n'est publié ici.
    """

    def __init__(self, store: SqliteStore) -> None:
        self.store = store
        self._subscribers: list[Subscriber] = []

    def subscribe(self, subscriber: Subscriber) -> None:
        self._subscribers.append(subscriber)

    def publish(
        self,
        mission_id: str,
        event_type: str,
        *,
        agent: str | None = None,
        payload: dict | None = None,
    ) -> Event:
        event = self.store.add_event(
            Event(
                mission_id=mission_id,
                type=event_type,
                agent=agent,
                payload=payload or {},
            )
        )
        for subscriber in list(self._subscribers):
            subscriber(event)
        return event
