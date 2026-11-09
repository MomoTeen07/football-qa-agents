from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from app.config import Settings
from app.tools.api_probe import UnsafeTargetError
from app.tools.api_suite import ApiSuite, build_api_suite, postman_safe_cases


def make_settings(
    tmp_path: Path,
    *,
    api_url: str = "http://localhost:8002",
) -> Settings:
    return Settings(
        _env_file=None,
        test_api_url=api_url,
        workspace_dir=tmp_path / "workspace",
        postman_dir=tmp_path / "postman",
        test_user1_email="qa.user1@example.com",
        test_user1_password="QaTest123!",
        test_user2_email="qa.user2@example.com",
        test_user2_password="QaTest123!",
        automation_timeout_seconds=30,
    )


def write_collection(tmp_path: Path) -> Path:
    collection = {
        "info": {"name": "Football QA"},
        "item": [
            {
                "name": "Health",
                "request": {
                    "method": "GET",
                    "url": {"raw": "{{baseUrl}}/health"},
                    "header": [],
                },
                "event": [
                    {
                        "listen": "test",
                        "script": {"exec": ["pm.response.to.have.status(200)"]},
                    }
                ],
            },
            {
                "name": "Me",
                "request": {
                    "method": "GET",
                    "url": {"raw": "{{baseUrl}}/api/users/me"},
                    "header": [
                        {"key": "Authorization", "value": "Bearer {{token}}"}
                    ],
                },
                "event": [
                    {
                        "listen": "test",
                        "script": {"exec": ["pm.response.to.have.status(200)"]},
                    }
                ],
            },
            {
                "name": "Add favorite",
                "request": {
                    "method": "POST",
                    "url": {"raw": "{{baseUrl}}/api/favorites"},
                    "header": [
                        {"key": "Authorization", "value": "Bearer {{token}}"}
                    ],
                },
                "event": [
                    {
                        "listen": "test",
                        "script": {"exec": ["pm.response.to.have.status(201)"]},
                    }
                ],
            },
        ],
    }
    path = tmp_path / "postman" / "collections" / "football-qa.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(collection), encoding="utf-8")
    return path


def test_postman_safe_cases_keep_only_get_requests(tmp_path: Path) -> None:
    collection_path = write_collection(tmp_path)
    collection = json.loads(collection_path.read_text(encoding="utf-8"))

    cases = postman_safe_cases(collection)

    assert [case["path"] for case in cases] == ["/health", "/api/users/me"]
    assert all(case["method"] == "GET" for case in cases)
    assert cases[1]["requires_bearer"] is True


def test_build_api_suite_writes_suite_and_sources(tmp_path: Path) -> None:
    write_collection(tmp_path)
    settings = make_settings(tmp_path)

    assets = build_api_suite(settings, "mission-suite")

    assert assets.suite_path.is_file()
    text = assets.suite_path.read_text(encoding="utf-8")
    assert "def test_health_returns_ok" in text
    assert "POSTMAN_CASES" in text
    assert "Add favorite" not in text
    assert assets.sources["postman_requests"] == 3
    assert assets.sources["postman_safe_cases"] == 2
    assert (
        tmp_path
        / "workspace"
        / "missions"
        / "mission-suite"
        / "api-automation"
        / "sources.json"
    ).is_file()


def test_api_suite_blocks_without_inventing_anomaly(tmp_path: Path) -> None:
    write_collection(tmp_path)
    settings = make_settings(tmp_path)

    def forbidden_executor(*args, **kwargs):
        raise AssertionError(
            "pytest ne doit pas être exécuté si la cible est injoignable"
        )

    suite = ApiSuite(
        settings,
        preflight=lambda url, timeout: "API de test injoignable.",
        executor=forbidden_executor,
    )

    outcome = suite.run("mission-blocked")

    assert outcome.status == "blocked"
    assert outcome.anomalies == []
    assert outcome.checks == []
    assert "Aucune anomalie applicative" in outcome.summary
    results = json.loads(
        (
            tmp_path
            / "workspace"
            / "missions"
            / "mission-blocked"
            / "api-automation"
            / "api-automation-results.json"
        ).read_text(encoding="utf-8")
    )
    assert results["status"] == "blocked"
    assert results["anomalies"] == []


def test_api_suite_parses_junit_and_declares_only_real_failures(
    tmp_path: Path,
) -> None:
    write_collection(tmp_path)
    settings = make_settings(tmp_path)

    def executor(suite_path, junit_path, directory, env):
        junit_path.write_text(
            '<?xml version="1.0" encoding="utf-8"?>'
            '<testsuite tests="2">'
            '<testcase name="test_health_returns_ok" time="0.01"/>'
            '<testcase name="test_leagues_return_six_entries" time="0.02">'
            '<failure message="HTTP 500"/>'
            "</testcase>"
            "</testsuite>",
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(
            args=["pytest"],
            returncode=1,
            stdout="2 tests",
            stderr="",
        )

    suite = ApiSuite(
        settings,
        preflight=lambda url, timeout: None,
        executor=executor,
    )

    outcome = suite.run("mission-completed")

    assert outcome.status == "completed"
    assert len(outcome.checks) == 2
    assert [item["check"] for item in outcome.anomalies] == [
        "test_leagues_return_six_entries"
    ]
    anomaly = outcome.anomalies[0]
    assert anomaly["reproduction"] == (
        "GET http://localhost:8002/api/football/leagues"
    )
    assert "HTTP 500" in anomaly["actual"]
    assert (
        tmp_path
        / "workspace"
        / "missions"
        / "mission-completed"
        / "api-automation"
        / "junit.xml"
    ).is_file()


def test_api_suite_does_not_reuse_stale_junit(tmp_path: Path) -> None:
    write_collection(tmp_path)
    settings = make_settings(tmp_path)
    stale = (
        tmp_path
        / "workspace"
        / "missions"
        / "mission-stale"
        / "api-automation"
        / "junit.xml"
    )
    stale.parent.mkdir(parents=True)
    stale.write_text(
        '<testsuite><testcase name="test_health_returns_ok"/></testsuite>',
        encoding="utf-8",
    )

    suite = ApiSuite(
        settings,
        preflight=lambda url, timeout: "API injoignable.",
        executor=lambda *args: None,
    )

    outcome = suite.run("mission-stale")

    assert outcome.status == "blocked"
    assert outcome.checks == []
    assert not stale.exists()


def test_api_suite_refuses_the_real_application_port(tmp_path: Path) -> None:
    settings = make_settings(tmp_path, api_url="http://localhost:8001")

    with pytest.raises(UnsafeTargetError):
        ApiSuite(settings, preflight=lambda *_: None).run("mission-unsafe")
