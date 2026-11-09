from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path

from app.domain.models import (
    Event,
    Mission,
    MissionStatus,
    Task,
    TaskStatus,
    utcnow,
)


class SqliteStore:
    """Stockage local des missions, tâches et événements.

    Le fichier SQLite est indépendant de la base PostgreSQL de l'application
    testée. Il ne contient que les données de pilotage QA.
    """

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        return connection

    def _init_db(self) -> None:
        with self._lock, self._connect() as connection:
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

                CREATE INDEX IF NOT EXISTS idx_tasks_mission ON tasks(mission_id);
                CREATE INDEX IF NOT EXISTS idx_events_mission ON events(mission_id);
                """
            )

    # ------------------------------------------------------------------
    # Missions
    # ------------------------------------------------------------------
    def create_mission(self, mission: Mission) -> Mission:
        with self._lock, self._connect() as connection:
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
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM missions WHERE id = ?", (mission_id,)
            ).fetchone()
        if row is None:
            return None
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
        with self._lock, self._connect() as connection:
            connection.execute(
                f"UPDATE missions SET {', '.join(fields)} WHERE id = ?", values
            )

    def list_missions(self) -> list[Mission]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM missions ORDER BY created_at DESC"
            ).fetchall()
        return [
            Mission(
                id=row["id"],
                instruction=row["instruction"],
                status=MissionStatus(row["status"]),
                requires_approval=bool(row["requires_approval"]),
                approval_reason=row["approval_reason"],
                report_path=row["report_path"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            for row in rows
        ]

    # ------------------------------------------------------------------
    # Tâches
    # ------------------------------------------------------------------
    def create_task(self, task: Task) -> Task:
        with self._lock, self._connect() as connection:
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
        with self._lock, self._connect() as connection:
            connection.execute(
                f"UPDATE tasks SET {', '.join(fields)} WHERE id = ?", values
            )

    def list_tasks(self, mission_id: str) -> list[Task]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM tasks WHERE mission_id = ? ORDER BY created_at",
                (mission_id,),
            ).fetchall()
        return [
            Task(
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
            for row in rows
        ]

    # ------------------------------------------------------------------
    # Événements
    # ------------------------------------------------------------------
    def add_event(self, event: Event) -> Event:
        with self._lock, self._connect() as connection:
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
        with self._connect() as connection:
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
