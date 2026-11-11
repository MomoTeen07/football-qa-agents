from __future__ import annotations

from pathlib import Path

import pytest

from app.config import Settings
from app.domain.models import MissionStatus, TaskStatus
from app.orchestrator.manager import Manager


@pytest.fixture()
def manager(tmp_path: Path):
    settings = Settings(
        mission_db_path=tmp_path / "missions.db",
        reports_dir=tmp_path / "reports",
        workspace_dir=tmp_path / "workspace",
        postman_dir=tmp_path / "postman",
        allure_results_dir=tmp_path / "reports" / "allure-results",
        real_agents_enabled=False,
    )
    instance = Manager(settings)
    yield instance
    instance.close()


def test_creating_a_mission_does_not_run_it(manager: Manager) -> None:
    mission = manager.create_mission("Analyse l'application et propose un plan de test.")

    assert mission.status == MissionStatus.CREATED
    assert manager.get_tasks(mission.id) == []
    event_types = [event.type for event in manager.get_events(mission.id)]
    assert "mission_created" in event_types
    assert "mission_started" not in event_types


def test_analysis_mission_runs_and_produces_a_report(manager: Manager) -> None:
    mission = manager.create_mission("Analyse l'application et propose un plan de test.")
    mission = manager.run_mission(mission.id)

    assert mission.status == MissionStatus.COMPLETED
    tasks = manager.get_tasks(mission.id)
    assert {task.agent for task in tasks} >= {
        "qa_analyst",
        "test_designer",
        "qa_reporter",
    }
    assert all(task.status == TaskStatus.COMPLETED for task in tasks)
    assert mission.report_path is not None
    report = Path(mission.report_path).read_text(encoding="utf-8")
    assert "Aucun test réel n'a été exécuté" in report
    assert "Aucune anomalie déclarée" in report


def test_full_campaign_plan_contains_api_and_ui_agents(manager: Manager) -> None:
    mission = manager.create_mission(
        "Lance une campagne complète de tests API et UI sur l'application."
    )
    mission = manager.run_mission(mission.id)

    assert mission.status == MissionStatus.COMPLETED
    agents = {task.agent for task in manager.get_tasks(mission.id)}
    assert {"api_tester", "api_automation", "ui_automation", "qa_reporter"} <= agents


def test_sensitive_mission_requires_approval(manager: Manager) -> None:
    mission = manager.create_mission("Lance un test de sécurité intrusif sur l'API.")
    assert mission.requires_approval is True

    blocked = manager.run_mission(mission.id)
    assert blocked.status == MissionStatus.WAITING_APPROVAL
    assert manager.get_tasks(mission.id) == []
    assert "approval_required" in [
        event.type for event in manager.get_events(mission.id)
    ]

    approved = manager.approve_mission(mission.id)
    assert approved.status == MissionStatus.COMPLETED
    event_types = [event.type for event in manager.get_events(mission.id)]
    assert "mission_approved" in event_types


def test_mission_events_are_real_and_ordered(manager: Manager) -> None:
    mission = manager.create_mission("Lance une campagne complète de tests API et UI.")
    manager.run_mission(mission.id)

    events = manager.get_events(mission.id)
    event_types = [event.type for event in events]
    assert event_types[0] == "mission_created"
    assert "mission_planned" in event_types
    assert "task_started" in event_types
    assert "task_completed" in event_types
    assert "report_ready" in event_types
    assert event_types[-1] == "mission_completed"
