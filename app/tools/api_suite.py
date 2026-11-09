"""Automatisation pytest réelle des tests API (phase 6).

La suite est générée dans le workspace de la mission à partir de la collection
Postman et des preuves de la phase 5, puis réellement exécutée par pytest.
Aucune anomalie n'est déclarée en cas de cible injoignable : le statut est
alors ``blocked``, sans anomalie applicative inventée.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path

import httpx

from app.config import Settings, get_settings
from app.tools.api_probe import ensure_test_api_url, UnsafeTargetError
from app.tools.redaction import redact_text
from app.tools.workspace import mission_workspace, write_mission_json, write_mission_text

STATUS_PATTERN = re.compile(r"pm\.response\.to\.have\.status\((\d{3})\)")
PATH_VARIABLES = {"code": "PL", "team_id": "57"}

API_TEST_CATALOG: dict[str, dict[str, str]] = {
    "test_health_returns_ok": {
        "method": "GET",
        "path": "/health",
        "expected": "HTTP 200 avec status ok",
    },
    "test_leagues_return_six_entries": {
        "method": "GET",
        "path": "/api/football/leagues",
        "expected": "HTTP 200 avec 6 championnats et les champs code/name/country",
    },
    "test_standings_return_rows": {
        "method": "GET",
        "path": "/api/football/leagues/PL/standings",
        "expected": "HTTP 200 avec un classement non vide et les champs attendus",
    },
    "test_matches_return_rows": {
        "method": "GET",
        "path": "/api/football/leagues/PL/matches",
        "expected": "HTTP 200 avec des matchs non vides",
    },
    "test_team_detail_returns_arsenal": {
        "method": "GET",
        "path": "/api/football/leagues/PL/teams/57",
        "expected": "HTTP 200 avec l'équipe 57 Arsenal",
    },
    "test_unknown_league_returns_404": {
        "method": "GET",
        "path": "/api/football/leagues/XX/standings",
        "expected": "HTTP 404",
    },
    "test_login_user1_returns_token": {
        "method": "POST",
        "path": "/api/auth/login",
        "expected": "HTTP 200 avec un access_token",
    },
    "test_login_user2_returns_token": {
        "method": "POST",
        "path": "/api/auth/login",
        "expected": "HTTP 200 avec un access_token",
    },
    "test_me_requires_token": {
        "method": "GET",
        "path": "/api/users/me",
        "expected": "HTTP 401 sans jeton",
    },
    "test_me_returns_user1": {
        "method": "GET",
        "path": "/api/users/me",
        "expected": "HTTP 200 avec l'email de l'utilisateur 1",
    },
    "test_bad_password_returns_401": {
        "method": "POST",
        "path": "/api/auth/login",
        "expected": "HTTP 401 avec un mauvais mot de passe",
    },
    "test_duplicate_registration_returns_409": {
        "method": "POST",
        "path": "/api/auth/register",
        "expected": "HTTP 409 avec un email déjà utilisé",
    },
    "test_short_password_returns_422": {
        "method": "POST",
        "path": "/api/auth/register",
        "expected": "HTTP 422 avec un mot de passe trop court",
    },
    "test_nominal_registration_and_login": {
        "method": "POST",
        "path": "/api/auth/register",
        "expected": "HTTP 201 puis connexion 200 avec le nouvel utilisateur",
    },
    "test_favorites_require_token": {
        "method": "GET",
        "path": "/api/favorites",
        "expected": "HTTP 401 sans jeton",
    },
    "test_add_favorite": {
        "method": "POST",
        "path": "/api/favorites",
        "expected": "HTTP 201 avec un favori créé",
    },
    "test_duplicate_favorite_returns_409": {
        "method": "POST",
        "path": "/api/favorites",
        "expected": "HTTP 409 pour un favori en double",
    },
    "test_favorite_isolation_between_users": {
        "method": "GET",
        "path": "/api/favorites",
        "expected": "favori visible par son propriétaire et invisible pour l'autre",
    },
    "test_cross_user_delete_is_refused": {
        "method": "DELETE",
        "path": "/api/favorites/{favorite_id}",
        "expected": "HTTP 404 lors d'une suppression croisée",
    },
    "test_delete_own_favorite": {
        "method": "DELETE",
        "path": "/api/favorites/{favorite_id}",
        "expected": "HTTP 204 puis favori absent de la liste",
    },
}


@dataclass
class ApiSuiteAssets:
    suite_path: Path
    postman_cases: list[dict]
    sources: dict
    evidence_paths: list[str] = field(default_factory=list)


@dataclass
class ApiSuiteCheck:
    name: str
    outcome: str
    duration_s: float
    detail: str = ""
    method: str = ""
    path: str = ""
    expected: str = ""


@dataclass
class ApiSuiteOutcome:
    status: str
    checks: list[ApiSuiteCheck] = field(default_factory=list)
    anomalies: list[dict] = field(default_factory=list)
    evidence_paths: list[str] = field(default_factory=list)
    summary: str = ""
    blocked_reason: str | None = None
    sources: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


def _postman_requests(collection: dict) -> list[dict]:
    requests: list[dict] = []

    def visit(items: list[dict]) -> None:
        for item in items:
            if "item" in item:
                visit(item.get("item") or [])
                continue
            request = item.get("request")
            if not isinstance(request, dict):
                continue
            method = str(request.get("method", "GET")).upper()
            url = request.get("url")
            raw = url.get("raw", "") if isinstance(url, dict) else str(url or "")
            expected = _expected_status(item)
            requests.append(
                {
                    "name": item.get("name") or f"{method} {raw}",
                    "method": method,
                    "raw_url": raw,
                    "headers": request.get("header") or [],
                    "expected_status": expected,
                }
            )

    visit(collection.get("item") or [])
    return requests


def _expected_status(item: dict) -> int | None:
    for event in item.get("event") or []:
        script = event.get("script") or {}
        for line in script.get("exec") or []:
            match = STATUS_PATTERN.search(str(line))
            if match:
                return int(match.group(1))
    return None


def _resolve_postman_path(raw: str) -> str | None:
    path = raw.replace("{{baseUrl}}", "")
    for name, value in PATH_VARIABLES.items():
        path = path.replace(f"{{{{{name}}}}}", value)
    if "{{" in path:
        return None
    path = path.split("?", 1)[0]
    if not path.startswith("/"):
        return None
    return path


def postman_safe_cases(collection: dict) -> list[dict]:
    """Extrait les requêtes GET sûres de la collection, réutilisables en pytest."""
    cases: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for request in _postman_requests(collection):
        if request["method"] != "GET":
            continue
        path = _resolve_postman_path(request["raw_url"])
        if path is None:
            continue
        key = (request["method"], path)
        if key in seen:
            continue
        seen.add(key)
        requires_bearer = any(
            str(header.get("key", "")).lower() == "authorization"
            for header in request["headers"]
            if isinstance(header, dict)
        )
        cases.append(
            {
                "name": request["name"],
                "method": request["method"],
                "path": path,
                "expected_status": request["expected_status"] or 200,
                "requires_bearer": requires_bearer,
            }
        )
    return cases


def _load_collection(settings: Settings, mission_id: str) -> tuple[dict | None, str | None]:
    collection_path = (
        Path(settings.postman_dir) / "collections" / "football-qa.json"
    )
    if collection_path.is_file():
        try:
            return json.loads(collection_path.read_text(encoding="utf-8")), str(
                collection_path
            )
        except ValueError:
            pass

    openapi_path = (
        Path(settings.workspace_dir)
        / "missions"
        / mission_id
        / "api"
        / "openapi.json"
    )
    if openapi_path.is_file():
        try:
            from app.tools.openapi_postman import build_postman_collection

            spec = json.loads(openapi_path.read_text(encoding="utf-8"))
            return (
                build_postman_collection(
                    spec, settings.test_api_url.rstrip("/")
                ),
                f"{openapi_path} (collection reconstruite)",
            )
        except (OSError, ValueError):
            return None, None
    return None, None


def _load_probe_results(settings: Settings, mission_id: str) -> tuple[dict | None, str | None]:
    path = (
        Path(settings.workspace_dir)
        / "missions"
        / mission_id
        / "api"
        / "probe-results.json"
    )
    if not path.is_file():
        return None, None
    try:
        return json.loads(path.read_text(encoding="utf-8")), str(path)
    except (OSError, ValueError):
        return None, None


SUITE_TEMPLATE = '''# Suite pytest générée par l'agent API Automation (football-qa-agents).
# Exécution réelle contre la stack de test isolée uniquement.
from __future__ import annotations

import os
import uuid

import httpx
import pytest

BASE_URL = os.environ["FOOTBALL_QA_API_URL"].rstrip("/")
USER1_EMAIL = os.environ["FOOTBALL_QA_USER1_EMAIL"]
USER1_PASSWORD = os.environ["FOOTBALL_QA_USER1_PASSWORD"]
USER2_EMAIL = os.environ["FOOTBALL_QA_USER2_EMAIL"]
USER2_PASSWORD = os.environ["FOOTBALL_QA_USER2_PASSWORD"]
AUTO_PASSWORD = "QaTest123!"
PROBE_TEAM_ID = 999001
PROBE_LEAGUE = "PL"
PROBE_TEAM_NAME = "QA Probe FC"
AUTO_TEAM_ID = 57
AUTO_TEAM_NAME = "Arsenal"

POSTMAN_CASES = __POSTMAN_CASES__
TEST_CATALOG = __TEST_CATALOG__


@pytest.fixture(scope="session")
def client():
    with httpx.Client(
        base_url=BASE_URL,
        timeout=20.0,
        follow_redirects=False,
    ) as instance:
        yield instance


def login(client, email, password):
    response = client.post(
        "/api/auth/login",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200, (
        "connexion attendue 200, obtenu " + str(response.status_code)
    )
    token = response.json().get("access_token")
    assert token, "jeton d'accès absent de la réponse de connexion"
    return token


@pytest.fixture(scope="session")
def token1(client):
    return login(client, USER1_EMAIL, USER1_PASSWORD)


@pytest.fixture(scope="session")
def token2(client):
    return login(client, USER2_EMAIL, USER2_PASSWORD)


def auth(token):
    return {"Authorization": "Bearer " + token}


def clear_probe_favorites(client, token):
    response = client.get("/api/favorites", headers=auth(token))
    assert response.status_code == 200, (
        "liste des favoris attendue 200, obtenu " + str(response.status_code)
    )
    for favorite in response.json():
        if favorite.get("team_id") == PROBE_TEAM_ID:
            client.delete(
                "/api/favorites/" + str(favorite["id"]),
                headers=auth(token),
            )


@pytest.fixture()
def favorite(client, token1):
    clear_probe_favorites(client, token1)
    response = client.post(
        "/api/favorites",
        headers=auth(token1),
        json={
            "team_id": AUTO_TEAM_ID,
            "league_code": PROBE_LEAGUE,
            "team_name": AUTO_TEAM_NAME,
            "team_crest": "",
        },
    )
    assert response.status_code == 201, (
        "création du favori attendue 201, obtenu " + str(response.status_code)
    )
    payload = response.json()
    assert isinstance(payload.get("id"), int), "identifiant de favori absent"
    created = payload
    yield created
    client.delete(
        "/api/favorites/" + str(created["id"]),
        headers=auth(token1),
    )


def test_health_returns_ok(client):
    response = client.get("/health")
    assert response.status_code == 200, "HTTP " + str(response.status_code)
    assert response.json().get("status") == "ok"


def test_leagues_return_six_entries(client):
    response = client.get("/api/football/leagues")
    assert response.status_code == 200, "HTTP " + str(response.status_code)
    payload = response.json()
    assert isinstance(payload, list), "réponse non liste"
    assert len(payload) == 6, "nombre de championnats " + str(len(payload))
    for league in payload:
        assert {"code", "name", "country"} <= set(league), "champs manquants"


def test_standings_return_rows(client):
    response = client.get("/api/football/leagues/PL/standings")
    assert response.status_code == 200, "HTTP " + str(response.status_code)
    payload = response.json()
    assert isinstance(payload, list) and payload, "classement vide"
    row = payload[0]
    assert {"position", "team", "playedGames", "won", "draw", "lost", "points"} <= set(row)
    assert isinstance(row["team"].get("id"), int)


def test_matches_return_rows(client):
    response = client.get("/api/football/leagues/PL/matches")
    assert response.status_code == 200, "HTTP " + str(response.status_code)
    payload = response.json()
    assert isinstance(payload, list) and payload, "aucun match"
    match = payload[0]
    assert {"id", "utcDate", "status", "homeTeam", "awayTeam"} <= set(match)


def test_team_detail_returns_arsenal(client):
    response = client.get("/api/football/leagues/PL/teams/57")
    assert response.status_code == 200, "HTTP " + str(response.status_code)
    payload = response.json()
    assert payload.get("id") == 57
    assert payload.get("name") == "Arsenal"


def test_unknown_league_returns_404(client):
    response = client.get("/api/football/leagues/XX/standings")
    assert response.status_code == 404, "HTTP " + str(response.status_code)


def test_login_user1_returns_token(client):
    token = login(client, USER1_EMAIL, USER1_PASSWORD)
    assert isinstance(token, str) and token


def test_login_user2_returns_token(client):
    token = login(client, USER2_EMAIL, USER2_PASSWORD)
    assert isinstance(token, str) and token


def test_me_requires_token(client):
    response = client.get("/api/users/me")
    assert response.status_code == 401, "HTTP " + str(response.status_code)


def test_me_returns_user1(client, token1):
    response = client.get("/api/users/me", headers=auth(token1))
    assert response.status_code == 200, "HTTP " + str(response.status_code)
    assert response.json().get("email") == USER1_EMAIL


def test_bad_password_returns_401(client):
    response = client.post(
        "/api/auth/login",
        json={"email": USER1_EMAIL, "password": "MotDePasseIncorrect123!"},
    )
    assert response.status_code == 401, "HTTP " + str(response.status_code)


def test_duplicate_registration_returns_409(client):
    response = client.post(
        "/api/auth/register",
        json={"email": USER1_EMAIL, "password": AUTO_PASSWORD, "name": "QA Doublon"},
    )
    assert response.status_code == 409, "HTTP " + str(response.status_code)


def test_short_password_returns_422(client):
    response = client.post(
        "/api/auth/register",
        json={
            "email": "qa.invalide@example.com",
            "password": "court",
            "name": "QA",
        },
    )
    assert response.status_code == 422, "HTTP " + str(response.status_code)


def test_nominal_registration_and_login(client):
    email = "qa.auto." + uuid.uuid4().hex[:10] + "@example.com"
    response = client.post(
        "/api/auth/register",
        json={"email": email, "password": AUTO_PASSWORD, "name": "QA Automatisation"},
    )
    assert response.status_code == 201, "HTTP " + str(response.status_code)
    token = response.json().get("access_token")
    assert token, "jeton absent après inscription"
    login_response = client.post(
        "/api/auth/login",
        json={"email": email, "password": AUTO_PASSWORD},
    )
    assert login_response.status_code == 200, "HTTP " + str(login_response.status_code)
    me = client.get("/api/users/me", headers=auth(login_response.json()["access_token"]))
    assert me.status_code == 200, "HTTP " + str(me.status_code)
    assert me.json().get("email") == email


def test_favorites_require_token(client):
    response = client.get("/api/favorites")
    assert response.status_code == 401, "HTTP " + str(response.status_code)


def test_add_favorite(client, favorite):
    assert favorite.get("team_id") == AUTO_TEAM_ID
    assert favorite.get("team_name") == AUTO_TEAM_NAME


def test_duplicate_favorite_returns_409(client, token1, favorite):
    response = client.post(
        "/api/favorites",
        headers=auth(token1),
        json={
            "team_id": AUTO_TEAM_ID,
            "league_code": PROBE_LEAGUE,
            "team_name": AUTO_TEAM_NAME,
            "team_crest": "",
        },
    )
    assert response.status_code == 409, "HTTP " + str(response.status_code)


def test_favorite_isolation_between_users(client, token1, token2, favorite):
    owner = client.get("/api/favorites", headers=auth(token1)).json()
    other = client.get("/api/favorites", headers=auth(token2)).json()
    owner_ids = {item.get("id") for item in owner if isinstance(item, dict)}
    other_ids = {item.get("id") for item in other if isinstance(item, dict)}
    assert favorite["id"] in owner_ids
    assert favorite["id"] not in other_ids


def test_cross_user_delete_is_refused(client, token2, favorite):
    response = client.delete(
        "/api/favorites/" + str(favorite["id"]),
        headers=auth(token2),
    )
    assert response.status_code == 404, "HTTP " + str(response.status_code)


def test_delete_own_favorite(client, token1, favorite):
    response = client.delete(
        "/api/favorites/" + str(favorite["id"]),
        headers=auth(token1),
    )
    assert response.status_code == 204, "HTTP " + str(response.status_code)
    remaining = client.get("/api/favorites", headers=auth(token1)).json()
    ids = {item.get("id") for item in remaining if isinstance(item, dict)}
    assert favorite["id"] not in ids


@pytest.mark.parametrize("case", POSTMAN_CASES, ids=lambda case: case["name"])
def test_postman_endpoint(client, token1, case):
    if not POSTMAN_CASES:
        pytest.skip("aucune requête Postman exploitable")
    headers = {"Accept": "application/json"}
    if case.get("requires_bearer"):
        headers.update(auth(token1))
    response = client.request(case["method"], case["path"], headers=headers)
    assert response.status_code == case["expected_status"], (
        case["method"] + " " + case["path"] + " attendu "
        + str(case["expected_status"]) + ", obtenu " + str(response.status_code)
    )
'''


def build_api_suite(
    settings: Settings,
    mission_id: str,
) -> ApiSuiteAssets:
    """Génère la suite pytest réelle à partir des preuves de la phase 5."""
    collection, collection_source = _load_collection(settings, mission_id)
    probe, probe_source = _load_probe_results(settings, mission_id)
    postman_cases = postman_safe_cases(collection) if collection else []

    suite_text = SUITE_TEMPLATE.replace(
        "__POSTMAN_CASES__",
        json.dumps(postman_cases, indent=2, ensure_ascii=False),
    ).replace(
        "__TEST_CATALOG__",
        json.dumps(API_TEST_CATALOG, indent=2, ensure_ascii=False),
    )

    directory = mission_workspace(settings, mission_id) / "api-automation"
    directory.mkdir(parents=True, exist_ok=True)
    suite_path = directory / "test_api_suite.py"
    suite_path.write_text(suite_text, encoding="utf-8")

    sources = {
        "postman_collection": collection_source,
        "probe_results": probe_source,
        "postman_requests": len(_postman_requests(collection)) if collection else 0,
        "postman_safe_cases": len(postman_cases),
        "probe_checks": len((probe or {}).get("checks", [])),
        "probe_anomalies": len((probe or {}).get("anomalies", [])),
    }
    sources_path = write_mission_json(
        settings,
        mission_id,
        "api-automation/sources.json",
        sources,
    )
    return ApiSuiteAssets(
        suite_path=suite_path,
        postman_cases=postman_cases,
        sources=sources,
        evidence_paths=[str(suite_path), str(sources_path)],
    )


def _parse_junit(path: Path, settings: Settings) -> list[ApiSuiteCheck]:
    tree = ET.parse(path)
    root = tree.getroot()
    suites = [root] if root.tag == "testsuite" else list(root.iter("testsuite"))
    checks: list[ApiSuiteCheck] = []
    for suite in suites:
        for testcase in suite.findall("testcase"):
            name = testcase.get("name", "test inconnu")
            failure = testcase.find("failure")
            error = testcase.find("error")
            skipped = testcase.find("skipped")
            if failure is not None or error is not None:
                node = failure if failure is not None else error
                outcome = "failed" if failure is not None else "error"
                detail = (node.get("message") or node.text or "").strip()
            elif skipped is not None:
                outcome = "skipped"
                detail = (skipped.get("message") or "").strip()
            else:
                outcome = "passed"
                detail = ""
            secrets = (
                settings.test_user1_password,
                settings.test_user2_password,
                "QaTest123!",
            )
            checks.append(
                ApiSuiteCheck(
                    name=name,
                    outcome=outcome,
                    duration_s=float(testcase.get("time") or 0.0),
                    detail=redact_text(detail, secrets)[:2000],
                )
            )
    return checks


def _catalog_entry(
    name: str,
    catalog: dict,
    postman_cases: list[dict],
    base_url: str,
) -> dict[str, str]:
    for key, value in catalog.items():
        if name == key or name.startswith(key + "["):
            return {
                "method": value.get("method", ""),
                "path": value.get("path", ""),
                "expected": value.get("expected", ""),
                "reproduction": (
                    f"{value.get('method', '')} {base_url}{value.get('path', '')}"
                ).strip(),
            }

    if "[" in name and name.startswith("test_postman_endpoint"):
        case_name = name.split("[", 1)[1].rsplit("]", 1)[0]
        for case in postman_cases:
            if case["name"] == case_name:
                return {
                    "method": case["method"],
                    "path": case["path"],
                    "expected": f"HTTP {case['expected_status']}",
                    "reproduction": f"{case['method']} {base_url}{case['path']}",
                }
    return {
        "method": "",
        "path": "",
        "expected": "test réussi",
        "reproduction": f"pytest api-automation/test_api_suite.py::{name}",
    }


class ApiSuite:
    """Génère et exécute la suite pytest API, avec preuves locales."""

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        executor: Callable[[Path, Path, Path, dict], subprocess.CompletedProcess]
        | None = None,
        preflight: Callable[[str, float], str | None] | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self._executor = executor or self._default_executor
        self._preflight = preflight or self._default_preflight

    def _default_executor(
        self,
        suite_path: Path,
        junit_path: Path,
        directory: Path,
        env: dict,
    ) -> subprocess.CompletedProcess:
        command = [
            sys.executable,
            "-m",
            "pytest",
            str(suite_path),
            "-p",
            "no:cacheprovider",
            f"--junitxml={junit_path}",
            "-q",
        ]
        return subprocess.run(
            command,
            cwd=directory,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=self.settings.automation_timeout_seconds,
        )

    def _default_preflight(self, base_url: str, timeout: float) -> str | None:
        try:
            response = httpx.get(
                f"{base_url.rstrip('/')}/health",
                timeout=timeout,
                follow_redirects=False,
            )
        except httpx.HTTPError as exc:
            return f"API de test injoignable ({type(exc).__name__})."
        if response.status_code != 200:
            return f"API de test en erreur (HTTP {response.status_code})."
        try:
            if response.json().get("status") != "ok":
                return "API de test sans statut de santé valide."
        except ValueError:
            return "API de test avec une réponse de santé non JSON."
        return None

    def run(self, mission_id: str) -> ApiSuiteOutcome:
        ensure_test_api_url(self.settings.test_api_url)
        base_url = self.settings.test_api_url.rstrip("/")

        assets = build_api_suite(self.settings, mission_id)
        directory = assets.suite_path.parent

        blocked_reason = self._preflight(
            base_url,
            self.settings.api_probe_timeout_seconds,
        )
        if blocked_reason:
            return self._write_outcome(
                mission_id,
                base_url,
                assets,
                status="blocked",
                checks=[],
                blocked_reason=blocked_reason,
                log="",
            )

        junit_path = directory / "junit.xml"
        env = os.environ.copy()
        env.update(
            {
                "FOOTBALL_QA_API_URL": base_url,
                "FOOTBALL_QA_USER1_EMAIL": self.settings.test_user1_email,
                "FOOTBALL_QA_USER1_PASSWORD": self.settings.test_user1_password,
                "FOOTBALL_QA_USER2_EMAIL": self.settings.test_user2_email,
                "FOOTBALL_QA_USER2_PASSWORD": self.settings.test_user2_password,
                "PYTHONIOENCODING": "utf-8",
            }
        )

        started = time.perf_counter()
        try:
            completed = self._executor(
                assets.suite_path,
                junit_path,
                directory,
                env,
            )
        except subprocess.TimeoutExpired:
            return self._write_outcome(
                mission_id,
                base_url,
                assets,
                status="blocked",
                checks=[],
                blocked_reason=(
                    "Suite pytest API interrompue après "
                    f"{self.settings.automation_timeout_seconds:.0f} s."
                ),
                log="",
            )
        except OSError as exc:
            return self._write_outcome(
                mission_id,
                base_url,
                assets,
                status="blocked",
                checks=[],
                blocked_reason=f"Exécution pytest impossible ({type(exc).__name__}).",
                log="",
            )

        duration = time.perf_counter() - started
        secrets = (
            self.settings.test_user1_password,
            self.settings.test_user2_password,
            "QaTest123!",
        )
        raw_log = (completed.stdout or "") + "\n" + (completed.stderr or "")
        log = redact_text(raw_log, secrets)[:20000]
        log_path = write_mission_text(
            self.settings,
            mission_id,
            "api-automation/pytest.log",
            log,
        )
        assets.evidence_paths.append(str(log_path))

        if not junit_path.is_file():
            return self._write_outcome(
                mission_id,
                base_url,
                assets,
                status="blocked",
                checks=[],
                blocked_reason=(
                    "pytest n'a produit aucun rapport JUnit "
                    f"(code retour {completed.returncode})."
                ),
                log=log,
            )

        try:
            checks = _parse_junit(junit_path, self.settings)
        except (ET.ParseError, OSError) as exc:
            return self._write_outcome(
                mission_id,
                base_url,
                assets,
                status="blocked",
                checks=[],
                blocked_reason=f"Rapport JUnit illisible ({type(exc).__name__}).",
                log=log,
            )

        anomalies: list[dict] = []
        for check in checks:
            entry = _catalog_entry(
                check.name,
                API_TEST_CATALOG,
                assets.postman_cases,
                base_url,
            )
            check.method = entry["method"]
            check.path = entry["path"]
            check.expected = entry["expected"]
            if check.outcome in {"failed", "error"}:
                anomalies.append(
                    {
                        "check": check.name,
                        "source": "pytest-api",
                        "method": entry["method"],
                        "path": entry["path"],
                        "expected": entry["expected"],
                        "actual": check.detail or check.outcome,
                        "reproduction": entry["reproduction"],
                        "duration_s": check.duration_s,
                        "evidence": str(junit_path),
                    }
                )

        assets.evidence_paths.append(str(junit_path))
        return self._write_outcome(
            mission_id,
            base_url,
            assets,
            status="completed",
            checks=checks,
            blocked_reason=None,
            log=log,
            anomalies=anomalies,
            duration=duration,
        )

    def _write_outcome(
        self,
        mission_id: str,
        base_url: str,
        assets: ApiSuiteAssets,
        *,
        status: str,
        checks: list[ApiSuiteCheck],
        blocked_reason: str | None,
        log: str,
        anomalies: list[dict] | None = None,
        duration: float = 0.0,
    ) -> ApiSuiteOutcome:
        anomalies = anomalies or []
        executed = [check for check in checks if check.outcome != "skipped"]
        passed = [check for check in executed if check.outcome == "passed"]
        failed = [check for check in executed if check.outcome in {"failed", "error"}]
        skipped = [check for check in checks if check.outcome == "skipped"]

        if status == "blocked":
            summary = (
                "Suite pytest API non exécutée : "
                f"{blocked_reason or 'cible indisponible.'} "
                "Aucune anomalie applicative n'est déclarée."
            )
        else:
            summary = (
                f"Suite pytest API exécutée : {len(passed)}/{len(executed)} "
                f"tests réussis, {len(failed)} échec(s), {len(skipped)} ignoré(s), "
                f"{len(anomalies)} anomalie(s) reproductible(s)."
            )

        results = {
            "mission_id": mission_id,
            "base_url": base_url,
            "status": status,
            "blocked_reason": blocked_reason,
            "sources": assets.sources,
            "summary": {
                "tests": len(checks),
                "passed": len(passed),
                "failed": len(failed),
                "skipped": len(skipped),
                "anomalies": len(anomalies),
                "duration_s": round(duration, 2),
            },
            "checks": [asdict(check) for check in checks],
            "anomalies": anomalies,
        }
        results_path = write_mission_json(
            self.settings,
            mission_id,
            "api-automation/api-automation-results.json",
            results,
        )
        report_path = write_mission_text(
            self.settings,
            mission_id,
            "api-automation/api-automation-report.md",
            self._markdown(mission_id, base_url, status, checks, anomalies, blocked_reason),
        )
        evidence = [*assets.evidence_paths, str(results_path), str(report_path)]
        return ApiSuiteOutcome(
            status=status,
            checks=checks,
            anomalies=anomalies,
            evidence_paths=evidence,
            summary=summary,
            blocked_reason=blocked_reason,
            sources=assets.sources,
        )

    @staticmethod
    def _markdown(
        mission_id: str,
        base_url: str,
        status: str,
        checks: list[ApiSuiteCheck],
        anomalies: list[dict],
        blocked_reason: str | None,
    ) -> str:
        executed = [check for check in checks if check.outcome != "skipped"]
        passed = [check for check in executed if check.outcome == "passed"]
        skipped = [check for check in checks if check.outcome == "skipped"]
        lines = [
            f"# Automatisation API pytest — mission {mission_id}",
            "",
            f"- API cible : `{base_url}`",
            f"- Statut : `{status}`",
            f"- Tests exécutés : {len(executed)}",
            f"- Réussis : {len(passed)}",
            f"- Ignorés : {len(skipped)}",
            f"- Anomalies : {len(anomalies)}",
            "",
        ]
        if blocked_reason:
            lines.extend([f"> Suite non exécutée : {blocked_reason}", ""])
        lines.extend(
            [
                "## Tests",
                "",
                "| Test | Attendu | Durée (s) | Résultat |",
                "|---|---|---|---|",
            ]
        )
        for check in checks:
            outcome = {
                "passed": "réussi",
                "failed": "échec",
                "error": "erreur",
                "skipped": "ignoré",
            }.get(check.outcome, check.outcome)
            lines.append(
                f"| {check.name} | {check.expected} | {check.duration_s:.3f} | {outcome} |"
            )
        lines.extend(["", "## Anomalies", ""])
        if not anomalies:
            lines.append(
                "Aucune anomalie déclarée : aucun test exécuté n'a échoué."
                if status == "completed"
                else "Aucune anomalie applicative : la suite n'a pas été exécutée."
            )
        else:
            for index, anomaly in enumerate(anomalies, start=1):
                lines.extend(
                    [
                        f"### {index}. {anomaly['check']}",
                        "",
                        f"- Reproduction : `{anomaly['reproduction']}`",
                        f"- Attendu : {anomaly['expected']}",
                        f"- Obtenu : {anomaly['actual'][:1500]}",
                        f"- Preuve : `{anomaly['evidence']}`",
                        "",
                    ]
                )
        lines.append("")
        return "\n".join(lines)
