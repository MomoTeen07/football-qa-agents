from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from app.config import Settings
from app.tools.api_probe import ApiProbe, UnsafeTargetError

USER1 = "qa.user1@example.com"
USER2 = "qa.user2@example.com"
PASSWORD = "QaTest123!"


def make_settings(tmp_path: Path, base_url: str = "http://localhost:8002") -> Settings:
    return Settings(
        _env_file=None,
        test_api_url=base_url,
        test_user1_email=USER1,
        test_user1_password=PASSWORD,
        test_user2_email=USER2,
        test_user2_password=PASSWORD,
        workspace_dir=tmp_path / "workspace",
        postman_dir=tmp_path / "postman",
        api_probe_timeout_seconds=5,
    )


def make_handler(*, fail_leagues: bool = False):
    next_id = {"value": 100}
    favorites: dict[str, list[dict]] = {"user1": [], "user2": []}
    emails = {"user1": USER1, "user2": USER2}
    tokens = {"token-1": "user1", "token-2": "user2"}

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        method = request.method
        authorization = request.headers.get("Authorization", "")
        token = (
            authorization.removeprefix("Bearer ").strip()
            if authorization.startswith("Bearer ")
            else None
        )
        user = tokens.get(token) if token else None

        def body() -> dict:
            return json.loads(request.content or b"{}")

        if method == "GET" and path == "/health":
            return httpx.Response(200, json={"status": "ok"})
        if method == "GET" and path == "/api/football/leagues":
            if fail_leagues:
                return httpx.Response(500, json={"detail": "boom"})
            return httpx.Response(
                200,
                json=[{"code": code} for code in ["PL", "FL1", "PD", "SA", "BL1", "CL"]],
            )
        if method == "GET" and path == "/api/football/leagues/PL/standings":
            return httpx.Response(
                200,
                json=[{"position": 1, "team": {"id": 57, "name": "Arsenal"}}],
            )
        if method == "GET" and path == "/api/football/leagues/PL/matches":
            return httpx.Response(200, json=[{"id": 1}])
        if method == "GET" and path == "/api/football/leagues/PL/teams/57":
            return httpx.Response(200, json={"id": 57, "name": "Arsenal"})
        if method == "GET" and path == "/api/football/leagues/XX/standings":
            return httpx.Response(404, json={"detail": "not found"})

        if method == "POST" and path == "/api/auth/login":
            data = body()
            email = data.get("email")
            if email in emails.values() and data.get("password") == PASSWORD:
                token_value = "token-1" if email == USER1 else "token-2"
                return httpx.Response(
                    200,
                    json={"access_token": token_value, "token_type": "bearer"},
                )
            return httpx.Response(401, json={"detail": "bad credentials"})
        if method == "GET" and path == "/api/users/me":
            if user is None:
                return httpx.Response(401, json={"detail": "authentication required"})
            return httpx.Response(
                200,
                json={"id": 1, "email": emails[user], "name": user},
            )
        if method == "POST" and path == "/api/auth/register":
            data = body()
            if data.get("email") == USER1:
                return httpx.Response(409, json={"detail": "already exists"})
            if len(data.get("password", "")) < 8:
                return httpx.Response(422, json={"detail": "validation"})
            return httpx.Response(201, json={"access_token": "new-token"})

        if method == "GET" and path == "/api/favorites":
            if user is None:
                return httpx.Response(401, json={"detail": "authentication required"})
            return httpx.Response(200, json=favorites[user])
        if method == "POST" and path == "/api/favorites":
            if user is None:
                return httpx.Response(401, json={"detail": "authentication required"})
            data = body()
            if any(
                favorite["team_id"] == data.get("team_id")
                for favorite in favorites[user]
            ):
                return httpx.Response(409, json={"detail": "duplicate"})
            favorite = {
                "id": next_id["value"],
                **data,
                "created_at": "2026-01-01T00:00:00Z",
            }
            next_id["value"] += 1
            favorites[user].append(favorite)
            return httpx.Response(201, json=favorite)
        if method == "DELETE" and path.startswith("/api/favorites/"):
            if user is None:
                return httpx.Response(401, json={"detail": "authentication required"})
            favorite_id = int(path.rsplit("/", 1)[-1])
            for index, favorite in enumerate(favorites[user]):
                if favorite["id"] == favorite_id:
                    favorites[user].pop(index)
                    return httpx.Response(204)
            return httpx.Response(404, json={"detail": "not found"})

        return httpx.Response(404, json={"detail": "unknown"})

    return handler, favorites


def make_probe(tmp_path: Path, handler, base_url: str = "http://localhost:8002") -> ApiProbe:
    return ApiProbe(
        make_settings(tmp_path, base_url),
        client_factory=lambda url: httpx.Client(
            base_url=url,
            transport=httpx.MockTransport(handler),
        ),
    )


def test_probe_runs_real_checks_and_writes_redacted_evidence(tmp_path: Path) -> None:
    handler, favorites = make_handler()
    outcome = make_probe(tmp_path, handler).run("mission-probe")

    assert outcome.status == "completed"
    assert outcome.anomalies == []
    assert outcome.checks
    assert all(not check.skipped for check in outcome.checks)
    assert all(check.passed for check in outcome.checks)
    names = {check.name for check in outcome.checks}
    assert "Ajout d'un favori" in names
    assert "Suppression croisée refusée" in names
    assert "Le favori n'est pas visible par l'autre utilisateur" in names
    assert favorites == {"user1": [], "user2": []}

    results_path = tmp_path / "workspace" / "missions" / "mission-probe" / "api" / "probe-results.json"
    report_path = tmp_path / "workspace" / "missions" / "mission-probe" / "api" / "probe-report.md"
    assert results_path.is_file()
    assert report_path.is_file()
    text = results_path.read_text(encoding="utf-8")
    assert PASSWORD not in text
    assert "token-1" not in text
    assert "[redacted]" in text
    assert "Aucune anomalie" in report_path.read_text(encoding="utf-8")


def test_probe_declares_anomaly_only_with_reproduction_and_evidence(
    tmp_path: Path,
) -> None:
    handler, _ = make_handler(fail_leagues=True)
    outcome = make_probe(tmp_path, handler).run("mission-failure")

    assert outcome.status == "completed"
    anomaly = next(
        item for item in outcome.anomalies if item["check"] == "Liste des championnats"
    )
    assert anomaly["reproduction"] == (
        "GET http://localhost:8002/api/football/leagues"
    )
    assert "HTTP 500" in anomaly["actual"]
    assert anomaly["response_excerpt"]

    results = json.loads(
        (
            tmp_path
            / "workspace"
            / "missions"
            / "mission-failure"
            / "api"
            / "probe-results.json"
        ).read_text(encoding="utf-8")
    )
    assert results["anomalies"]


def test_probe_refuses_the_real_application_port(tmp_path: Path) -> None:
    handler, _ = make_handler()
    probe = make_probe(tmp_path, handler, base_url="http://localhost:8001")

    with pytest.raises(UnsafeTargetError):
        probe.run("mission-unsafe")

    assert not (tmp_path / "workspace" / "missions" / "mission-unsafe").exists()


def test_probe_reports_blocked_without_inventing_anomaly(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    outcome = make_probe(tmp_path, handler).run("mission-blocked")

    assert outcome.status == "blocked"
    assert outcome.anomalies == []
    assert any(
        check.actual.startswith("connexion impossible")
        for check in outcome.checks
    )
    assert "Aucune anomalie applicative" in outcome.summary
