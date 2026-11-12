from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path

import pytest

from app.config import Settings
from app.domain.models import Mission, MissionStatus, Task, TaskStatus, utcnow
from app.orchestrator.doctor import diagnose, summarize
from app.orchestrator.manager import Manager
from app.orchestrator.planner import build_plan
from app.store.sqlite_store import SqliteStore


@pytest.fixture()
def settings(tmp_path: Path) -> Settings:
    return Settings(
        mission_db_path=tmp_path / "missions.db",
        reports_dir=tmp_path / "reports",
        workspace_dir=tmp_path / "workspace",
        postman_dir=tmp_path / "postman",
        allure_results_dir=tmp_path / "reports" / "allure-results",
        real_agents_enabled=False,
    )


@pytest.fixture()
def manager(settings: Settings):
    instance = Manager(settings)
    yield instance
    instance.close()


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_resume_running_mission_reuses_tasks_and_keeps_results(
    manager: Manager,
) -> None:
    mission = manager.create_mission(
        "Analyse l'application et propose un plan de test."
    )
    plan = build_plan(mission.instruction)
    analysis = manager.store.create_task(
        Task(
            mission_id=mission.id,
            key="analysis",
            agent="qa_analyst",
            title="Analyse déjà terminée",
            status=TaskStatus.COMPLETED,
            result="analyse initiale",
            evidence=["workspace/analyse.json"],
        )
    )
    manager.store.update_mission(mission.id, status=MissionStatus.RUNNING)
    manager.bus.publish(
        mission.id,
        "task_started",
        agent="qa_analyst",
        payload={"key": "analysis", "title": "Analyse déjà terminée"},
    )

    resumed = manager.run_mission(mission.id)

    tasks = manager.get_tasks(mission.id)
    keys = [task.key for task in tasks]
    assert sorted(keys) == sorted(item["key"] for item in plan)
    assert len(keys) == len(set(keys)), "aucune tâche ne doit être dupliquée"

    stored_analysis = next(task for task in tasks if task.key == "analysis")
    assert stored_analysis.id == analysis.id
    assert stored_analysis.result == "analyse initiale"
    assert stored_analysis.evidence == ["workspace/analyse.json"]

    starts = [
        event
        for event in manager.get_events(mission.id)
        if event.type == "task_started"
        and event.payload.get("key") == "analysis"
    ]
    assert len(starts) == 1, "une tâche terminée ne doit pas être rejouée"

    assert resumed.status == MissionStatus.COMPLETED
    assert resumed.report_path is not None
    assert Path(resumed.report_path).is_file()


def test_resume_does_not_regenerate_an_existing_report(
    manager: Manager, settings: Settings
) -> None:
    mission = manager.create_mission(
        "Analyse l'application et propose un plan de test."
    )
    for item in build_plan(mission.instruction):
        manager.store.create_task(
            Task(
                mission_id=mission.id,
                key=item["key"],
                agent=item["agent"],
                title=item["title"],
                depends_on=item["depends_on"],
                status=TaskStatus.COMPLETED,
                result=f"résultat {item['key']}",
                evidence=[],
            )
        )

    report_file = Path(settings.reports_dir) / f"{mission.id}.md"
    report_file.parent.mkdir(parents=True, exist_ok=True)
    report_file.write_text("RAPPORT EXISTANT À CONSERVER\n", encoding="utf-8")
    manager.store.update_mission(
        mission.id,
        status=MissionStatus.RUNNING,
        report_path=str(report_file),
    )

    resumed = manager.run_mission(mission.id)

    assert report_file.read_text(encoding="utf-8") == "RAPPORT EXISTANT À CONSERVER\n"
    assert not [
        event
        for event in manager.get_events(mission.id)
        if event.type == "report_ready"
    ], "un rapport déjà produit ne doit pas être annoncé une seconde fois"
    assert resumed.status == MissionStatus.COMPLETED
    assert resumed.report_path == str(report_file)


def test_doctor_detects_duplicates_and_orphans_without_writing(
    manager: Manager,
) -> None:
    mission = manager.create_mission(
        "Analyse l'application et propose un plan de test."
    )
    manager.store.create_task(
        Task(
            mission_id=mission.id,
            key="analysis",
            agent="qa_analyst",
            title="Analyse",
            status=TaskStatus.COMPLETED,
            result="ok",
        )
    )
    manager.store.create_task(
        Task(
            mission_id=mission.id,
            key="analysis",
            agent="qa_analyst",
            title="Analyse dupliquée",
        )
    )
    manager.store.update_mission(mission.id, status=MissionStatus.COMPLETED)

    now = utcnow().isoformat()
    raw = sqlite3.connect(manager.store.path)
    try:
        raw.execute(
            """
            INSERT INTO tasks (
                id, mission_id, key, agent, title, status,
                depends_on, result, evidence, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "tache-orpheline",
                "mission-disparue",
                "ui_automation",
                "ui_automation",
                "Tâche orpheline",
                TaskStatus.PENDING.value,
                "[]",
                None,
                "[]",
                now,
                now,
            ),
        )
        raw.execute(
            """
            INSERT INTO events (mission_id, type, agent, payload, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            ("mission-disparue", "task_started", None, "{}", now),
        )
        raw.commit()
    finally:
        raw.close()

    before = _hash(manager.store.path)
    read_only = SqliteStore(manager.store.path, read_only=True)
    report = diagnose(read_only)
    after = _hash(manager.store.path)

    assert before == after, "doctor ne doit jamais modifier la base"
    assert report["problems"] is True
    assert report["duplicate_task_keys"] == [
        {"mission_id": mission.id, "key": "analysis", "count": 2}
    ]
    assert report["orphan_tasks"] == 1
    assert report["orphan_events"] == 1
    assert any(
        item["id"] == mission.id for item in report["inconsistent_missions"]
    )
    assert "clé(s) de tâche dupliquée(s)" in summarize(report)


def test_doctor_flags_a_running_mission_without_tasks(
    manager: Manager,
) -> None:
    mission = Mission(instruction="Mission bloquée", status=MissionStatus.RUNNING)
    manager.store.create_mission(mission)

    report = diagnose(manager.store)

    assert report["problems"] is True
    assert report["stale_missions"][0]["id"] == mission.id
    assert any(
        item["id"] == mission.id
        and "aucune tâche" in item["reason"]
        for item in report["inconsistent_missions"]
    )
    assert "non terminale(s)" in summarize(report)


def test_doctor_summarizes_an_empty_database(tmp_path: Path) -> None:
    store = SqliteStore(tmp_path / "vide.db")

    report = diagnose(store)

    assert report["missions_total"] == 0
    assert report["problems"] is False
    assert summarize(report) == "Base de pilotage vide : aucune mission enregistrée."


def test_doctor_summarizes_a_healthy_database(manager: Manager) -> None:
    mission = manager.create_mission(
        "Analyse l'application et propose un plan de test."
    )
    for item in build_plan(mission.instruction):
        manager.store.create_task(
            Task(
                mission_id=mission.id,
                key=item["key"],
                agent=item["agent"],
                title=item["title"],
                depends_on=item["depends_on"],
                status=TaskStatus.COMPLETED,
            )
        )
    manager.store.update_mission(mission.id, status=MissionStatus.COMPLETED)

    report = diagnose(manager.store)

    assert report["problems"] is False
    assert summarize(report) == (
        "Aucune incohérence détectée sur 1 mission(s)."
    )
