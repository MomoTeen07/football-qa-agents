from __future__ import annotations

import json
from pathlib import Path

from app.config import Settings
from app.tools.allure_report import AllureReport, AllureSuite


def make_settings(tmp_path: Path) -> Settings:
    return Settings(
        _env_file=None,
        workspace_dir=tmp_path / "workspace",
        reports_dir=tmp_path / "reports" / "missions",
        allure_results_dir=tmp_path / "reports" / "allure-results",
        test_api_url="http://localhost:8002",
        test_ui_url="http://localhost:5175",
        test_user1_password="QaTest123!",
        test_user2_password="QaTest123!",
    )


def probe_payload() -> dict:
    return {
        "status": "completed",
        "base_url": "http://localhost:8002",
        "checks": [
            {
                "name": "Santé de l'API",
                "method": "GET",
                "path": "/health",
                "expected": "200",
                "actual": "HTTP 200",
                "passed": True,
                "skipped": False,
                "duration_ms": 10,
                "detail": "status=ok",
                "response_excerpt": '{"status": "ok"}',
            },
            {
                "name": "Classement",
                "method": "GET",
                "path": "/api/football/leagues/PL/standings",
                "expected": "200",
                "actual": "HTTP 500",
                "passed": False,
                "skipped": False,
                "duration_ms": 20,
                "detail": "HTTP 500",
                "response_excerpt": "boom",
            },
            {
                "name": "Favori non authentifié",
                "method": "GET",
                "path": "/api/favorites",
                "expected": "401",
                "actual": "",
                "passed": False,
                "skipped": True,
                "duration_ms": 0,
                "detail": "vérification ignorée",
                "response_excerpt": "",
            },
        ],
        "anomalies": [
            {
                "check": "Classement",
                "method": "GET",
                "path": "/api/football/leagues/PL/standings",
                "expected": "200",
                "actual": "HTTP 500",
                "reproduction": (
                    "GET http://localhost:8002/api/football/leagues/PL/standings"
                ),
            }
        ],
    }


def api_payload() -> dict:
    return {
        "status": "completed",
        "base_url": "http://localhost:8002",
        "summary": {
            "tests": 2,
            "passed": 1,
            "failed": 1,
            "skipped": 0,
            "anomalies": 1,
        },
        "checks": [
            {
                "name": "test_health",
                "outcome": "passed",
                "duration_s": 0.1,
                "detail": "",
            },
            {
                "name": "test_leagues",
                "outcome": "failed",
                "duration_s": 0.2,
                "detail": "assert 500 == 200",
            },
        ],
        "anomalies": [
            {
                "check": "test_leagues",
                "expected": "HTTP 200",
                "actual": "HTTP 500",
                "reproduction": "GET http://localhost:8002/api/football/leagues",
            }
        ],
    }


def ui_payload() -> dict:
    return {
        "status": "completed",
        "ui_url": "http://localhost:5175",
        "summary": {
            "checks": 2,
            "passed": 1,
            "failed": 1,
            "skipped": 0,
            "anomalies": 1,
        },
        "checks": [
            {
                "name": "Accueil",
                "status": "passed",
                "expected": "h1 visible",
                "detail": "",
                "path": "/",
                "duration_s": 0.5,
                "screenshot": "",
            },
            {
                "name": "Championnats",
                "status": "failed",
                "expected": "6 cartes",
                "detail": "3 cartes",
                "path": "/championships",
                "duration_s": 0.6,
                "screenshot": "screenshots/01-championnats.png",
            },
        ],
        "anomalies": [
            {
                "check": "Championnats",
                "expected": "6 cartes",
                "actual": "3 cartes",
                "reproduction": "Ouvrir http://localhost:5175/championships",
                "screenshot": "screenshots/01-championnats.png",
            }
        ],
    }


def suites() -> list[AllureSuite]:
    return [
        AllureSuite("Sondes API (phase 5)", "probe", probe_payload()),
        AllureSuite("Automatisation API pytest (phase 6)", "api", api_payload()),
        AllureSuite(
            "Automatisation UI Playwright (phase 6)", "ui", ui_payload()
        ),
    ]


def read_results(directory: Path) -> list[dict]:
    return [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(directory.glob("*-result.json"))
    ]


def test_allure_generates_standard_results_and_totals(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    mission_id = "mission123"
    screenshot = (
        settings.workspace_dir
        / "missions"
        / mission_id
        / "ui-automation"
        / "screenshots"
        / "01-championnats.png"
    )
    screenshot.parent.mkdir(parents=True)
    screenshot.write_bytes(b"\x89PNG\r\n\x1a\n")

    outcome = AllureReport(settings).generate(mission_id, suites())

    assert outcome.status == "completed"
    assert outcome.total == 7
    assert outcome.passed == 3
    assert outcome.failed == 3
    assert outcome.skipped == 1
    assert outcome.anomalies == 3

    results = read_results(Path(outcome.results_dir))
    assert len(results) == 7
    by_name = {result["name"]: result for result in results}
    assert by_name["Santé de l'API"]["status"] == "passed"
    assert by_name["Favori non authentifié"]["status"] == "skipped"
    failed_api = by_name["test_leagues"]
    assert failed_api["status"] == "failed"
    assert "HTTP 500" in failed_api["statusDetails"]["message"]
    assert failed_api["links"][0]["url"].endswith("/api/football/leagues")
    failed_ui = by_name["Championnats"]
    assert failed_ui["status"] == "failed"
    assert any(
        attachment["type"] == "image/png"
        for attachment in failed_ui["attachments"]
    )
    screenshot_attachment = next(
        attachment
        for attachment in failed_ui["attachments"]
        if attachment["type"] == "image/png"
    )
    assert (
        Path(outcome.results_dir) / screenshot_attachment["source"]
    ).is_file()
    for result in results:
        assert result["stage"] == "finished"
        assert isinstance(result["start"], int)
        assert isinstance(result["stop"], int)
        assert result["start"] <= result["stop"]
        labels = {label["name"]: label["value"] for label in result["labels"]}
        assert labels["parentSuite"] == f"Mission {mission_id}"
        assert labels["language"] == "python"


def test_allure_summary_and_markdown_are_written(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    outcome = AllureReport(settings).generate("mission123", suites())

    summary = json.loads(
        Path(outcome.summary_path).read_text(encoding="utf-8")
    )
    assert summary["totals"] == {
        "total": 7,
        "passed": 3,
        "failed": 3,
        "broken": 0,
        "skipped": 1,
        "anomalies": 3,
    }
    assert len(summary["suites"]) == 3
    assert len(summary["anomalies"]) == 3

    markdown = Path(outcome.report_path).read_text(encoding="utf-8")
    assert "# Rapport Allure — mission mission123" in markdown
    assert "## Suites" in markdown
    assert "GET http://localhost:8002/api/football/leagues" in markdown
    assert "allure serve" in markdown

    environment = (
        Path(outcome.results_dir) / "environment.properties"
    ).read_text(encoding="utf-8")
    assert "Mission=mission123" in environment
    assert "API de test=http://localhost:8002" in environment


def test_allure_blocked_suite_is_skipped_without_anomaly(
    tmp_path: Path,
) -> None:
    settings = make_settings(tmp_path)
    outcome = AllureReport(settings).generate(
        "blockedmission",
        [
            AllureSuite(
                "Automatisation API pytest (phase 6)",
                "api",
                {
                    "status": "blocked",
                    "blocked_reason": "API de test injoignable.",
                    "checks": [],
                    "anomalies": [],
                },
            )
        ],
    )

    assert outcome.status == "completed"
    assert outcome.total == 1
    assert outcome.skipped == 1
    assert outcome.anomalies == 0
    result = read_results(Path(outcome.results_dir))[0]
    assert result["status"] == "skipped"
    assert "API de test injoignable." in result["statusDetails"]["message"]


def test_allure_without_real_execution_generates_nothing(
    tmp_path: Path,
) -> None:
    settings = make_settings(tmp_path)
    outcome = AllureReport(settings).generate(
        "emptymission",
        [AllureSuite("Sondes API (phase 5)", "probe", None)],
    )

    assert outcome.status == "skipped"
    assert outcome.evidence_paths == []
    assert not (
        Path(settings.allure_results_dir) / "emptymission"
    ).exists()


def test_allure_regeneration_removes_stale_results(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    report = AllureReport(settings)
    first = report.generate("mission123", suites())
    stale = Path(first.results_dir) / "stale-result.json"
    stale.write_text("{}", encoding="utf-8")

    second = report.generate("mission123", suites())

    assert not stale.exists()
    assert len(read_results(Path(second.results_dir))) == 7


def test_allure_result_identifiers_are_deterministic(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    report = AllureReport(settings)
    first = report.generate("mission123", suites())
    second = report.generate("mission123", suites())

    first_names = sorted(
        path.name for path in Path(first.results_dir).glob("*-result.json")
    )
    second_names = sorted(
        path.name for path in Path(second.results_dir).glob("*-result.json")
    )
    assert first_names == second_names
