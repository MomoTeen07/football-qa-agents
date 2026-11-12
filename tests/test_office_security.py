from __future__ import annotations

import http.client
import json
import threading
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import urlopen

import pytest

from app.config import PROJECT_ROOT
from app.domain.models import Mission
from app.events.bus import EventBus
from app.office import server as server_module
from app.office.server import SECURITY_HEADERS, create_server
from app.store.sqlite_store import SqliteStore


@pytest.fixture()
def store(tmp_path: Path) -> SqliteStore:
    return SqliteStore(tmp_path / "missions.db")


@pytest.fixture()
def office_server(store: SqliteStore):
    server = create_server(
        store,
        port=0,
        static_dir=PROJECT_ROOT / "office",
        max_sse_clients=2,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address[:2]
    yield server, host, port
    server.shutdown()
    server.server_close()
    thread.join(timeout=2)


@pytest.fixture()
def single_client_server(store: SqliteStore):
    server = create_server(
        store,
        port=0,
        static_dir=PROJECT_ROOT / "office",
        max_sse_clients=1,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address[:2]
    yield server, host, port
    server.shutdown()
    server.server_close()
    thread.join(timeout=2)


def request(host: str, port: int, method: str, path: str):
    connection = http.client.HTTPConnection(host, port, timeout=5)
    try:
        connection.request(method, path)
        response = connection.getresponse()
        body = response.read()
        return response.status, response, body
    finally:
        connection.close()


def assert_security_headers(response) -> None:
    for name, expected in SECURITY_HEADERS.items():
        assert response.headers.get(name) == expected, name


def read_sse_frame(stream) -> tuple[str, str]:
    event_line = stream.readline().decode("utf-8").strip()
    data_line = stream.readline().decode("utf-8").strip()
    blank = stream.readline().decode("utf-8")
    assert blank == "\n"
    assert event_line.startswith("event: ")
    assert data_line.startswith("data: ")
    return event_line.removeprefix("event: "), data_line.removeprefix("data: ")


def test_security_headers_are_set_on_every_response(
    office_server, store: SqliteStore
) -> None:
    _, host, port = office_server
    mission = store.create_mission(Mission(instruction="Mission bureau"))

    status, response, body = request(host, port, "GET", "/")
    assert status == 200
    assert_security_headers(response)

    status, response, _ = request(host, port, "GET", "/api/state?mission_id=bad%21id")
    assert status == 400
    assert_security_headers(response)

    status, response, _ = request(
        host, port, "GET", "/api/state?mission_id=mission-inconnue"
    )
    assert status == 404
    assert_security_headers(response)

    status, response, _ = request(host, port, "GET", f"/api/state?mission_id={mission.id}")
    assert status == 200
    assert_security_headers(response)


def test_unsupported_methods_return_405_with_headers(
    office_server,
) -> None:
    _, host, port = office_server

    for method in ("POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"):
        status, response, _ = request(host, port, method, "/api/state")
        assert status == 405, method
        assert response.getheader("Allow") == "GET"
        assert_security_headers(response)


def test_sse_rejects_clients_above_the_limit(
    single_client_server, store: SqliteStore
) -> None:
    server, host, port = single_client_server
    mission = store.create_mission(Mission(instruction="Mission SSE"))
    bus = EventBus(store)
    server.bus = bus
    bus.publish(mission.id, "mission_created")

    first = urlopen(f"http://{host}:{port}/events?mission_id={mission.id}", timeout=5)
    try:
        event, _ = read_sse_frame(first)
        assert event == "snapshot"
        assert server.sse_clients == 1

        with pytest.raises(HTTPError) as error:
            urlopen(f"http://{host}:{port}/events?mission_id={mission.id}", timeout=5)
        assert error.value.code == 503
        payload = json.loads(error.value.read().decode("utf-8"))
        assert "Trop de flux SSE" in payload["error"]
        assert_security_headers(error.value)
        assert server.sse_clients == 1
    finally:
        first.close()

    # Une déconnexion brutale peut ne pas être visible dès la première
    # écriture (le noyau acquitte le tampon). On publie jusqu'à ce que le RST
    # soit reçu et que le serveur libère explicitement le créneau SSE.
    expires = time.monotonic() + 5.0
    while server.sse_clients and time.monotonic() < expires:
        bus.publish(mission.id, "mission_ping")
        time.sleep(0.1)
    assert server.sse_clients == 0

    with urlopen(
        f"http://{host}:{port}/events?mission_id={mission.id}", timeout=5
    ) as retry:
        event, _ = read_sse_frame(retry)
        assert event == "snapshot"
        assert server.sse_clients == 1


def test_state_is_built_once_per_batch_of_events(
    office_server, store: SqliteStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    server, host, port = office_server
    mission = store.create_mission(Mission(instruction="Mission lot d'événements"))
    bus = EventBus(store)

    calls = {"count": 0}
    real_build = server_module.build_office_state

    def counting_build(*args, **kwargs):
        calls["count"] += 1
        return real_build(*args, **kwargs)

    events = [
        bus.publish(mission.id, f"mission_event_{index}")
        for index in range(3)
    ]

    class FakeStream:
        def __init__(self, store, mission_id) -> None:
            self.sent = False

        def attach_bus(self, bus) -> None:
            return None

        def initial(self) -> list:
            return []

        def wait(self, after_id: int, timeout: float = 1.0) -> list:
            if not self.sent:
                self.sent = True
                return events
            time.sleep(0.01)
            return []

    monkeypatch.setattr(server_module, "build_office_state", counting_build)
    monkeypatch.setattr(server_module, "OfficeEventStream", FakeStream)

    with urlopen(
        f"http://{host}:{port}/events?mission_id={mission.id}", timeout=5
    ) as response:
        event, _ = read_sse_frame(response)
        assert event == "snapshot"
        states = []
        for _ in range(3):
            event, data = read_sse_frame(response)
            assert event == "office"
            states.append(json.loads(data)["state"])

    assert calls["count"] == 2, "un instantané + un seul lot d'événements"
    assert states[0] == states[1] == states[2]


def test_sse_limit_is_never_below_one(
    store: SqliteStore,
) -> None:
    server = create_server(
        store,
        port=0,
        static_dir=PROJECT_ROOT / "office",
        max_sse_clients=0,
    )
    try:
        assert server.max_sse_clients == 1
    finally:
        server.server_close()
