from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from app.config import Settings
from app.tools.api_probe import UnsafeTargetError
from app.tools.ui_suite import (
    UI_RUNNER_SCRIPT,
    UiSuite,
    UnsafeUiTargetError,
    ensure_test_ui_url,
)


def make_settings(
    tmp_path: Path,
    *,
    ui_url: str = "http://localhost:5175",
    api_url: str = "http://localhost:8002",
) -> Settings:
    return Settings(
        _env_file=None,
        test_ui_url=ui_url,
        test_api_url=api_url,
        workspace_dir=tmp_path / "workspace",
        postman_dir=tmp_path / "postman",
        test_user1_email="qa.user1@example.com",
        test_user1_password="QaTest123!",
        test_user2_email="qa.user2@example.com",
        test_user2_password="QaTest123!",
        ui_automation_timeout_seconds=30,
        api_probe_timeout_seconds=5,
    )


def test_ui_target_guard_accepts_only_the_test_frontend() -> None:
    ensure_test_ui_url("http://localhost:5175")
    ensure_test_ui_url("http://127.0.0.1:5175")

    for url in (
        "http://localhost:5174",
        "http://localhost:8002",
        "https://example.com:5175",
    ):
        with pytest.raises(UnsafeUiTargetError):
            ensure_test_ui_url(url)


def test_ui_suite_blocks_when_frontend_is_unreachable(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)

    def forbidden_executor(*args, **kwargs):
        raise AssertionError(
            "Playwright ne doit pas être exécuté si le frontend est injoignable"
        )

    suite = UiSuite(
        settings,
        preflight=lambda url, timeout: "Frontend de test injoignable.",
        api_preflight=lambda url, timeout: None,
        executor=forbidden_executor,
    )

    outcome = suite.run("mission-ui-blocked")

    assert outcome.status == "blocked"
    assert outcome.anomalies == []
    assert outcome.checks == []
    assert "Aucune anomalie applicative" in outcome.summary
    results = json.loads(
        (
            tmp_path
            / "workspace"
            / "missions"
            / "mission-ui-blocked"
            / "ui-automation"
            / "ui-automation-results.json"
        ).read_text(encoding="utf-8")
    )
    assert results["status"] == "blocked"
    assert results["anomalies"] == []


def test_ui_suite_blocks_when_api_is_unreachable(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)

    def forbidden_executor(*args, **kwargs):
        raise AssertionError(
            "Playwright ne doit pas être exécuté si l'API est injoignable"
        )

    suite = UiSuite(
        settings,
        preflight=lambda url, timeout: None,
        api_preflight=lambda url, timeout: "API de test injoignable.",
        executor=forbidden_executor,
    )

    outcome = suite.run("mission-api-blocked")

    assert outcome.status == "blocked"
    assert outcome.anomalies == []
    assert "API de test injoignable" in outcome.summary


def test_ui_suite_parses_playwright_results_and_screenshots(
    tmp_path: Path,
) -> None:
    settings = make_settings(tmp_path)

    def executor(script_path, directory, env):
        payload = {
            "status": "completed",
            "checks": [
                {
                    "name": "Accueil accessible",
                    "status": "passed",
                    "expected": "h1 visible",
                    "detail": "",
                    "path": "/",
                    "duration_s": 0.1,
                    "screenshot": "",
                },
                {
                    "name": "Championnats visibles",
                    "status": "failed",
                    "expected": "6 cartes",
                    "detail": "3 cartes seulement",
                    "path": "/championships",
                    "duration_s": 0.2,
                    "screenshot": "01-championnats.png",
                },
            ],
            "anomalies": [
                {
                    "check": "Championnats visibles",
                    "source": "playwright-ui",
                    "expected": "6 cartes",
                    "actual": "3 cartes seulement",
                    "reproduction": "Ouvrir http://localhost:5175/championships",
                    "screenshot": "01-championnats.png",
                }
            ],
        }
        (directory / "ui-playwright-results.json").write_text(
            json.dumps(payload, ensure_ascii=False),
            encoding="utf-8",
        )
        (directory / "screenshots" / "01-championnats.png").write_bytes(b"png")
        return subprocess.CompletedProcess(
            args=["playwright"],
            returncode=0,
            stdout="scénarios exécutés",
            stderr="",
        )

    suite = UiSuite(
        settings,
        preflight=lambda url, timeout: None,
        api_preflight=lambda url, timeout: None,
        executor=executor,
    )

    outcome = suite.run("mission-ui-completed")

    assert outcome.status == "completed"
    assert len(outcome.checks) == 2
    assert [item["check"] for item in outcome.anomalies] == [
        "Championnats visibles"
    ]
    assert any(path.endswith(".png") for path in outcome.evidence_paths)
    assert (
        tmp_path
        / "workspace"
        / "missions"
        / "mission-ui-completed"
        / "ui-automation"
        / "ui-automation-results.json"
    ).is_file()


def test_ui_suite_technical_error_blocks_without_anomaly(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)

    def executor(script_path, directory, env):
        payload = {
            "status": "error",
            "checks": [],
            "anomalies": [
                {
                    "check": "Exécution Playwright",
                    "expected": "navigateur disponible",
                    "actual": "navigateur absent",
                }
            ],
        }
        (directory / "ui-playwright-results.json").write_text(
            json.dumps(payload, ensure_ascii=False),
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(
            args=["playwright"],
            returncode=1,
            stdout="",
            stderr="browser missing",
        )

    suite = UiSuite(
        settings,
        preflight=lambda url, timeout: None,
        api_preflight=lambda url, timeout: None,
        executor=executor,
    )

    outcome = suite.run("mission-ui-error")

    assert outcome.status == "blocked"
    assert outcome.anomalies == []
    assert "incomplète" in (outcome.blocked_reason or "")


def test_ui_suite_does_not_reuse_stale_results(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    stale_results = (
        tmp_path
        / "workspace"
        / "missions"
        / "mission-ui-stale"
        / "ui-automation"
        / "ui-playwright-results.json"
    )
    stale_results.parent.mkdir(parents=True)
    stale_results.write_text('{"status": "completed"}', encoding="utf-8")
    stale_screenshot = stale_results.parent / "screenshots" / "01-old.png"
    stale_screenshot.parent.mkdir(parents=True)
    stale_screenshot.write_bytes(b"old")

    suite = UiSuite(
        settings,
        preflight=lambda url, timeout: "Frontend injoignable.",
        api_preflight=lambda url, timeout: None,
        executor=lambda *args: None,
    )

    outcome = suite.run("mission-ui-stale")

    assert outcome.status == "blocked"
    assert outcome.checks == []
    assert not stale_results.exists()
    assert not stale_screenshot.exists()


def test_ui_suite_refuses_a_non_test_frontend(tmp_path: Path) -> None:
    settings = make_settings(tmp_path, ui_url="http://localhost:5174")

    with pytest.raises(UnsafeUiTargetError):
        UiSuite(settings).run("mission-unsafe-ui")


def test_ui_suite_refuses_the_real_application_api(tmp_path: Path) -> None:
    settings = make_settings(tmp_path, api_url="http://localhost:8001")

    with pytest.raises(UnsafeTargetError):
        UiSuite(settings).run("mission-unsafe-api")


def test_ui_runner_is_valid_python_and_logs_in_from_a_clean_page() -> None:
    # Un reload de /login conserve `history.state` : l'application renverrait
    # vers /favorites au lieu de /championships. Le scénario doit donc repasser
    # par une page publique avant d'ouvrir /login.
    compile(UI_RUNNER_SCRIPT, "run_ui_checks.py", "exec")
    public_goto = UI_RUNNER_SCRIPT.index('page.goto("/championships"')
    login_goto = UI_RUNNER_SCRIPT.index('page.goto("/login"')
    assert public_goto < login_goto
