from __future__ import annotations

import json
import threading
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import urlopen

import pytest

from app.config import PROJECT_ROOT, Settings
from app.domain.models import Mission, MissionStatus, Task, TaskStatus
from app.events.bus import EventBus
from app.office.catalog import AGENTS, agent_catalog
from app.office.server import create_server
from app.office.state import build_office_state, mission_summaries
from app.office.stream import OfficeEventStream
from app.orchestrator.manager import Manager
from app.store.sqlite_store import SqliteStore

EXPECTED_AGENTS = {
    "manager",
    "qa_analyst",
    "test_designer",
    "api_tester",
    "api_automation",
    "ui_automation",
    "devops",
    "qa_reporter",
}


@pytest.fixture()
def store(tmp_path: Path) -> SqliteStore:
    return SqliteStore(tmp_path / "missions.db")


def create_mission(
    store: SqliteStore,
    status: MissionStatus = MissionStatus.RUNNING,
) -> Mission:
    mission = Mission(instruction="Campagne complète API et UI", status=status)
    return store.create_mission(mission)


def add_task(
    store: SqliteStore,
    mission: Mission,
    key: str,
    agent: str,
    status: TaskStatus,
    *,
    depends_on: list[str] | None = None,
) -> Task:
    task = Task(
        mission_id=mission.id,
        key=key,
        agent=agent,
        title=f"Tâche {key}",
        status=status,
        depends_on=depends_on or [],
        result="Résultat réel" if status == TaskStatus.COMPLETED else None,
        evidence=["workspace/preuve.json"] if status == TaskStatus.COMPLETED else [],
    )
    return store.create_task(task)


def publish(bus: EventBus, mission: Mission, event_type: str, agent: str | None = None):
    return bus.publish(
        mission.id,
        event_type,
        agent=agent,
        payload={"title": f"Événement {event_type}"},
    )


# ----------------------------------------------------------------------
# Catalogue
# ----------------------------------------------------------------------
def test_catalog_contains_eight_distinct_characters() -> None:
    assert len(AGENTS) == 8
    assert {agent.id for agent in AGENTS} == EXPECTED_AGENTS
    assert len({agent.name for agent in AGENTS}) == 8
    assert len({agent.department for agent in AGENTS}) >= 5
    catalog = agent_catalog()
    assert all(item["department_label"] for item in catalog)
    assert all(item["summary"] for item in catalog)


# ----------------------------------------------------------------------
# État réel
# ----------------------------------------------------------------------
def test_state_maps_real_tasks_and_agent_statuses(store: SqliteStore) -> None:
    mission = create_mission(store)
    add_task(store, mission, "analysis", "qa_analyst", TaskStatus.COMPLETED)
    add_task(
        store,
        mission,
        "design",
        "test_designer",
        TaskStatus.RUNNING,
        depends_on=["analysis"],
    )
    add_task(
        store,
        mission,
        "api_design",
        "api_tester",
        TaskStatus.PENDING,
        depends_on=["design"],
    )
    add_task(store, mission, "report", "qa_reporter", TaskStatus.PENDING)
    publish(EventBus(store), mission, "mission_planned")

    state = build_office_state(store, mission.id)

    assert state["mission"]["id"] == mission.id
    assert state["mission"]["progress"] == 25
    assert state["stats"]["tasks_total"] == 4
    assert state["stats"]["tasks_done"] == 1
    assert state["stats"]["agents_working"] == 2  # manager + test_designer

    agents = {agent["id"]: agent for agent in state["agents"]}
    assert agents["qa_analyst"]["status"] == "done"
    assert agents["test_designer"]["status"] == "working"
    assert agents["api_tester"]["status"] == "waiting"
    assert agents["manager"]["status"] == "working"
    assert agents["qa_analyst"]["last_result"] == "Résultat réel"
    assert agents["qa_analyst"]["tasks_done"] == 1


def test_communications_are_derived_from_completed_dependencies(
    store: SqliteStore,
) -> None:
    mission = create_mission(store)
    add_task(store, mission, "analysis", "qa_analyst", TaskStatus.COMPLETED)
    add_task(
        store,
        mission,
        "design",
        "test_designer",
        TaskStatus.RUNNING,
        depends_on=["analysis"],
    )
    add_task(
        store,
        mission,
        "api_design",
        "api_tester",
        TaskStatus.PENDING,
        depends_on=["design"],
    )

    state = build_office_state(store, mission.id)

    assert state["communications"] == [
        {
            "from": "qa_analyst",
            "to": "test_designer",
            "task_key": "design",
            "task_title": "Tâche design",
            "depends_on": "analysis",
            "status": "running",
            "at": state["communications"][0]["at"],
        }
    ]


def test_no_mission_produces_an_empty_idle_office(store: SqliteStore) -> None:
    state = build_office_state(store)

    assert state["mission"] is None
    assert len(state["agents"]) == 8
    assert all(agent["status"] == "idle" for agent in state["agents"])
    assert state["events"] == []
    assert state["communications"] == []
    assert state["stats"]["progress"] == 0
    assert state["allure"] is None


def test_allure_summary_is_exposed_when_present(
    store: SqliteStore, tmp_path: Path
) -> None:
    mission = create_mission(store, MissionStatus.COMPLETED)
    allure_dir = tmp_path / "allure" / mission.id
    allure_dir.mkdir(parents=True)
    (allure_dir / "allure-summary.json").write_text(
        json.dumps(
            {
                "status": "completed",
                "totals": {
                    "total": 59,
                    "passed": 59,
                    "failed": 0,
                    "skipped": 0,
                    "anomalies": 0,
                },
            }
        ),
        encoding="utf-8",
    )

    state = build_office_state(store, mission.id, allure_root=tmp_path / "allure")

    assert state["allure"]["total"] == 59
    assert state["allure"]["passed"] == 59
    assert state["allure"]["anomalies"] == 0


def test_mission_summaries_are_compact_and_ordered(store: SqliteStore) -> None:
    first = create_mission(store, MissionStatus.COMPLETED)
    add_task(store, first, "analysis", "qa_analyst", TaskStatus.COMPLETED)
    second = Mission(instruction="Deuxième mission")
    store.create_mission(second)

    summaries = mission_summaries(store)

    assert [item["id"] for item in summaries] == [second.id, first.id]
    assert summaries[1]["progress"] == 100
    assert summaries[0]["instruction"] == "Deuxième mission"


# ----------------------------------------------------------------------
# Flux SSE / EventBus
# ----------------------------------------------------------------------
def test_event_stream_attaches_to_the_real_event_bus(store: SqliteStore) -> None:
    mission = create_mission(store)
    bus = EventBus(store)
    stream = OfficeEventStream(store, mission.id)
    stream.attach_bus(bus)

    event = publish(bus, mission, "mission_started")

    received = stream.wait(0, timeout=0.5)
    assert [item.id for item in received] == [event.id]
    assert stream.wait(event.id, timeout=0.05) == []


def test_event_stream_reads_persisted_events_and_deduplicates(
    store: SqliteStore,
) -> None:
    mission = create_mission(store)
    bus = EventBus(store)
    first = publish(bus, mission, "mission_created")
    second = publish(bus, mission, "mission_planned")

    stream = OfficeEventStream(store, mission.id)
    initial = stream.initial()

    assert [item.id for item in initial] == [first.id, second.id]
    assert [item.id for item in stream.initial()] == [first.id, second.id]


# ----------------------------------------------------------------------
# Serveur HTTP local
# ----------------------------------------------------------------------
@pytest.fixture()
def office_server(store: SqliteStore):
    server = create_server(
        store,
        port=0,
        static_dir=PROJECT_ROOT / "office",
        allure_root=None,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address[:2]
    yield server, f"http://{host}:{port}"
    server.shutdown()
    server.server_close()
    thread.join(timeout=2)


def http_get(url: str) -> tuple[int, str, str]:
    with urlopen(url, timeout=5) as response:
        return (
            response.status,
            response.headers.get("Content-Type", ""),
            response.read().decode("utf-8"),
        )


def test_server_serves_frontend_and_apis(
    office_server, store: SqliteStore
) -> None:
    _, base = office_server
    mission = create_mission(store)

    status, content_type, body = http_get(f"{base}/")
    assert status == 200
    assert content_type.startswith("text/html")
    assert "Football QA Agents" in body

    status, content_type, body = http_get(f"{base}/assets/app.js")
    assert status == 200
    assert content_type.startswith("text/javascript")
    assert "EventSource" in body

    status, content_type, body = http_get(f"{base}/api/state?mission_id={mission.id}")
    assert status == 200
    assert content_type.startswith("application/json")
    payload = json.loads(body)
    assert payload["mission"]["id"] == mission.id
    assert len(payload["agents"]) == 8

    status, _, body = http_get(f"{base}/api/missions")
    assert status == 200
    assert json.loads(body)["missions"][0]["id"] == mission.id

    with pytest.raises(HTTPError) as error:
        http_get(f"{base}/api/state?mission_id=inconnue")
    assert error.value.code == 404

    with pytest.raises(HTTPError) as error:
        http_get(f"{base}/api/state?mission_id=bad%21id")
    assert error.value.code == 400

    with pytest.raises(HTTPError) as error:
        http_get(f"{base}/assets/%2e%2e%2fapp%2fconfig.py")
    assert error.value.code == 404


def test_server_streams_a_real_snapshot_and_event(
    office_server, store: SqliteStore
) -> None:
    server, base = office_server
    mission = create_mission(store)
    bus = EventBus(store)
    server.bus = bus
    publish(bus, mission, "mission_created")

    with urlopen(f"{base}/events?mission_id={mission.id}", timeout=5) as response:
        assert response.headers.get("Content-Type", "").startswith(
            "text/event-stream"
        )
        first = response.readline().decode("utf-8")
        second = response.readline().decode("utf-8")
        third = response.readline().decode("utf-8")
        assert first.startswith("event: snapshot")
        assert second.startswith("data: ")
        payload = json.loads(second.removeprefix("data: "))
        assert payload["mission"]["id"] == mission.id
        assert third == "\n"


def test_server_refuses_a_non_local_interface(store: SqliteStore) -> None:
    with pytest.raises(ValueError):
        create_server(store, host="0.0.0.0", port=0, static_dir=PROJECT_ROOT / "office")


# ----------------------------------------------------------------------
# Garanties du frontend et des événements
# ----------------------------------------------------------------------
def test_frontend_is_offline_and_has_no_random_animation() -> None:
    assets = sorted((PROJECT_ROOT / "office" / "assets").glob("*.js"))
    assert assets
    # Le namespace SVG est la seule occurrence autorisée de « http:// ».
    svg_namespace = "http://www.w3.org/2000/svg"
    for path in assets:
        text = path.read_text(encoding="utf-8").replace(svg_namespace, "")
        assert "Math.random" not in text
        assert "setInterval" not in text
        assert "https://" not in text
        assert "http://" not in text


def test_task_events_carry_the_task_key_for_the_office(
    tmp_path: Path,
) -> None:
    settings = Settings(
        mission_db_path=tmp_path / "missions.db",
        reports_dir=tmp_path / "reports",
        workspace_dir=tmp_path / "workspace",
        postman_dir=tmp_path / "postman",
        allure_results_dir=tmp_path / "allure",
        real_agents_enabled=False,
    )
    manager = Manager(settings)
    try:
        mission = manager.create_mission("Analyse l'application et propose un plan de test.")
        manager.run_mission(mission.id)
        events = manager.get_events(mission.id)
    finally:
        manager.close()

    task_events = [
        event
        for event in events
        if event.type in {"task_started", "task_completed", "task_failed", "task_blocked"}
    ]
    assert task_events
    assert all("key" in event.payload for event in task_events)
