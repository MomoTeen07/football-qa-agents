"""Constats de sécurité R1 à R4 (phase 9, jalon J0).

Ces tests décrivent le comportement **attendu** après durcissement. Au jalon
J0 ils sont marqués `xfail(strict=True)` : ils doivent échouer sur le code
actuel (défaut confirmé) et le marqueur sera retiré au jalon J1 quand les
correctifs seront livrés. Un `xfail` strict qui se met à passer casse la suite,
ce qui force la suppression du marqueur.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.config import Settings
from app.domain.models import Mission, MissionStatus, Task, TaskStatus
from app.events.bus import EventBus
from app.office.state import build_office_state, serialize_event
from app.store.sqlite_store import SqliteStore
from app.tools.devops import DevOpsPromotion
from app.tools.workspace import mission_workspace, write_mission_text

SENTINEL = "sentinel-phase9-do-not-leak-7f21"


def make_settings(tmp_path: Path) -> Settings:
    return Settings(
        _env_file=None,
        real_agents_enabled=False,
        mission_db_path=tmp_path / "missions.db",
        workspace_dir=tmp_path / "workspace",
        reports_dir=tmp_path / "reports",
        postman_dir=tmp_path / "postman",
        allure_results_dir=tmp_path / "allure",
        gemini_api_key=SENTINEL,
        telegram_bot_token="",
        devops_repo_dir=tmp_path / "repo",
    )


# ----------------------------------------------------------------------
# R1 — identifiants de mission non validés hors du serveur du bureau
# ----------------------------------------------------------------------
@pytest.mark.xfail(
    strict=True,
    reason="R1 : mission_workspace accepte encore une traversée d'identifiant",
)
def test_mission_workspace_refuses_traversal(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)

    with pytest.raises(ValueError):
        mission_workspace(settings, "../evasion")

    assert not (tmp_path / "workspace" / "evasion").exists()


@pytest.mark.xfail(
    strict=True,
    reason="R1 : la promotion DevOps construit un chemin avec l'identifiant brut",
)
def test_devops_refuses_a_traversing_mission_id(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    (settings.devops_repo_dir / ".git").mkdir(parents=True, exist_ok=True)

    with pytest.raises(ValueError):
        DevOpsPromotion(settings, runner=lambda command, cwd: None).run("../evasion")

    assert not (tmp_path / "workspace" / "evasion").exists()


# ----------------------------------------------------------------------
# R2 — écriture hors du dossier de mission via un chemin relatif
# ----------------------------------------------------------------------
@pytest.mark.xfail(
    strict=True,
    reason="R2 : write_mission_text accepte encore ../../evasion.txt",
)
def test_write_mission_text_stays_inside_the_mission_directory(
    tmp_path: Path,
) -> None:
    settings = make_settings(tmp_path)

    with pytest.raises(ValueError):
        write_mission_text(settings, "mission-ok", "../../evasion.txt", SENTINEL)

    assert not (tmp_path / "workspace" / "evasion.txt").exists()
    assert not (tmp_path / "evasion.txt").exists()


# ----------------------------------------------------------------------
# R3 — rédaction absente de la sérialisation du bureau
# ----------------------------------------------------------------------
@pytest.fixture()
def office_payload(tmp_path: Path) -> tuple[SqliteStore, Mission]:
    store = SqliteStore(tmp_path / "office.db")
    mission = Mission(instruction=f"Analyser {SENTINEL}", status=MissionStatus.RUNNING)
    store.create_mission(mission)
    store.create_task(
        Task(
            mission_id=mission.id,
            key="analysis",
            agent="qa_analyst",
            title=f"Tâche {SENTINEL}",
            status=TaskStatus.COMPLETED,
            result=f"résultat réel {SENTINEL}",
            evidence=[f"workspace/{SENTINEL}.json"],
        )
    )
    bus = EventBus(store)
    bus.publish(
        mission.id,
        "task_completed",
        agent="qa_analyst",
        payload={"key": "analysis", "summary": SENTINEL},
    )
    return store, mission


@pytest.mark.xfail(
    strict=True,
    reason="R3 : build_office_state ne rédige pas task.result et event.payload",
)
def test_office_state_redacts_known_secrets(office_payload) -> None:
    store, mission = office_payload

    state = build_office_state(store, mission.id, secrets=(SENTINEL,))

    assert SENTINEL not in json.dumps(state, ensure_ascii=False)


@pytest.mark.xfail(
    strict=True,
    reason="R3 : serialize_event renvoie le payload brut",
)
def test_serialize_event_redacts_known_secrets(office_payload) -> None:
    store, mission = office_payload
    event = store.list_events(mission.id)[0]

    payload = serialize_event(event, secrets=(SENTINEL,))

    assert SENTINEL not in json.dumps(payload, ensure_ascii=False)


# ----------------------------------------------------------------------
# R4 — aucun test de non-fuite sentinelle dans les rapports
# ----------------------------------------------------------------------
@pytest.mark.xfail(
    strict=True,
    reason="R4 : le rapport Markdown et la synthèse JSON ne rédigent pas les secrets connus",
)
def test_reporter_redacts_known_secrets(tmp_path: Path) -> None:
    from app.agents.phase7 import QAReporterAgent

    settings = make_settings(tmp_path)
    mission = Mission(instruction=f"Analyser {SENTINEL}")
    task = Task(
        mission_id=mission.id,
        key="report",
        agent="qa_reporter",
        title=f"Rapport {SENTINEL}",
    )

    result = QAReporterAgent(settings).run(
        task,
        mission,
        context={
            "tasks": [
                {
                    "agent": "qa_analyst",
                    "title": f"Analyse {SENTINEL}",
                    "status": "completed",
                    "result": SENTINEL,
                    "evidence": [],
                }
            ]
        },
    )

    assert SENTINEL not in result.summary
    assert SENTINEL not in (settings.reports_dir / f"{mission.id}.json").read_text(
        encoding="utf-8"
    )


@pytest.mark.xfail(
    strict=True,
    reason="R4 : les fichiers Allure ne rédigent pas les secrets connus",
)
def test_allure_files_redact_known_secrets(tmp_path: Path) -> None:
    from app.agents.phase7 import QAReporterAgent

    settings = make_settings(tmp_path)
    mission = Mission(instruction="Vérifier les sondes")
    payload = {
        "status": "completed",
        "base_url": "http://localhost:8002",
        "checks": [
            {
                "name": f"Santé {SENTINEL}",
                "method": "GET",
                "path": "/health",
                "passed": True,
                "response_excerpt": f'{{"token": "{SENTINEL}"}}',
            }
        ],
        "anomalies": [
            {
                "check": f"Santé {SENTINEL}",
                "expected": "200",
                "actual": SENTINEL,
                "reproduction": f"GET /health {SENTINEL}",
            }
        ],
    }
    path = (
        settings.workspace_dir
        / "missions"
        / mission.id
        / "api"
        / "probe-results.json"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    task = Task(
        mission_id=mission.id,
        key="report",
        agent="qa_reporter",
        title="Rapport",
    )

    QAReporterAgent(settings).run(task, mission, context={"tasks": []})

    results_dir = settings.allure_results_dir / mission.id
    files = sorted(results_dir.glob("*"))
    assert files
    for file in files:
        if file.is_file():
            assert SENTINEL not in file.read_text(encoding="utf-8"), file.name


# ----------------------------------------------------------------------
# Les identifiants réels existants doivent continuer de fonctionner
# ----------------------------------------------------------------------
@pytest.mark.xfail(
    strict=True,
    reason="R1 : la validation centralisée n'existe pas encore",
)
def test_valid_mission_ids_still_work(tmp_path: Path) -> None:
    from app.security import validate_mission_id

    assert validate_mission_id("7e30889c18cd") == "7e30889c18cd"
    assert validate_mission_id("mission_test-01") == "mission_test-01"
