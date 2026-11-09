from __future__ import annotations

import json
from pathlib import Path

from app.agents.phase5 import APITesterAgent, QAAnalystAgent
from app.agents.stubs import QAReporterAgent
from app.config import Settings
from app.domain.models import Mission, Task
from app.tools.api_probe import ProbeCheck, ProbeOutcome

SPEC = {
    "openapi": "3.0.0",
    "info": {"title": "Football QA API", "version": "1.0.0"},
    "paths": {
        "/health": {
            "get": {
                "tags": ["health"],
                "summary": "Health",
                "responses": {"200": {"description": "OK"}},
            }
        },
        "/api/favorites": {
            "post": {
                "tags": ["favorites"],
                "summary": "Add favorite",
                "security": [{"HTTPBearer": []}],
                "responses": {"201": {"description": "Created"}},
            }
        },
    },
}


class FakeLLM:
    def __init__(self, text: str = "Synthèse LLM") -> None:
        self.text = text
        self.available = True
        self.calls: list[tuple[str, str | None]] = []

    def generate(self, prompt: str, *, system_instruction: str | None = None) -> str:
        self.calls.append((prompt, system_instruction))
        return self.text


class FakeProbe:
    def __init__(self, outcome: ProbeOutcome) -> None:
        self.outcome = outcome
        self.calls: list[str] = []

    def run(self, mission_id: str) -> ProbeOutcome:
        self.calls.append(mission_id)
        return self.outcome


def make_settings(tmp_path: Path, *, real_agents_enabled: bool = True) -> Settings:
    return Settings(
        _env_file=None,
        real_agents_enabled=real_agents_enabled,
        workspace_dir=tmp_path / "workspace",
        postman_dir=tmp_path / "postman",
        test_api_url="http://localhost:8002",
        test_user1_email="qa.user1@example.com",
        test_user1_password="QaTest123!",
        test_user2_email="qa.user2@example.com",
        test_user2_password="QaTest123!",
    )


def make_mission(instruction: str = "Analyse l'API et prépare Postman.") -> Mission:
    return Mission(instruction=instruction)


def make_task(mission: Mission, agent: str, key: str) -> Task:
    return Task(
        mission_id=mission.id,
        key=key,
        agent=agent,
        title=f"Tâche {agent}",
    )


def test_qa_analyst_without_real_agents_keeps_deterministic_fallback(
    tmp_path: Path,
) -> None:
    settings = make_settings(tmp_path, real_agents_enabled=False)
    llm = FakeLLM()
    mission = make_mission()
    task = make_task(mission, "qa_analyst", "analysis")

    result = QAAnalystAgent(settings, llm=llm).run(task, mission)

    assert llm.calls == []
    assert "Aucun test réel n'a été exécuté" in result.summary
    assert not (tmp_path / "workspace" / "missions" / mission.id).exists()


def test_qa_analyst_uses_gemini_and_writes_evidence(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    llm = FakeLLM("Analyse enrichie par Gemini.")
    mission = make_mission()
    task = make_task(mission, "qa_analyst", "analysis")

    result = QAAnalystAgent(settings, llm=llm).run(task, mission)

    assert llm.calls
    assert "Analyse enrichie par Gemini." in result.summary
    assert result.evidence
    evidence = Path(result.evidence[0])
    assert evidence.is_file()
    assert "Analyse enrichie par Gemini." in evidence.read_text(encoding="utf-8")


def test_api_tester_generates_postman_and_runs_probe(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import app.agents.phase5 as phase5

    monkeypatch.setattr(phase5, "fetch_openapi", lambda *args, **kwargs: SPEC)
    outcome = ProbeOutcome(
        status="completed",
        checks=[
            ProbeCheck(
                name="Santé de l'API",
                method="GET",
                path="/health",
                expected="200",
                actual="HTTP 200",
                passed=True,
            )
        ],
        anomalies=[],
        evidence_paths=[str(tmp_path / "probe.json")],
        summary="Sondes API réelles terminées : 1/1 réussie.",
    )
    probe = FakeProbe(outcome)
    llm = FakeLLM("Risques résiduels : couverture UI à compléter.")
    settings = make_settings(tmp_path)
    mission = make_mission()
    task = make_task(mission, "api_tester", "api_design")

    result = APITesterAgent(settings, llm=llm, probe=probe).run(task, mission)

    assert probe.calls == [mission.id]
    assert "Collection Postman générée" in result.summary
    assert "Sondes API réelles terminées" in result.summary
    assert "Risques résiduels" in result.summary
    assert (tmp_path / "postman" / "collections" / "football-qa.json").is_file()
    assert (
        tmp_path / "postman" / "environments" / "football-qa-test.json"
    ).is_file()
    assert (
        tmp_path
        / "workspace"
        / "missions"
        / mission.id
        / "api"
        / "openapi.json"
    ).is_file()
    assert any(path.endswith("probe.json") for path in result.evidence)


def test_api_tester_does_not_invent_anomaly_when_probe_is_blocked(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import app.agents.phase5 as phase5

    monkeypatch.setattr(phase5, "fetch_openapi", lambda *args, **kwargs: SPEC)
    outcome = ProbeOutcome(
        status="blocked",
        checks=[],
        anomalies=[],
        evidence_paths=[],
        summary="Sondes API réelles non exécutées : API injoignable.",
    )
    settings = make_settings(tmp_path)
    mission = make_mission()
    task = make_task(mission, "api_tester", "api_design")

    result = APITesterAgent(
        settings, llm=FakeLLM(), probe=FakeProbe(outcome)
    ).run(task, mission)

    assert "API injoignable" in result.summary
    assert "Anomalies reproductibles" not in result.summary


def test_reporter_uses_real_probe_evidence_for_anomalies(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    mission = make_mission()
    api_dir = (
        tmp_path / "workspace" / "missions" / mission.id / "api"
    )
    api_dir.mkdir(parents=True)
    (api_dir / "probe-results.json").write_text(
        json.dumps(
            {
                "status": "completed",
                "checks": [
                    {"name": "Ajout d'un favori", "skipped": False, "passed": False}
                ],
                "anomalies": [
                    {
                        "check": "Ajout d'un favori",
                        "method": "POST",
                        "path": "/api/favorites",
                        "expected": "201",
                        "actual": "HTTP 500",
                        "reproduction": "POST http://localhost:8002/api/favorites",
                        "response_excerpt": '{"detail": "boom"}',
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    task = make_task(mission, "qa_reporter", "report")

    report = QAReporterAgent(settings).run(
        task,
        mission,
        context={
            "tasks": [
                {
                    "agent": "api_tester",
                    "title": "API",
                    "status": "completed",
                    "result": "Sondes terminées",
                    "evidence": [],
                }
            ]
        },
    ).summary

    assert "Des sondes API réelles ont été exécutées" in report
    assert "POST http://localhost:8002/api/favorites" in report
    assert "HTTP 500" in report
    assert "Aucun test réel n'a été exécuté" not in report
    assert "Aucune anomalie déclarée" not in report


def test_reporter_without_probe_keeps_planning_report(tmp_path: Path) -> None:
    settings = make_settings(tmp_path, real_agents_enabled=False)
    mission = make_mission("Analyse l'application.")
    task = make_task(mission, "qa_reporter", "report")

    report = QAReporterAgent(settings).run(
        task,
        mission,
        context={"tasks": []},
    ).summary

    assert "Aucun test réel n'a été exécuté" in report
    assert "Aucune anomalie déclarée" in report
