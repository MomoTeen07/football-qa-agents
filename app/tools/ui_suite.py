"""Automatisation UI Playwright réelle (phase 6).

Le script Playwright est généré dans le workspace de la mission puis exécuté
par le Python du venv. La cible est strictement limitée au frontend de test
(`localhost:5175`) ; toute autre cible est refusée avant exécution.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from urllib.parse import urlparse

import httpx

from app.config import Settings, get_settings
from app.tools.api_probe import UnsafeTargetError, ensure_test_api_url
from app.tools.redaction import redact_text
from app.tools.workspace import mission_workspace, write_mission_json, write_mission_text

TEST_UI_PORT = 5175


class UnsafeUiTargetError(RuntimeError):
    """La cible UI n'est pas le frontend de test autorisé."""


def ensure_test_ui_url(url: str) -> None:
    """Refuse toute cible autre que le frontend de test local sur le port 5175."""
    parsed = urlparse(url)
    if (
        parsed.scheme not in {"http", "https"}
        or parsed.hostname not in {"localhost", "127.0.0.1"}
        or parsed.port != TEST_UI_PORT
    ):
        raise UnsafeUiTargetError(
            "L'automatisation UI est limitée au frontend de test local "
            f"sur le port {TEST_UI_PORT}."
        )


@dataclass
class UiSuiteCheck:
    name: str
    status: str
    expected: str = ""
    detail: str = ""
    path: str = ""
    duration_s: float = 0.0
    screenshot: str = ""


@dataclass
class UiSuiteOutcome:
    status: str
    checks: list[UiSuiteCheck] = field(default_factory=list)
    anomalies: list[dict] = field(default_factory=list)
    evidence_paths: list[str] = field(default_factory=list)
    summary: str = ""
    blocked_reason: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


UI_RUNNER_SCRIPT = '''# Script Playwright généré par l'agent UI Automation (football-qa-agents).
# Exécution réelle contre le frontend de test isolé uniquement.
from __future__ import annotations

import json
import os
import re
import time
import traceback
from pathlib import Path

import httpx
from playwright.sync_api import expect, sync_playwright

UI_URL = os.environ["FOOTBALL_QA_UI_URL"].rstrip("/")
API_URL = os.environ["FOOTBALL_QA_API_URL"].rstrip("/")
USER1_EMAIL = os.environ["FOOTBALL_QA_USER1_EMAIL"]
USER1_PASSWORD = os.environ["FOOTBALL_QA_USER1_PASSWORD"]
RESULTS_PATH = Path(os.environ["FOOTBALL_QA_UI_RESULTS"])
SCREENSHOT_DIR = Path(os.environ["FOOTBALL_QA_UI_SCREENSHOTS"])
HEADLESS = os.environ.get("FOOTBALL_QA_UI_HEADLESS", "true").lower() != "false"
PROBE_TEAM_ID = 999001


def api_client():
    return httpx.Client(base_url=API_URL, timeout=20.0, follow_redirects=False)


def api_login(client):
    response = client.post(
        "/api/auth/login",
        json={"email": USER1_EMAIL, "password": USER1_PASSWORD},
    )
    response.raise_for_status()
    return response.json()["access_token"]


def auth(token):
    return {"Authorization": "Bearer " + token}


def prepare_target():
    """Choisit une équipe réelle non déjà favorite pour le scénario UI."""
    with api_client() as client:
        token = api_login(client)
        favorites = client.get("/api/favorites", headers=auth(token)).json()
        used = {
            favorite.get("team_id")
            for favorite in favorites
            if isinstance(favorite, dict)
        }
        standings = client.get("/api/football/leagues/PL/standings").json()
        candidates = [
            row["team"]
            for row in standings
            if isinstance(row, dict) and row["team"].get("id") not in used
        ]
        team = candidates[0] if candidates else standings[0]["team"]
        return int(team["id"]), str(team["name"]), token


def cleanup(token, team_id):
    if token is None:
        return
    with api_client() as client:
        favorites = client.get("/api/favorites", headers=auth(token)).json()
        for favorite in favorites:
            if not isinstance(favorite, dict):
                continue
            if favorite.get("team_id") in {team_id, PROBE_TEAM_ID}:
                client.delete(
                    "/api/favorites/" + str(favorite.get("id")),
                    headers=auth(token),
                )


class Recorder:
    def __init__(self, page):
        self.page = page
        self.checks = []

    def _screenshot(self, name):
        SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
        safe = re.sub(r"[^a-zA-Z0-9_-]+", "-", name).strip("-")[:60] or "check"
        path = SCREENSHOT_DIR / (f"{len(self.checks) + 1:02d}-{safe}.png")
        try:
            self.page.screenshot(path=str(path), full_page=True)
            return str(path)
        except Exception:
            return ""

    def check(self, name, expected, path, action):
        started = time.perf_counter()
        try:
            action()
            status = "passed"
            detail = ""
            screenshot = ""
        except Exception as exc:
            status = "failed"
            detail = f"{type(exc).__name__}: {exc}"[:1500]
            screenshot = self._screenshot(name)
        self.checks.append(
            {
                "name": name,
                "status": status,
                "expected": expected,
                "detail": detail,
                "path": path,
                "duration_s": round(time.perf_counter() - started, 3),
                "screenshot": screenshot,
            }
        )
        return status == "passed"

    def skip(self, name, expected, path, reason):
        self.checks.append(
            {
                "name": name,
                "status": "skipped",
                "expected": expected,
                "detail": reason,
                "path": path,
                "duration_s": 0.0,
                "screenshot": "",
            }
        )


def build_anomalies(checks):
    anomalies = []
    for check in checks:
        if check["status"] != "failed":
            continue
        anomalies.append(
            {
                "check": check["name"],
                "source": "playwright-ui",
                "expected": check["expected"],
                "actual": check["detail"],
                "reproduction": "Ouvrir " + UI_URL + (check["path"] or "/"),
                "screenshot": check["screenshot"],
            }
        )
    return anomalies


def main():
    target_id = None
    team_name = ""
    api_token = None
    recorder = None
    checks = []
    status = "completed"
    try:
        target_id, team_name, api_token = prepare_target()
    except Exception as exc:
        prepare_error = f"{type(exc).__name__}: {exc}"[:500]
    else:
        prepare_error = ""

    try:
        with sync_playwright() as play:
            browser = play.chromium.launch(headless=HEADLESS)
            context = browser.new_context(base_url=UI_URL)
            page = context.new_page()
            page.set_default_timeout(15000)
            recorder = Recorder(page)

            recorder.check(
                "Accueil accessible",
                "h1 et marque Football QA visibles",
                "/",
                lambda: (
                    page.goto("/", wait_until="networkidle"),
                    expect(page.locator("h1")).to_contain_text("Le football"),
                    expect(page.locator(".brand")).to_contain_text("Football QA"),
                ),
            )
            recorder.check(
                "Championnats visibles",
                "6 cartes et Premier League / Ligue des champions",
                "/championships",
                lambda: (
                    page.goto("/championships", wait_until="networkidle"),
                    expect(page.get_by_test_id("championship-list")).to_be_visible(),
                    expect(page.get_by_test_id("championship-card")).to_have_count(6),
                    expect(page.get_by_text("Premier League", exact=True)).to_be_visible(),
                    expect(
                        page.get_by_text("Ligue des champions", exact=True)
                    ).to_be_visible(),
                ),
            )
            recorder.check(
                "Classement Premier League",
                "titre, onglet classement et lignes de tableau",
                "/championships/PL",
                lambda: (
                    page.goto("/championships/PL", wait_until="networkidle"),
                    expect(page.locator("h1")).to_have_text("Premier League"),
                    expect(page.get_by_role("tab", name="Classement")).to_have_attribute(
                        "aria-selected", "true"
                    ),
                    expect(page.locator("table tbody tr")).not_to_have_count(0),
                ),
            )
            recorder.check(
                "Onglet matchs",
                "cartes de match affichées",
                "/championships/PL",
                lambda: (
                    page.get_by_role("tab", name="Matchs").click(),
                    expect(page.locator(".card.match")).not_to_have_count(0),
                ),
            )
            recorder.check(
                "Détail équipe sans session",
                "Arsenal visible et bouton favori masqué",
                "/teams/PL/57",
                lambda: (
                    page.goto("/teams/PL/57", wait_until="networkidle"),
                    expect(page.locator("h1")).to_have_text("Arsenal"),
                    expect(page.get_by_test_id("favorite-button")).to_have_count(0),
                    expect(
                        page.get_by_text("Connecte-toi pour gérer tes favoris.")
                    ).to_be_visible(),
                ),
            )
            recorder.check(
                "Favoris protégés sans session",
                "redirection vers /login",
                "/favorites",
                lambda: (
                    page.goto("/favorites", wait_until="networkidle"),
                    expect(page).to_have_url(re.compile(r"/login$")),
                    expect(page.get_by_test_id("email-input")).to_be_visible(),
                ),
            )

            logged_in = recorder.check(
                "Connexion utilisateur 1",
                "redirection vers /championships et lien favoris visible",
                "/login",
                lambda: (
                    page.get_by_test_id("email-input").fill(USER1_EMAIL),
                    page.get_by_test_id("password-input").fill(USER1_PASSWORD),
                    page.get_by_test_id("submit-login").click(),
                    expect(page).to_have_url(re.compile(r"/championships$")),
                    expect(page.get_by_test_id("favorites-link")).to_be_visible(),
                ),
            )

            if not logged_in:
                recorder.skip(
                    "Ajout d'un favori",
                    "bouton passe à Dans mes favoris",
                    "/teams/PL/" + str(target_id or 57),
                    "connexion UI impossible",
                )
                recorder.skip(
                    "Favori visible dans la liste",
                    "carte du favori visible",
                    "/favorites",
                    "connexion UI impossible",
                )
                recorder.skip(
                    "Suppression d'un favori",
                    "carte supprimée de la liste",
                    "/favorites",
                    "connexion UI impossible",
                )
                recorder.skip(
                    "Déconnexion",
                    "lien de connexion visible",
                    "/championships",
                    "connexion UI impossible",
                )
            elif target_id is None:
                for name, expected, path in (
                    ("Ajout d'un favori", "bouton passe à Dans mes favoris", "/teams/PL/57"),
                    ("Favori visible dans la liste", "carte du favori visible", "/favorites"),
                    ("Suppression d'un favori", "carte supprimée de la liste", "/favorites"),
                    ("Déconnexion", "lien de connexion visible", "/championships"),
                ):
                    recorder.skip(name, expected, path, prepare_error or "cible indisponible")
            else:
                team_path = "/teams/PL/" + str(target_id)
                added = recorder.check(
                    "Ajout d'un favori",
                    "bouton passe à Dans mes favoris",
                    team_path,
                    lambda: (
                        page.goto(team_path, wait_until="networkidle"),
                        expect(page.locator("h1")).to_have_text(team_name),
                        expect(page.get_by_test_id("favorite-button")).to_contain_text(
                            "Ajouter aux favoris"
                        ),
                        page.get_by_test_id("favorite-button").click(),
                        expect(page.get_by_test_id("favorite-button")).to_contain_text(
                            "Dans mes favoris"
                        ),
                    ),
                )
                if added:
                    card = page.locator(".card.fav", has_text=team_name)
                    recorder.check(
                        "Favori visible dans la liste",
                        "carte du favori visible",
                        "/favorites",
                        lambda: (
                            page.goto("/favorites", wait_until="networkidle"),
                            expect(card).to_be_visible(),
                            expect(card.locator("h2")).to_have_text(team_name),
                        ),
                    )
                    recorder.check(
                        "Suppression d'un favori",
                        "carte supprimée de la liste",
                        "/favorites",
                        lambda: (
                            card.get_by_role("button", name="Supprimer").click(),
                            expect(card).to_have_count(0),
                        ),
                    )
                else:
                    recorder.skip(
                        "Favori visible dans la liste",
                        "carte du favori visible",
                        "/favorites",
                        "ajout du favori impossible",
                    )
                    recorder.skip(
                        "Suppression d'un favori",
                        "carte supprimée de la liste",
                        "/favorites",
                        "ajout du favori impossible",
                    )
                recorder.check(
                    "Déconnexion",
                    "lien de connexion visible",
                    "/championships",
                    lambda: (
                        page.get_by_role("button", name="Déconnexion").click(),
                        expect(page.get_by_test_id("login-button")).to_be_visible(),
                    ),
                )

            checks = recorder.checks
            context.close()
            browser.close()
    except Exception:
        status = "error"
        checks = recorder.checks if recorder is not None else checks
        error_detail = traceback.format_exc()[-2000:]
    finally:
        try:
            cleanup(api_token, target_id if target_id is not None else 57)
        except Exception:
            pass
        if status == "error":
            checks = checks or []
            if not checks:
                checks = [
                    {
                        "name": "Exécution Playwright",
                        "status": "skipped",
                        "expected": "navigateur et scénarios exécutables",
                        "detail": error_detail if "error_detail" in globals() else "",
                        "path": "/",
                        "duration_s": 0.0,
                        "screenshot": "",
                    }
                ]
        anomalies = build_anomalies(checks)
        summary = {
            "checks": len(checks),
            "passed": sum(1 for check in checks if check["status"] == "passed"),
            "failed": sum(1 for check in checks if check["status"] == "failed"),
            "skipped": sum(1 for check in checks if check["status"] == "skipped"),
            "anomalies": len(anomalies),
        }
        RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
        RESULTS_PATH.write_text(
            json.dumps(
                {
                    "status": status,
                    "ui_url": UI_URL,
                    "api_url": API_URL,
                    "summary": summary,
                    "checks": checks,
                    "anomalies": anomalies,
                },
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
'''


class UiSuite:
    """Génère et exécute les scénarios Playwright réels."""

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        executor: Callable[[Path, Path, dict], subprocess.CompletedProcess]
        | None = None,
        preflight: Callable[[str, float], str | None] | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self._executor = executor or self._default_executor
        self._preflight = preflight or self._default_preflight

    def _default_executor(
        self,
        script_path: Path,
        directory: Path,
        env: dict,
    ) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(script_path)],
            cwd=directory,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=self.settings.ui_automation_timeout_seconds,
        )

    def _default_preflight(self, ui_url: str, timeout: float) -> str | None:
        try:
            response = httpx.get(
                ui_url.rstrip("/") + "/",
                timeout=timeout,
                follow_redirects=True,
            )
        except httpx.HTTPError as exc:
            return f"Frontend de test injoignable ({type(exc).__name__})."
        if response.status_code != 200:
            return f"Frontend de test en erreur (HTTP {response.status_code})."
        return None

    def run(self, mission_id: str) -> UiSuiteOutcome:
        ensure_test_ui_url(self.settings.test_ui_url)
        ensure_test_api_url(self.settings.test_api_url)
        ui_url = self.settings.test_ui_url.rstrip("/")

        directory = mission_workspace(self.settings, mission_id) / "ui-automation"
        directory.mkdir(parents=True, exist_ok=True)
        script_path = directory / "run_ui_checks.py"
        script_path.write_text(UI_RUNNER_SCRIPT, encoding="utf-8")
        screenshots = directory / "screenshots"
        screenshots.mkdir(parents=True, exist_ok=True)
        raw_results = directory / "ui-playwright-results.json"

        blocked_reason = self._preflight(
            ui_url,
            self.settings.api_probe_timeout_seconds,
        )
        if blocked_reason:
            return self._write_outcome(
                mission_id,
                ui_url,
                script_path,
                status="blocked",
                checks=[],
                anomalies=[],
                blocked_reason=blocked_reason,
                log="",
                duration=0.0,
            )

        env = os.environ.copy()
        env.update(
            {
                "FOOTBALL_QA_UI_URL": ui_url,
                "FOOTBALL_QA_API_URL": self.settings.test_api_url.rstrip("/"),
                "FOOTBALL_QA_USER1_EMAIL": self.settings.test_user1_email,
                "FOOTBALL_QA_USER1_PASSWORD": self.settings.test_user1_password,
                "FOOTBALL_QA_UI_RESULTS": str(raw_results),
                "FOOTBALL_QA_UI_SCREENSHOTS": str(screenshots),
                "FOOTBALL_QA_UI_HEADLESS": (
                    "true" if self.settings.ui_browser_headless else "false"
                ),
                "PYTHONIOENCODING": "utf-8",
            }
        )

        started = time.perf_counter()
        try:
            completed = self._executor(script_path, directory, env)
        except subprocess.TimeoutExpired:
            return self._write_outcome(
                mission_id,
                ui_url,
                script_path,
                status="blocked",
                checks=[],
                anomalies=[],
                blocked_reason=(
                    "Scénarios Playwright interrompus après "
                    f"{self.settings.ui_automation_timeout_seconds:.0f} s."
                ),
                log="",
                duration=0.0,
            )
        except OSError as exc:
            return self._write_outcome(
                mission_id,
                ui_url,
                script_path,
                status="blocked",
                checks=[],
                anomalies=[],
                blocked_reason=f"Exécution Playwright impossible ({type(exc).__name__}).",
                log="",
                duration=0.0,
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
            "ui-automation/playwright.log",
            log,
        )

        if not raw_results.is_file():
            return self._write_outcome(
                mission_id,
                ui_url,
                script_path,
                status="blocked",
                checks=[],
                anomalies=[],
                blocked_reason=(
                    "Playwright n'a produit aucun résultat "
                    f"(code retour {completed.returncode})."
                ),
                log=log,
                duration=duration,
                extra_evidence=[str(log_path)],
            )

        try:
            payload = json.loads(raw_results.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return self._write_outcome(
                mission_id,
                ui_url,
                script_path,
                status="blocked",
                checks=[],
                anomalies=[],
                blocked_reason="Résultats Playwright illisibles.",
                log=log,
                duration=duration,
                extra_evidence=[str(log_path)],
            )

        checks = [
            UiSuiteCheck(
                name=check.get("name", "scénario"),
                status=check.get("status", "failed"),
                expected=check.get("expected", ""),
                detail=redact_text(str(check.get("detail", "")), secrets)[:2000],
                path=check.get("path", ""),
                duration_s=float(check.get("duration_s") or 0.0),
                screenshot=check.get("screenshot", ""),
            )
            for check in payload.get("checks", [])
        ]
        anomalies = [
            {
                **anomaly,
                "actual": redact_text(str(anomaly.get("actual", "")), secrets)[:2000],
            }
            for anomaly in payload.get("anomalies", [])
        ]
        status = payload.get("status", "completed")
        return self._write_outcome(
            mission_id,
            ui_url,
            script_path,
            status="completed" if status == "completed" else "blocked",
            checks=checks,
            anomalies=anomalies if status == "completed" else [],
            blocked_reason=(
                None
                if status == "completed"
                else "Exécution Playwright incomplète (erreur technique)."
            ),
            log=log,
            duration=duration,
            extra_evidence=[str(log_path), str(raw_results), *screenshots.glob("*.png")],
        )

    def _write_outcome(
        self,
        mission_id: str,
        ui_url: str,
        script_path: Path,
        *,
        status: str,
        checks: list[UiSuiteCheck],
        anomalies: list[dict],
        blocked_reason: str | None,
        log: str,
        duration: float,
        extra_evidence: list = None,
    ) -> UiSuiteOutcome:
        extra_evidence = extra_evidence or []
        executed = [check for check in checks if check.status != "skipped"]
        passed = [check for check in executed if check.status == "passed"]
        failed = [check for check in executed if check.status == "failed"]
        skipped = [check for check in checks if check.status == "skipped"]

        if status == "blocked":
            summary = (
                "Scénarios Playwright non exécutés : "
                f"{blocked_reason or 'frontend indisponible.'} "
                "Aucune anomalie applicative n'est déclarée."
            )
        else:
            summary = (
                f"Scénarios Playwright exécutés : {len(passed)}/{len(executed)} "
                f"scénarios réussis, {len(failed)} échec(s), {len(skipped)} ignoré(s), "
                f"{len(anomalies)} anomalie(s) reproductible(s)."
            )

        results = {
            "mission_id": mission_id,
            "ui_url": ui_url,
            "status": status,
            "blocked_reason": blocked_reason,
            "summary": {
                "checks": len(checks),
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
            "ui-automation/ui-automation-results.json",
            results,
        )
        report_path = write_mission_text(
            self.settings,
            mission_id,
            "ui-automation/ui-automation-report.md",
            self._markdown(mission_id, ui_url, status, checks, anomalies, blocked_reason),
        )
        evidence = [
            str(script_path),
            str(results_path),
            str(report_path),
            *[str(path) for path in extra_evidence],
        ]
        return UiSuiteOutcome(
            status=status,
            checks=checks,
            anomalies=anomalies,
            evidence_paths=evidence,
            summary=summary,
            blocked_reason=blocked_reason,
        )

    @staticmethod
    def _markdown(
        mission_id: str,
        ui_url: str,
        status: str,
        checks: list[UiSuiteCheck],
        anomalies: list[dict],
        blocked_reason: str | None,
    ) -> str:
        executed = [check for check in checks if check.status != "skipped"]
        passed = [check for check in executed if check.status == "passed"]
        skipped = [check for check in checks if check.status == "skipped"]
        lines = [
            f"# Automatisation UI Playwright — mission {mission_id}",
            "",
            f"- Frontend cible : `{ui_url}`",
            f"- Statut : `{status}`",
            f"- Scénarios exécutés : {len(executed)}",
            f"- Réussis : {len(passed)}",
            f"- Ignorés : {len(skipped)}",
            f"- Anomalies : {len(anomalies)}",
            "",
        ]
        if blocked_reason:
            lines.extend([f"> Scénarios non exécutés : {blocked_reason}", ""])
        lines.extend(
            [
                "## Scénarios",
                "",
                "| Scénario | Attendu | Durée (s) | Résultat |",
                "|---|---|---|---|",
            ]
        )
        for check in checks:
            outcome = {
                "passed": "réussi",
                "failed": "échec",
                "skipped": "ignoré",
            }.get(check.status, check.status)
            lines.append(
                f"| {check.name} | {check.expected} | {check.duration_s:.3f} | {outcome} |"
            )
        lines.extend(["", "## Anomalies", ""])
        if not anomalies:
            lines.append(
                "Aucune anomalie déclarée : aucun scénario exécuté n'a échoué."
                if status == "completed"
                else "Aucune anomalie applicative : les scénarios n'ont pas été exécutés."
            )
        else:
            for index, anomaly in enumerate(anomalies, start=1):
                lines.extend(
                    [
                        f"### {index}. {anomaly.get('check', 'Scénario')}",
                        "",
                        f"- Reproduction : `{anomaly.get('reproduction', '')}`",
                        f"- Attendu : {anomaly.get('expected', '')}",
                        f"- Obtenu : {str(anomaly.get('actual', ''))[:1500]}",
                        f"- Capture : `{anomaly.get('screenshot', '')}`",
                        "",
                    ]
                )
        lines.append("")
        return "\n".join(lines)
