"""Diagnostic en lecture seule de la base de pilotage (phase 9, WP3).

`python -m app.cli doctor` ne répare rien et ne crée aucune mission : il liste
les incohérences observables pour qu'un humain décide. La base est ouverte en
mode SQLite `mode=ro`, donc aucun PRAGMA d'écriture ni schéma n'est appliqué.
"""

from __future__ import annotations

from collections import Counter

from app.domain.models import MissionStatus, TaskStatus
from app.store.sqlite_store import SqliteStore

TERMINAL_STATUSES = {
    MissionStatus.COMPLETED,
    MissionStatus.FAILED,
    MissionStatus.CANCELLED,
}

ACTIVE_TASK_STATUSES = {TaskStatus.PENDING, TaskStatus.RUNNING}


def diagnose(store: SqliteStore) -> dict:
    """Retourne un rapport de cohérence, sans modifier la base."""

    missions = store.list_missions()
    by_status = Counter(mission.status.value for mission in missions)
    stale_missions: list[dict] = []
    inconsistent_missions: list[dict] = []
    duplicate_keys: list[dict] = []

    for mission in missions:
        tasks = store.list_tasks(mission.id)
        running = [
            task for task in tasks if task.status in ACTIVE_TASK_STATUSES
        ]

        if mission.status not in TERMINAL_STATUSES:
            stale_missions.append(
                {
                    "id": mission.id,
                    "status": mission.status.value,
                    "instruction": mission.instruction[:120],
                    "tasks": len(tasks),
                    "active_tasks": len(running),
                    "updated_at": str(mission.updated_at),
                }
            )

        if mission.status in TERMINAL_STATUSES and running:
            inconsistent_missions.append(
                {
                    "id": mission.id,
                    "status": mission.status.value,
                    "reason": (
                        f"{len(running)} tâche(s) encore en attente ou en cours "
                        "sur une mission terminée"
                    ),
                }
            )
        elif mission.status == MissionStatus.RUNNING and not tasks:
            inconsistent_missions.append(
                {
                    "id": mission.id,
                    "status": mission.status.value,
                    "reason": "mission en cours sans aucune tâche planifiée",
                }
            )

        keys = Counter(task.key for task in tasks)
        for key, count in keys.items():
            if count > 1:
                duplicate_keys.append(
                    {"mission_id": mission.id, "key": key, "count": count}
                )

    orphan_tasks = store.list_orphan_tasks()
    orphan_events = store.list_events_without_mission()

    problems = bool(
        stale_missions
        or inconsistent_missions
        or duplicate_keys
        or orphan_tasks
        or orphan_events
    )
    return {
        "missions_total": len(missions),
        "missions_by_status": dict(sorted(by_status.items())),
        "stale_missions": stale_missions,
        "inconsistent_missions": inconsistent_missions,
        "duplicate_task_keys": duplicate_keys,
        "orphan_tasks": len(orphan_tasks),
        "orphan_events": len(orphan_events),
        "problems": problems,
    }


def summarize(report: dict) -> str:
    """Résumé texte stable, utilisé par la CLI et les tests."""

    if not report["missions_total"]:
        return "Base de pilotage vide : aucune mission enregistrée."
    if not report["problems"]:
        return (
            f"Aucune incohérence détectée sur {report['missions_total']} mission(s)."
        )
    parts = [
        f"{len(report['stale_missions'])} mission(s) non terminale(s)",
        f"{len(report['inconsistent_missions'])} incohérence(s)",
        f"{len(report['duplicate_task_keys'])} clé(s) de tâche dupliquée(s)",
        f"{report['orphan_tasks']} tâche(s) orpheline(s)",
        f"{report['orphan_events']} événement(s) orphelin(s)",
    ]
    return "Diagnostic : " + ", ".join(parts) + "."
