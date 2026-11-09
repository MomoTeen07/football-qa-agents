from __future__ import annotations

import json
from pathlib import Path

from app.agents.phase6 import (
    API_FALLBACK,
    UI_FALLBACK,
    APIAutomationAgent,
    UIAutomationAgent,
)
from app.agents.stubs import QAReporterAgent
from app.config import Settings
from app.domain.models import Mission, Task
from app.tools.api_probe import UnsafeTargetError
from app.tools.api_suite import ApiSuiteCheck, ApiSuiteOutcome
from app.tools.ui_suite import UiSuiteCheck, UiSuiteOutcome, UnsafeUiTargetError


def make_settings(tmp_path: Path, *, real_agents_enabled: bool = True) -> Settings:
    return Settings(
        _env_file=None,
        real_agents_enabled=real_agents_enabled,
        workspace_dir=tmp_path / "workspace",
        postman_dir=tmp_path / "postman",
        reports_dir=tmp_path / "reports",
        test_api_url="http://localhost:8002",
        test_ui_url="http://localhost:5175",
    )


def make_mission() -> Mission:
    return Mission(instruction="Lance une campagne complète API et UI.")


def make_task(mission: Mission, agent: str, key: str) -> Task:
    return Task(
        mission_id=mission.id,
        key=key,
        agent=agent,
        title=f"Tâche {agent}",
    )


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )


class ForbiddenSuite:
    def run(self, mission_id: str):
        raise AssertionError("la suite ne doit pas être exécutée en mode repli")


class FakeApiSuite:
    def __init__(self, outcome: ApiSuiteOutcome) -> None:
        self.outcome = outcome
        self.calls: list[str] = []

    def run(self, mission_id: str) -> ApiSuiteOutcome:
        self.calls.append(mission_id)
        return self.outcome


class RaisingApiSuite:
    def __init__(self, error: Exception) -> None:
        self.error = error

    def run(self, mission_id: str):
        raise self.error


class FakeUiSuite:
    def __init__(self, outcome: UiSuiteOutcome) -> None:
        self.outcome = outcome
        self.calls: list[str] = []

    def run(self, mission_id: str) -> UiSuiteOutcome:
        self.calls.append(mission_id)
        return self.outcome


class RaisingUiSuite:
    def __init__(self, error: Exception) -> None:
        self.error = error

    def run(self, mission_id: str):
        raise self.error


def test_api_automation_uses_fallback_without_real_agents(tmp_path: Path) -> None:
    settings = make_settings(tmp_path, real_agents_enabled=False)
    mission = make_mission()
    task = make_task(mission, "api_automation", "api_automation")

    result = APIAutomationAgent(settings, suite=ForbiddenSuite()).run(task, mission)

    assert result.summary == API_FALLBACK
    assert result.anomalies == []
    assert result.evidence == []


def test_ui_automation_uses_fallback_without_real_agents(tmp_path: Path) -> None:
    settings = make_settings(tmp_path, real_agents_enabled=False)
    mission = make_mission()
    task = make_task(mission, "ui_automation", "ui_automation")

    result = UIAutomationAgent(settings, suite=ForbiddenSuite()).run(task, mission)

    assert result.summary == UI_FALLBACK
    assert result.anomalies == []
    assert result.evidence == []


def test_api_automation_reports_real_failures(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    mission = make_mission()
    task = make_task(mission, "api_automation", "api_automation")
    anomaly = {
        "check": "test_leagues_return_six_entries",
        "method": "GET",
        "path": "/api/football/leagues",
        "expected": "HTTP 200",
        "actual": "HTTP 500",
        "reproduction": "GET http://localhost:8002/api/football/leagues",
    }
    outcome = ApiSuiteOutcome(
        status="completed",
        checks=[
            ApiSuiteCheck(name="test_health_returns_ok", outcome="passed", duration_s=0.1),
            ApiSuiteCheck(
                name="test_leagues_return_six_entries",
                outcome="failed",
                duration_s=0.2,
            ),
        ],
        anomalies=[anomaly],
        evidence_paths=["junit.xml", "report.md"],
        summary="Suite pytest API exécutée : 1/2 tests réussis, 1 échec(s).",
        sources={
            "postman_requests": 11,
            "postman_safe_cases": 5,
            "probe_checks": 21,
        },
    )
    suite = FakeApiSuite(outcome)

    result = APIAutomationAgent(settings, suite=suite).run(task, mission)

    assert suite.calls == [mission.id]
    assert "Requêtes Postman analysées : 11" in result.summary
    assert "Sondes phase 5 réutilisées : 21" in result.summary
    assert "Anomalies reproductibles" in result.summary
    assert anomaly["reproduction"] in result.summary
    assert result.anomalies == [anomaly]
    assert result.evidence == ["junit.xml", "report.md"]


def test_api_automation_blocked_does_not_declare_anomaly(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    mission = make_mission()
    task = make_task(mission, "api_automation", "api_automation")
    outcome = ApiSuiteOutcome(
        status="blocked",
        checks=[],
        anomalies=[],
        summary="Suite pytest API non exécutée : API injoignable.",
        blocked_reason="API injoignable.",
    )

    result = APIAutomationAgent(settings, suite=FakeApiSuite(outcome)).run(
        task, mission
    )

    assert "non exécutée" in result.summary
    assert "Anomalies reproductibles" not in result.summary
    assert result.anomalies == []


def test_api_automation_refuses_unsafe_target(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    mission = make_mission()
    task = make_task(mission, "api_automation", "api_automation")

    result = APIAutomationAgent(
        settings,
        suite=RaisingApiSuite(UnsafeTargetError("cible interdite")),
    ).run(task, mission)

    assert "Automatisation API non exécutée" in result.summary
    assert result.artifacts == []
    assert result.anomalies == []


def test_ui_automation_reports_real_failures(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    mission = make_mission()
    task = make_task(mission, "ui_automation", "ui_automation")
    anomaly = {
        "check": "Championnats visibles",
        "source": "playwright-ui",
        "expected": "6 cartes",
        "actual": "3 cartes",
        "reproduction": "Ouvrir http://localhost:5175/championships",
        "screenshot": "01-championnats.png",
    }
    outcome = UiSuiteOutcome(
        status="completed",
        checks=[
            UiSuiteCheck(name="Accueil accessible", status="passed"),
            UiSuiteCheck(name="Championnats visibles", status="failed"),
        ],
        anomalies=[anomaly],
        evidence_paths=["run_ui_checks.py", "report.md", "01-championnats.png"],
        summary="Scénarios Playwright exécutés : 1/2 scénarios réussis.",
    )

    result = UIAutomationAgent(settings, suite=FakeUiSuite(outcome)).run(
        task, mission
    )

    assert "Anomalies reproductibles" in result.summary
    assert anomaly["reproduction"] in result.summary
    assert result.anomalies == [anomaly]
    assert result.evidence == outcome.evidence_paths


def test_ui_automation_refuses_unsafe_target(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    mission = make_mission()
    task = make_task(mission, "ui_automation", "ui_automation")

    result = UIAutomationAgent(
        settings,
        suite=RaisingUiSuite(UnsafeUiTargetError("frontend interdit")),
    ).run(task, mission)

    assert "Automatisation UI non exécutée" in result.summary
    assert result.artifacts == []
    assert result.anomalies == []


def test_reporter_includes_phase6_results_and_real_anomalies(
    tmp_path: Path,
) -> None:
    settings = make_settings(tmp_path)
    mission = make_mission()
    base = tmp_path / "workspace" / "missions" / mission.id
    write_json(
        base / "api-automation" / "api-automation-results.json",
        {
            "status": "completed",
            "summary": {
                "tests": 2,
                "passed": 1,
                "failed": 1,
                "skipped": 0,
                "anomalies": 1,
            },
            "anomalies": [
                {
                    "check": "test_leagues_return_six_entries",
                    "reproduction": "GET http://localhost:8002/api/football/leagues",
                    "expected": "HTTP 200",
                    "actual": "HTTP 500",
                    "evidence": "junit.xml",
                }
            ],
        },
    )
    write_json(
        base / "ui-automation" / "ui-automation-results.json",
        {
            "status": "completed",
            "summary": {
                "checks": 2,
                "passed": 2,
                "failed": 0,
                "skipped": 0,
                "anomalies": 0,
            },
            "anomalies": [],
        },
    )
    task = make_task(mission, "qa_reporter", "report")

    report = QAReporterAgent(settings).run(
        task,
        mission,
        context={
            "tasks": [
                {
                    "agent": "api_automation",
                    "title": "API",
                    "status": "completed",
                    "result": "suite exécutée",
                    "evidence": [],
                }
            ]
        },
    ).summary

    assert "Automatisation API pytest (phase 6)" in report
    assert "Automatisation UI Playwright (phase 6)" in report
    assert "GET http://localhost:8002/api/football/leagues" in report
    assert "HTTP 500" in report
    assert "Aucun test réel n'a été exécuté" not in report
    assert "Aucune anomalie déclarée" not in report


def test_reporter_does_not_invent_anomaly_for_blocked_phase6(
    tmp_path: Path,
) -> None:
    settings = make_settings(tmp_path)
    mission = make_mission()
    base = tmp_path / "workspace" / "missions" / mission.id
    write_json(
        base / "api-automation" / "api-automation-results.json",
        {
            "status": "blocked",
            "blocked_reason": "API de test injoignable.",
            "summary": {
                "tests": 0,
                "passed": 0,
                "failed": 0,
                "skipped": 0,
                "anomalies": 0,
            },
            "anomalies": [],
        },
    )
    task = make_task(mission, "qa_reporter", "report")

    report = QAReporterAgent(settings).run(task, mission, context={"tasks": []}).summary

    assert "Aucune anomalie déclarée" in report
    assert "API de test injoignable" in report
    assert "Anomalies reproductibles" not in report
