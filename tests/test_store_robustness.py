from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

import pytest

from app.domain.models import Mission, Task
from app.store.sqlite_store import (
    BUSY_TIMEOUT_MS,
    LOCK_RETRY_DELAY_SECONDS,
    MAX_LOCK_RETRIES,
    SqliteStore,
    StorageError,
)


@pytest.fixture()
def store(tmp_path: Path) -> SqliteStore:
    return SqliteStore(tmp_path / "missions.db")


def test_wal_timeout_and_foreign_keys_are_enabled(store: SqliteStore) -> None:
    with store._read() as connection:
        journal_mode = connection.execute("PRAGMA journal_mode").fetchone()[0]
        busy_timeout = connection.execute("PRAGMA busy_timeout").fetchone()[0]
        foreign_keys = connection.execute("PRAGMA foreign_keys").fetchone()[0]
        synchronous = connection.execute("PRAGMA synchronous").fetchone()[0]

    assert journal_mode.lower() == "wal"
    assert busy_timeout == BUSY_TIMEOUT_MS
    assert foreign_keys == 1
    assert synchronous == 1  # NORMAL


def test_foreign_keys_reject_orphan_tasks(store: SqliteStore) -> None:
    orphan = Task(
        mission_id="mission-absente",
        key="analysis",
        agent="qa_analyst",
        title="Tâche orpheline",
    )

    with pytest.raises(StorageError):
        store.create_task(orphan)

    assert store.list_orphan_tasks() == []


def test_write_retries_after_transient_lock(
    store: SqliteStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    real_connect = store._connect
    calls = {"count": 0}

    def flaky_connect():
        calls["count"] += 1
        if calls["count"] <= 2:
            raise sqlite3.OperationalError("database is locked")
        return real_connect()

    monkeypatch.setattr(store, "_connect", flaky_connect)

    mission = store.create_mission(Mission(instruction="Mission après verrou"))

    assert calls["count"] == 3
    assert store.get_mission(mission.id) is not None


def test_write_gives_up_after_bounded_retries(
    store: SqliteStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    def always_locked():
        raise sqlite3.OperationalError("database is locked")

    delays: list[float] = []
    monkeypatch.setattr(store, "_connect", always_locked)
    monkeypatch.setattr(
        "app.store.sqlite_store.time.sleep", lambda delay: delays.append(delay)
    )

    with pytest.raises(StorageError) as error:
        store.create_mission(Mission(instruction="Mission bloquée"))

    assert "verrouillée" in str(error.value)
    # Une tentative initiale + MAX_LOCK_RETRIES reprises, jamais plus.
    assert len(delays) == MAX_LOCK_RETRIES
    assert delays == [
        LOCK_RETRY_DELAY_SECONDS * attempt
        for attempt in range(1, MAX_LOCK_RETRIES + 1)
    ]


def test_corrupted_database_raises_a_clear_storage_error(tmp_path: Path) -> None:
    path = tmp_path / "corrompue.db"
    path.write_bytes(b"ceci n'est pas une base sqlite\n" * 32)

    with pytest.raises(StorageError) as error:
        SqliteStore(path)

    message = str(error.value)
    assert "corrompue" in message or "illisible" in message
    assert str(path) in message


def test_read_only_store_reports_corruption_without_writing(tmp_path: Path) -> None:
    path = tmp_path / "corrompue.db"
    path.write_bytes(b"pas une base sqlite" * 16)
    before = path.read_bytes()

    store = SqliteStore(path, read_only=True)
    with pytest.raises(StorageError):
        store.list_missions()

    assert path.read_bytes() == before


def test_read_only_store_never_creates_a_missing_file(tmp_path: Path) -> None:
    path = tmp_path / "absente.db"

    SqliteStore(path, read_only=True)

    assert not path.exists()


def test_read_only_store_does_not_mutate_the_database(
    store: SqliteStore,
) -> None:
    mission = store.create_mission(Mission(instruction="Mission stable"))
    before = store.path.read_bytes()

    read_only = SqliteStore(store.path, read_only=True)
    assert [item.id for item in read_only.list_missions()] == [mission.id]
    assert read_only.list_tasks(mission.id) == []

    assert store.path.read_bytes() == before


def test_concurrent_readers_and_writers_share_the_store(
    store: SqliteStore,
) -> None:
    errors: list[BaseException] = []
    created: list[str] = []
    lock = threading.Lock()

    def writer(index: int) -> None:
        try:
            for item in range(5):
                mission = store.create_mission(
                    Mission(instruction=f"Mission {index}-{item}")
                )
                with lock:
                    created.append(mission.id)
        except BaseException as exc:  # pragma: no cover - signalé ci-dessous
            with lock:
                errors.append(exc)

    def reader() -> None:
        try:
            for _ in range(10):
                store.list_missions()
        except BaseException as exc:  # pragma: no cover - signalé ci-dessous
            with lock:
                errors.append(exc)

    threads = [
        threading.Thread(target=writer, args=(index,)) for index in range(4)
    ] + [threading.Thread(target=reader) for _ in range(3)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=20)

    assert not errors
    assert len(created) == 20
    assert {mission.id for mission in store.list_missions()} == set(created)


def test_two_store_instances_can_write_sequentially(tmp_path: Path) -> None:
    path = tmp_path / "missions.db"
    first = SqliteStore(path)
    second = SqliteStore(path)

    first_mission = first.create_mission(Mission(instruction="Depuis le premier"))
    second_mission = second.create_mission(Mission(instruction="Depuis le second"))

    assert {item.id for item in first.list_missions()} == {
        first_mission.id,
        second_mission.id,
    }
