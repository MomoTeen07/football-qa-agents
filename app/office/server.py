"""Serveur HTTP local du bureau virtuel.

Le serveur est volontairement minimal et sans dépendance supplémentaire :
`http.server` de la bibliothèque standard, écoute strictement sur la boucle
locale, sert le frontend `office/` et expose un flux SSE branché sur les
événements réels du système QA.

Il ne démarre aucune mission, ne planifie rien et n'expose aucun secret.
"""

from __future__ import annotations

import json
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

from app.config import PROJECT_ROOT
from app.office.state import (
    build_office_state,
    mission_summaries,
    serialize_event,
)
from app.office.stream import OfficeEventStream
from app.security import validate_mission_id
from app.store.sqlite_store import SqliteStore

MIME_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".webp": "image/webp",
    ".ico": "image/x-icon",
    ".woff2": "font/woff2",
}

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cross-Origin-Resource-Policy": "same-origin",
    "Content-Security-Policy": (
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; connect-src 'self'; font-src 'self'; "
        "object-src 'none'; base-uri 'none'; frame-ancestors 'none'"
    ),
}

# Le bureau est local : une douzaine d'onglets simultanés suffit largement.
# Au-delà, la réponse est un 503 explicite plutôt qu'un thread bloqué.
MAX_SSE_CLIENTS = 12
SSE_WRITE_TIMEOUT_SECONDS = 10.0


def _valid_mission_id(value: str | None) -> bool:
    if not value:
        return False
    try:
        validate_mission_id(value)
    except ValueError:
        return False
    return True


class OfficeHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(
        self,
        address: tuple[str, int],
        store: SqliteStore,
        static_dir: Path,
        *,
        bus=None,
        allure_root: Path | None = None,
        secrets: tuple[str, ...] = (),
        max_sse_clients: int = MAX_SSE_CLIENTS,
    ) -> None:
        super().__init__(address, OfficeRequestHandler)
        self.store = store
        self.static_dir = Path(static_dir).resolve()
        self.bus = bus
        self.allure_root = Path(allure_root) if allure_root else None
        self.secrets = tuple(secrets)
        self.max_sse_clients = max(1, int(max_sse_clients))
        self.quiet = True
        self.stopping = False
        self._sse_lock = threading.Lock()
        self._sse_clients = 0

    def try_acquire_sse(self) -> bool:
        with self._sse_lock:
            if self._sse_clients >= self.max_sse_clients:
                return False
            self._sse_clients += 1
            return True

    def release_sse(self) -> None:
        with self._sse_lock:
            self._sse_clients = max(0, self._sse_clients - 1)

    @property
    def sse_clients(self) -> int:
        with self._sse_lock:
            return self._sse_clients

    def shutdown(self) -> None:
        self.stopping = True
        super().shutdown()


class OfficeRequestHandler(BaseHTTPRequestHandler):
    server_version = "FootballQAOffice/1.0"
    server: OfficeHTTPServer

    # ------------------------------------------------------------------
    # Réponses
    # ------------------------------------------------------------------
    def log_message(self, format: str, *args) -> None:  # noqa: A002
        if not getattr(self.server, "quiet", True):
            super().log_message(format, *args)

    def _common_headers(self) -> None:
        for key, value in SECURITY_HEADERS.items():
            self.send_header(key, value)

    def _send_json(self, payload: dict, status: int = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self._common_headers()
        self.end_headers()
        self.wfile.write(body)

    def _send_error_json(self, status: int, message: str) -> None:
        self._send_json({"error": message}, status)

    def _method_not_allowed(self) -> None:
        body = json.dumps(
            {"error": "Méthode non supportée : GET uniquement."},
            ensure_ascii=False,
        ).encode("utf-8")
        self.send_response(HTTPStatus.METHOD_NOT_ALLOWED)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Allow", "GET")
        self.send_header("Cache-Control", "no-store")
        self._common_headers()
        self.end_headers()
        self.wfile.write(body)

    # Toute méthode autre que GET reçoit une réponse claire et les en-têtes de
    # sécurité, jamais une page d'erreur HTML par défaut.
    def do_HEAD(self) -> None:  # noqa: N802
        self._method_not_allowed()

    def do_POST(self) -> None:  # noqa: N802
        self._method_not_allowed()

    def do_PUT(self) -> None:  # noqa: N802
        self._method_not_allowed()

    def do_PATCH(self) -> None:  # noqa: N802
        self._method_not_allowed()

    def do_DELETE(self) -> None:  # noqa: N802
        self._method_not_allowed()

    def do_OPTIONS(self) -> None:  # noqa: N802
        self._method_not_allowed()

    def _send_file(self, path: Path) -> None:
        try:
            body = path.read_bytes()
        except OSError:
            self._send_error_json(HTTPStatus.NOT_FOUND, "Fichier introuvable.")
            return
        content_type = MIME_TYPES.get(path.suffix.lower(), "application/octet-stream")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self._common_headers()
        self.end_headers()
        self.wfile.write(body)

    def _static_path(self, request_path: str) -> Path | None:
        relative = request_path.lstrip("/")
        if relative in {"", "index.html"}:
            relative = "index.html"
        candidate = (self.server.static_dir / relative).resolve()
        if not candidate.is_relative_to(self.server.static_dir):
            return None
        if not candidate.is_file():
            return None
        return candidate

    # ------------------------------------------------------------------
    # Routage
    # ------------------------------------------------------------------
    def do_GET(self) -> None:  # noqa: N802
        parsed = urlsplit(self.path)
        path = unquote(parsed.path)
        query = parse_qs(parsed.query)
        mission_id = (query.get("mission_id") or [None])[0]

        if mission_id is not None and not _valid_mission_id(mission_id):
            self._send_error_json(HTTPStatus.BAD_REQUEST, "Identifiant de mission invalide.")
            return

        if path == "/api/health":
            self._send_json(
                {
                    "status": "ok",
                    "mission": self._requested_mission(mission_id),
                }
            )
            return

        if path == "/api/state":
            self._serve_state(mission_id)
            return

        if path == "/api/missions":
            self._send_json(
                {
                    "missions": mission_summaries(
                        self.server.store,
                        secrets=self.server.secrets,
                    ),
                    "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                }
            )
            return

        if path == "/events":
            self._serve_events(mission_id)
            return

        if path == "/favicon.ico":
            self.send_response(HTTPStatus.NO_CONTENT)
            self._common_headers()
            self.end_headers()
            return

        static = self._static_path(path)
        if static is None:
            self._send_error_json(HTTPStatus.NOT_FOUND, "Ressource introuvable.")
            return
        self._send_file(static)

    def _requested_mission(self, mission_id: str | None) -> str | None:
        if mission_id:
            return mission_id if self.server.store.get_mission(mission_id) else None
        missions = self.server.store.list_missions()
        return missions[0].id if missions else None

    def _serve_state(self, mission_id: str | None) -> None:
        if mission_id and self.server.store.get_mission(mission_id) is None:
            self._send_error_json(HTTPStatus.NOT_FOUND, "Mission introuvable.")
            return
        state = build_office_state(
            self.server.store,
            mission_id,
            allure_root=self.server.allure_root,
            secrets=self.server.secrets,
        )
        self._send_json(state)

    # ------------------------------------------------------------------
    # SSE
    # ------------------------------------------------------------------
    def _send_sse(self, event: str, payload: dict) -> None:
        data = json.dumps(payload, ensure_ascii=False)
        frame = f"event: {event}\ndata: {data}\n\n".encode("utf-8")
        self.wfile.write(frame)
        self.wfile.flush()

    def _serve_events(self, mission_id: str | None) -> None:
        resolved = self._requested_mission(mission_id)
        if resolved is None:
            self._send_error_json(HTTPStatus.NOT_FOUND, "Aucune mission à afficher.")
            return

        if not self.server.try_acquire_sse():
            self._send_error_json(
                HTTPStatus.SERVICE_UNAVAILABLE,
                "Trop de flux SSE ouverts : fermez un onglet puis réessayez.",
            )
            return

        try:
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Accel-Buffering", "no")
            self._common_headers()
            self.end_headers()
            self.close_connection = True
            # Un client lent ne doit pas immobiliser un thread indéfiniment.
            self.connection.settimeout(SSE_WRITE_TIMEOUT_SECONDS)

            stream = OfficeEventStream(self.server.store, resolved)
            if self.server.bus is not None:
                stream.attach_bus(self.server.bus)

            events = stream.initial()
            self._send_sse(
                "snapshot",
                build_office_state(
                    self.server.store,
                    resolved,
                    allure_root=self.server.allure_root,
                    secrets=self.server.secrets,
                ),
            )
            last_id = max((event.id or 0) for event in events) if events else 0
            last_heartbeat = time.monotonic()

            while not self.server.stopping:
                new_events = stream.wait(last_id, timeout=1.0)
                if new_events:
                    # Un seul instantané par lot : plusieurs événements proches
                    # ne doivent pas déclencher plusieurs reconstructions.
                    batch_state = build_office_state(
                        self.server.store,
                        resolved,
                        allure_root=self.server.allure_root,
                        secrets=self.server.secrets,
                    )
                    for event in new_events:
                        last_id = max(last_id, event.id or 0)
                        self._send_sse(
                            "office",
                            {
                                "event": serialize_event(
                                    event, secrets=self.server.secrets
                                ),
                                "state": batch_state,
                            },
                        )
                if time.monotonic() - last_heartbeat >= 15:
                    self.wfile.write(b": keep-alive\n\n")
                    self.wfile.flush()
                    last_heartbeat = time.monotonic()
        except (BrokenPipeError, ConnectionResetError, TimeoutError, OSError):
            return
        finally:
            self.server.release_sse()


def create_server(
    store: SqliteStore,
    *,
    host: str = "127.0.0.1",
    port: int = 5180,
    static_dir: Path | None = None,
    bus=None,
    allure_root: Path | None = None,
    secrets: tuple[str, ...] = (),
    max_sse_clients: int = MAX_SSE_CLIENTS,
) -> OfficeHTTPServer:
    """Crée le serveur local. Refuse toute interface non locale."""

    if host not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("Le bureau virtuel écoute uniquement sur la boucle locale.")
    static = Path(static_dir) if static_dir else PROJECT_ROOT / "office"
    if not (static / "index.html").is_file():
        raise FileNotFoundError(f"Frontend du bureau introuvable : {static}")
    return OfficeHTTPServer(
        (host, port),
        store,
        static,
        bus=bus,
        allure_root=allure_root,
        secrets=secrets,
        max_sse_clients=max_sse_clients,
    )
