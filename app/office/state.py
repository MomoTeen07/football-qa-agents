"""Construction de l'état du bureau à partir des données réelles.

Aucune donnée n'est simulée : missions, tâches, événements et preuves
proviennent du store SQLite du système QA. Les communications affichées
sont des **passations** déduites des dépendances réelles entre tâches.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from app.domain.models import Event, Mission, MissionStatus, Task, TaskStatus
from app.office.catalog import (
    agent_catalog,
    agent_order,
    department_catalog,
)
from app.store.sqlite_store import SqliteStore

MISSION_STATUS_LABELS = {
    MissionStatus.CREATED: "Créée",
    MissionStatus.WAITING_APPROVAL: "Approbation requise",
    MissionStatus.PLANNING: "Planification",
    MissionStatus.RUNNING: "En cours",
    MissionStatus.REVIEWING: "Revue",
    MissionStatus.REPORTING: "Rapport",
    MissionStatus.COMPLETED: "Terminée",
    MissionStatus.FAILED: "Échec",
    MissionStatus.CANCELLED: "Annulée",
}

AGENT_STATUS_LABELS = {
    "working": "En travail",
    "done": "Terminé",
    "waiting": "En attente",
    "blocked": "Bloqué",
    "idle": "Disponible",
}

TASK_STATUS_LABELS = {
    TaskStatus.PENDING: "En attente",
    TaskStatus.RUNNING: "En cours",
    TaskStatus.COMPLETED: "Terminée",
    TaskStatus.FAILED: "Échec",
    TaskStatus.BLOCKED: "Bloquée",
    TaskStatus.SKIPPED: "Ignorée",
}

ACTIVE_MISSION_STATUSES = {
    MissionStatus.PLANNING,
    MissionStatus.RUNNING,
    MissionStatus.REVIEWING,
    MissionStatus.REPORTING,
}


def latest_mission(store: SqliteStore) -> Mission | None:
    missions = store.list_missions()
    return missions[0] if missions else None


def _iso(value: datetime | str | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _short(value: str | None, limit: int = 240) -> str | None:
    if not value:
        return value
    text = " ".join(value.split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _task_dict(task: Task) -> dict:
    return {
        "id": task.id,
        "key": task.key,
        "agent": task.agent,
        "title": task.title,
        "status": task.status.value,
        "status_label": TASK_STATUS_LABELS.get(task.status, task.status.value),
        "depends_on": list(task.depends_on),
        "result": _short(task.result, 600),
        "evidence": list(task.evidence[:12]),
        "evidence_count": len(task.evidence),
        "created_at": _iso(task.created_at),
        "updated_at": _iso(task.updated_at),
    }


def _event_dict(event: Event) -> dict:
    return {
        "id": event.id,
        "mission_id": event.mission_id,
        "type": event.type,
        "agent": event.agent,
        "payload": event.payload,
        "created_at": _iso(event.created_at),
    }


def serialize_event(event: Event) -> dict:
    """Sérialisation publique d'un événement pour le flux SSE."""

    return _event_dict(event)


def _agent_status(
    agent_id: str,
    own_tasks: list[Task],
    mission: Mission | None,
) -> str:
    if agent_id == "manager":
        if mission is None:
            return "idle"
        if mission.status == MissionStatus.COMPLETED:
            return "done"
        if mission.status == MissionStatus.FAILED:
            return "blocked"
        if mission.status in ACTIVE_MISSION_STATUSES:
            return "working"
        if mission.status in {MissionStatus.CREATED, MissionStatus.WAITING_APPROVAL}:
            return "waiting"
        return "idle"

    if any(task.status == TaskStatus.RUNNING for task in own_tasks):
        return "working"
    if any(
        task.status in {TaskStatus.FAILED, TaskStatus.BLOCKED} for task in own_tasks
    ):
        return "blocked"
    if own_tasks and all(task.status == TaskStatus.COMPLETED for task in own_tasks):
        return "done"
    if (
        mission is not None
        and mission.status in ACTIVE_MISSION_STATUSES
        and any(task.status == TaskStatus.PENDING for task in own_tasks)
    ):
        return "waiting"
    if mission is not None and mission.status == MissionStatus.FAILED:
        return "waiting"
    return "idle"


def _communications(tasks: list[Task]) -> list[dict]:
    by_key = {task.key: task for task in tasks}
    communications: list[dict] = []
    for task in tasks:
        if task.status not in {TaskStatus.RUNNING, TaskStatus.COMPLETED}:
            continue
        for dependency_key in task.depends_on:
            dependency = by_key.get(dependency_key)
            if dependency is None or dependency.status != TaskStatus.COMPLETED:
                continue
            if dependency.agent == task.agent:
                continue
            communications.append(
                {
                    "from": dependency.agent,
                    "to": task.agent,
                    "task_key": task.key,
                    "task_title": task.title,
                    "depends_on": dependency_key,
                    "status": task.status.value,
                    "at": _iso(task.updated_at),
                }
            )
    communications.sort(key=lambda item: item["at"] or "")
    return communications[-24:]


def _allure_summary(allure_root: Path | None, mission_id: str) -> dict | None:
    if allure_root is None:
        return None
    summary_path = Path(allure_root) / mission_id / "allure-summary.json"
    if not summary_path.is_file():
        return None
    try:
        payload = json.loads(summary_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    totals = payload.get("totals") or {}
    return {
        "dir": str(summary_path.parent),
        "total": int(totals.get("total", 0)),
        "passed": int(totals.get("passed", 0)),
        "failed": int(totals.get("failed", 0)),
        "skipped": int(totals.get("skipped", 0)),
        "anomalies": int(totals.get("anomalies", 0)),
        "status": payload.get("status"),
    }


def _empty_state(requested_mission_id: str | None = None) -> dict:
    agents = []
    for agent in agent_catalog():
        agents.append(
            {
                **agent,
                "status": "idle",
                "status_label": AGENT_STATUS_LABELS["idle"],
                "current_task": "Aucune mission",
                "tasks_total": 0,
                "tasks_done": 0,
                "last_event": None,
                "last_result": None,
            }
        )
    return {
        "generated_at": datetime.now().astimezone().isoformat(),
        "requested_mission_id": requested_mission_id,
        "mission": None,
        "agents": agents,
        "departments": department_catalog(),
        "tasks": [],
        "events": [],
        "communications": [],
        "stats": {
            "tasks_total": 0,
            "tasks_done": 0,
            "tasks_running": 0,
            "tasks_blocked": 0,
            "tasks_pending": 0,
            "tasks_failed": 0,
            "events_total": 0,
            "evidence_total": 0,
            "agents_working": 0,
            "agents_done": 0,
            "agents_waiting": 0,
            "agents_blocked": 0,
            "progress": 0,
        },
        "allure": None,
    }


def build_office_state(
    store: SqliteStore,
    mission_id: str | None = None,
    *,
    allure_root: Path | None = None,
) -> dict:
    """Retourne un instantané complet et sérialisable du bureau."""

    missions = store.list_missions()
    mission: Mission | None = None
    if mission_id:
        mission = next((item for item in missions if item.id == mission_id), None)
    elif missions:
        mission = missions[0]

    if mission is None:
        return _empty_state(mission_id)

    tasks = store.list_tasks(mission.id)
    events = store.list_events(mission.id)
    by_agent: dict[str, list[Task]] = {}
    for task in tasks:
        by_agent.setdefault(task.agent, []).append(task)

    events_by_agent: dict[str, Event] = {}
    mission_events: list[Event] = []
    for event in events:
        if event.agent:
            events_by_agent[event.agent] = event
        else:
            mission_events.append(event)

    agents: list[dict] = []
    for agent in agent_catalog():
        own_tasks = by_agent.get(agent["id"], [])
        status = _agent_status(agent["id"], own_tasks, mission)
        running = next(
            (task for task in own_tasks if task.status == TaskStatus.RUNNING), None
        )
        last_completed = next(
            (
                task
                for task in reversed(own_tasks)
                if task.status == TaskStatus.COMPLETED and task.result
            ),
            None,
        )
        if agent["id"] == "manager":
            current_task = f"Coordination : {MISSION_STATUS_LABELS[mission.status]}"
            last_event = mission_events[-1] if mission_events else None
        else:
            current_task = (
                running.title
                if running is not None
                else (own_tasks[-1].title if own_tasks else "Aucune tâche planifiée")
            )
            last_event = events_by_agent.get(agent["id"])
        agents.append(
            {
                **agent,
                "status": status,
                "status_label": AGENT_STATUS_LABELS[status],
                "current_task": current_task,
                "tasks_total": len(own_tasks),
                "tasks_done": sum(
                    1 for task in own_tasks if task.status == TaskStatus.COMPLETED
                ),
                "last_event": _event_dict(last_event) if last_event else None,
                "last_result": _short(
                    last_completed.result if last_completed else None, 240
                ),
            }
        )
    agents.sort(key=lambda item: agent_order(item["id"]))

    total = len(tasks)
    done = sum(1 for task in tasks if task.status == TaskStatus.COMPLETED)
    progress = round(done * 100 / total) if total else 0

    stats = {
        "tasks_total": total,
        "tasks_done": done,
        "tasks_running": sum(1 for task in tasks if task.status == TaskStatus.RUNNING),
        "tasks_blocked": sum(1 for task in tasks if task.status == TaskStatus.BLOCKED),
        "tasks_pending": sum(1 for task in tasks if task.status == TaskStatus.PENDING),
        "tasks_failed": sum(1 for task in tasks if task.status == TaskStatus.FAILED),
        "events_total": len(events),
        "evidence_total": sum(len(task.evidence) for task in tasks),
        "agents_working": sum(1 for agent in agents if agent["status"] == "working"),
        "agents_done": sum(1 for agent in agents if agent["status"] == "done"),
        "agents_waiting": sum(1 for agent in agents if agent["status"] == "waiting"),
        "agents_blocked": sum(1 for agent in agents if agent["status"] == "blocked"),
        "progress": progress,
    }

    return {
        "generated_at": datetime.now().astimezone().isoformat(),
        "requested_mission_id": mission_id,
        "mission": {
            "id": mission.id,
            "instruction": mission.instruction,
            "status": mission.status.value,
            "status_label": MISSION_STATUS_LABELS[mission.status],
            "requires_approval": mission.requires_approval,
            "approval_reason": mission.approval_reason,
            "report_path": mission.report_path,
            "created_at": _iso(mission.created_at),
            "updated_at": _iso(mission.updated_at),
            "progress": progress,
            "tasks_total": total,
            "tasks_done": done,
        },
        "agents": agents,
        "departments": department_catalog(),
        "tasks": [_task_dict(task) for task in tasks],
        "events": [_event_dict(event) for event in events[-120:]],
        "communications": _communications(tasks),
        "stats": stats,
        "allure": _allure_summary(allure_root, mission.id),
    }


def mission_summaries(store: SqliteStore, limit: int = 20) -> list[dict]:
    """Liste compacte des missions récentes pour le panneau « Missions »."""

    summaries: list[dict] = []
    for mission in store.list_missions()[:limit]:
        tasks = store.list_tasks(mission.id)
        total = len(tasks)
        done = sum(1 for task in tasks if task.status == TaskStatus.COMPLETED)
        summaries.append(
            {
                "id": mission.id,
                "instruction": _short(mission.instruction, 160),
                "status": mission.status.value,
                "status_label": MISSION_STATUS_LABELS[mission.status],
                "requires_approval": mission.requires_approval,
                "created_at": _iso(mission.created_at),
                "tasks_total": total,
                "tasks_done": done,
                "progress": round(done * 100 / total) if total else 0,
            }
        )
    return summaries


def state_for_request(
    store: SqliteStore,
    mission_id: str | None,
    *,
    allure_root: Path | None = None,
) -> dict[str, Any]:
    return build_office_state(store, mission_id, allure_root=allure_root)
