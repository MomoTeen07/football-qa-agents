"""Stockage SQLite local du pilotage QA (durci en phase 9)."""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from app.domain.models import (
    Event,
    Mission,
    MissionStatus,
    Task,
    TaskStatus,
    utcnow,
)

# Réglages de robustesse (WP3). Les valeurs restent modestes pour un usage
# local mono-utilisateur : WAL permet la lecture pendant l'écriture, le
# busy_timeout évite les échecs immédiats, et le retry couvre les collisions
# résiduelles entre processus (gateway, bureau, scripts).
BUSY_TIMEOUT_MS = 5_000
MAX_LOCK_RETRIES = 3
LOCK_RETRY_DELAY_SECONDS = 0.1


class StorageError(RuntimeError):
    """Erreur de stockage explicite, destinée à l'utilisateur."""


class SqliteStore:
    """Stockage local des missions, tâches et événements.

    Le fichier SQLite est indépendant de la base PostgreSQL de l'application
    testée. Il ne contient que les données de pilotage QA.

    En mode ``read_only``, aucune écriture n'est possible : pas de création de
    dossier, pas de schéma, pas de PRAGMA WAL. Ce mode est utilisé par
    ``python -m app.cli doctor`` pour garantir un diagnostic sans mutation.
    """

    def __init__(self, path: Path, *, read_only: bool = False) -> None:
        self.path = Path(path)
        self.read_only = read_only
        self._lock = threading.RLock()
        if not read_only:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._init_db()

    # ------------------------------------------------------------------
    # Connexions
    # ------------------------------------------------------------------
    def _connect(self) -> sqlite3.Connection:
        if self.read_only:
            uri = f"{self.path.resolve().as_uri()}?mode=ro"
            connection = sqlite3.connect(
                uri,
                uri=True,
                timeout=BUSY_TIMEOUT_MS / 1000,
            )
        else:
            connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute(f"PRAGMA busy_timeout={BUSY_TIMEOUT_MS}")
            connection.execute("PRAGMA foreign_keys=ON")
            if not self.read_only:
                connection.execute("PRAGMA journal_mode=WAL")
                connection.execute("PRAGMA synchronous=NORMAL")
        except sqlite3.DatabaseError as exc:
            connection.close()
            raise StorageError(
                "Base SQLite locale illisible ou corrompue "
                f"({self.path}). Vérifiez le fichier ou restaurez une sauvegarde."
            ) from exc
        return connection

    @contextmanager
    def _read(self) -> Iterator[sqlite3.Connection]:
        connection = self._connect()
        try:
            yield connection
        except sqlite3.DatabaseError as exc:
            raise StorageError(
                "Lecture SQLite impossible : base illisible ou corrompue "
                f"({self.path}). Vérifiez le fichier ou restaurez une sauvegarde."
            ) from exc
        finally:
            connection.close()

    @contextmanager
    def _write(self, operation: str) -> Iterator[sqlite3.Connection]:
        """Connexion d'écriture avec retry borné sur ``database is locked``."""

        attempt = 0
        while True:
            try:
                with self._lock:
                    connection = self._connect()
                    try:
                        yield connection
                        connection.commit()
                    except Exception:
                        connection.rollback()
                        raise
                    finally:
                        connection.close()
                return
            except sqlite3.OperationalError as exc:
                if "locked" not in str(exc).lower() or attempt >= MAX_LOCK_RETRIES:
                    raise StorageError(
                        f"Écriture SQLite impossible ({operation}) : base "
                        "verrouillée par un autre processus. Réessayez après "
                        "la fin de l'opération en cours."
                    ) from exc
                attempt += 1
                time.sleep(LOCK_RETRY_DELAY_SECONDS * attempt)
            except sqlite3.DatabaseError as exc:
                raise StorageError(
                    f"Écriture SQLite impossible ({operation}) : base "
                    f"illisible ou corrompue ({self.path})."
                ) from exc

    def _init_db(self) -> None:
        try:
            with self._write("initialisation") as connection:
                connection.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS missions (
                        id TEXT PRIMARY KEY,
                        instruction TEXT NOT NULL,
                        status TEXT NOT NULL,
                        requires_approval INTEGER NOT NULL DEFAULT 0,
                        approval_reason TEXT,
                        report_path TEXT,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    );

                    CREATE TABLE IF NOT EXISTS tasks (
                        id TEXT PRIMARY KEY,
                        mission_id TEXT NOT NULL,
                        key TEXT NOT NULL,
                        agent TEXT NOT NULL,
                        title TEXT NOT NULL,
                        status TEXT NOT NULL,
                        depends_on TEXT NOT NULL,
                        result TEXT,
                        evidence TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        FOREIGN KEY (mission_id) REFERENCES missions(id)
                    );

                    CREATE TABLE IF NOT EXISTS events (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        mission_id TEXT NOT NULL,
                        type TEXT NOT NULL,
                        agent TEXT,
                        payload TEXT NOT NULL,
                        created_at TEXT NOT NULL
                    );

                    CREATE INDEX IF NOT EXISTS idx_tasks_mission
                        ON tasks(mission_id);
                    CREATE INDEX IF NOT EXISTS idx_events_mission
                        ON events(mission_id);
                    """
                )
        except sqlite3.DatabaseError as exc:
            raise StorageError(
                "Impossible d'initialiser la base SQLite locale "
                f"({self.path}) : fichier illisible ou corrompu."
            ) from exc

    # ------------------------------------------------------------------
    # Conversions
    # ------------------------------------------------------------------
    @staticmethod
    def _mission_from_row(row: sqlite3.Row) -> Mission:
        return Mission(
            id=row["id"],
            instruction=row["instruction"],
            status=MissionStatus(row["status"]),
            requires_approval=bool(row["requires_approval"]),
            approval_reason=row["approval_reason"],
            report_path=row["report_path"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @staticmethod
    def _task_from_row(row: sqlite3.Row) -> Task:
        return Task(
            id=row["id"],
            mission_id=row["mission_id"],
            key=row["key"],
            agent=row["agent"],
            title=row["title"],
            status=TaskStatus(row["status"]),
            depends_on=json.loads(row["depends_on"]),
            result=row["result"],
            evidence=json.loads(row["evidence"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    # ------------------------------------------------------------------
    # Missions
    # ------------------------------------------------------------------
    def create_mission(self, mission: Mission) -> Mission:
        with self._write("création de mission") as connection:
            connection.execute(
                """
                INSERT INTO missions (
                    id, instruction, status, requires_approval,
                    approval_reason, report_path, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    mission.id,
                    mission.instruction,
                    mission.status.value,
                    int(mission.requires_approval),
                    mission.approval_reason,
                    mission.report_path,
                    mission.created_at.isoformat(),
                    mission.updated_at.isoformat(),
                ),
            )
        return mission

    def get_mission(self, mission_id: str) -> Mission | None:
        with self._read() as connection:
            row = connection.execute(
                "SELECT * FROM missions WHERE id = ?", (mission_id,)
            ).fetchone()
        if row is None:
            return None
        return self._mission_from_row(row)

    def update_mission(
        self,
        mission_id: str,
        *,
        status: MissionStatus | None = None,
        report_path: str | None = None,
    ) -> None:
        fields: list[str] = ["updated_at = ?"]
        values: list[object] = [utcnow().isoformat()]
        if status is not None:
            fields.append("status = ?")
            values.append(status.value)
        if report_path is not None:
            fields.append("report_path = ?")
            values.append(report_path)
        values.append(mission_id)
        with self._write("mise à jour de mission") as connection:
            connection.execute(
                f"UPDATE missions SET {', '.join(fields)} WHERE id = ?", values
            )

    def list_missions(self) -> list[Mission]:
        with self._read() as connection:
            rows = connection.execute(
                "SELECT * FROM missions ORDER BY created_at DESC"
            ).fetchall()
        return [self._mission_from_row(row) for row in rows]

    # ------------------------------------------------------------------
    # Tâches
    # ------------------------------------------------------------------
    def create_task(self, task: Task) -> Task:
        with self._write("création de tâche") as connection:
            connection.execute(
                """
                INSERT INTO tasks (
                    id, mission_id, key, agent, title, status,
                    depends_on, result, evidence, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task.id,
                    task.mission_id,
                    task.key,
                    task.agent,
                    task.title,
                    task.status.value,
                    json.dumps(task.depends_on),
                    task.result,
                    json.dumps(task.evidence),
                    task.created_at.isoformat(),
                    task.updated_at.isoformat(),
                ),
            )
        return task

    def update_task(
        self,
        task_id: str,
        *,
        status: TaskStatus | None = None,
        result: str | None = None,
        evidence: list[str] | None = None,
    ) -> None:
        fields: list[str] = ["updated_at = ?"]
        values: list[object] = [utcnow().isoformat()]
        if status is not None:
            fields.append("status = ?")
            values.append(status.value)
        if result is not None:
            fields.append("result = ?")
            values.append(result)
        if evidence is not None:
            fields.append("evidence = ?")
            values.append(json.dumps(evidence))
        values.append(task_id)
        with self._write("mise à jour de tâche") as connection:
            connection.execute(
                f"UPDATE tasks SET {', '.join(fields)} WHERE id = ?", values
            )

    def list_tasks(self, mission_id: str) -> list[Task]:
        with self._read() as connection:
            rows = connection.execute(
                "SELECT * FROM tasks WHERE mission_id = ? ORDER BY created_at",
                (mission_id,),
            ).fetchall()
        return [self._task_from_row(row) for row in rows]

    def list_orphan_tasks(self) -> list[Task]:
        """Tâches dont la mission n'existe plus (diagnostic uniquement)."""

        with self._read() as connection:
            rows = connection.execute(
                """
                SELECT tasks.* FROM tasks
                LEFT JOIN missions ON missions.id = tasks.mission_id
                WHERE missions.id IS NULL
                ORDER BY tasks.created_at
                """
            ).fetchall()
        return [self._task_from_row(row) for row in rows]

    # ------------------------------------------------------------------
    # Événements
    # ------------------------------------------------------------------
    def add_event(self, event: Event) -> Event:
        with self._write("ajout d'événement") as connection:
            cursor = connection.execute(
                """
                INSERT INTO events (mission_id, type, agent, payload, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    event.mission_id,
                    event.type,
                    event.agent,
                    json.dumps(event.payload, ensure_ascii=False),
                    event.created_at.isoformat(),
                ),
            )
            event.id = int(cursor.lastrowid)
        return event

    def list_events(self, mission_id: str) -> list[Event]:
        with self._read() as connection:
            rows = connection.execute(
                "SELECT * FROM events WHERE mission_id = ? ORDER BY id",
                (mission_id,),
            ).fetchall()
        return [
            Event(
                id=row["id"],
                mission_id=row["mission_id"],
                type=row["type"],
                agent=row["agent"],
                payload=json.loads(row["payload"]),
                created_at=row["created_at"],
            )
            for row in rows
        ]

    def list_events_without_mission(self) -> list[Event]:
        """Événements rattachés à une mission absente (diagnostic)."""

        with self._read() as connection:
            rows = connection.execute(
                """
                SELECT events.* FROM events
                LEFT JOIN missions ON missions.id = events.mission_id
                WHERE missions.id IS NULL
                ORDER BY events.id
                """
            ).fetchall()
        return [
            Event(
                id=row["id"],
                mission_id=row["mission_id"],
                type=row["type"],
                agent=row["agent"],
                payload=json.loads(row["payload"]),
                created_at=row["created_at"],
            )
            for row in rows
        ]
