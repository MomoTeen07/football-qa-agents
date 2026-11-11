"""Génération de résultats Allure 2 et de synthèses Markdown/JSON (phase 7).

Le module ne dépend d'aucun paquet supplémentaire : il écrit des fichiers
`allure-results` au format JSON standard, consommables par la CLI Allure, ainsi
qu'une synthèse Markdown et JSON autonome. La CLI Allure reste optionnelle.

Aucune anomalie n'est inventée : seules les preuves réellement présentes dans
le workspace de la mission sont converties.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from app.config import Settings, get_settings
from app.security import known_secrets, redact_structure
from app.tools.redaction import redact_text


@dataclass
class AllureSuite:
    """Une source de preuves à convertir en résultats Allure."""

    label: str
    kind: str  # "probe", "api" ou "ui"
    payload: dict | None = None


@dataclass
class AllureOutcome:
    status: str
    total: int = 0
    passed: int = 0
    failed: int = 0
    broken: int = 0
    skipped: int = 0
    anomalies: int = 0
    results_dir: str = ""
    summary_path: str = ""
    report_path: str = ""
    summary: str = ""
    evidence_paths: list[str] = field(default_factory=list)


@dataclass
class _Case:
    suite: str
    name: str
    status: str
    duration_ms: int = 0
    message: str = ""
    trace: str = ""
    reproduction: str = ""
    tags: tuple[str, ...] = ()
    text_attachments: list[tuple[str, str]] = field(default_factory=list)
    screenshot: str = ""


class AllureReport:
    """Convertit les preuves d'une mission en résultats Allure 2."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    # ------------------------------------------------------------------
    # API publique
    # ------------------------------------------------------------------
    def generate(
        self,
        mission_id: str,
        suites: list[AllureSuite],
    ) -> AllureOutcome:
        cases: list[_Case] = []
        suite_summaries: list[dict] = []
        anomalies: list[dict] = []

        for suite in suites:
            suite_cases = self._cases_from_payload(suite)
            cases.extend(suite_cases)
            if suite.payload:
                anomalies.extend(
                    dict(anomaly, suite=suite.label)
                    for anomaly in suite.payload.get("anomalies", [])
                )
            suite_summaries.append(
                {
                    "name": suite.label,
                    "status": (suite.payload or {}).get("status", "absent"),
                    "totals": _totals(suite_cases),
                }
            )

        if not cases:
            return AllureOutcome(
                status="skipped",
                summary=(
                    "Aucune exécution réelle : aucun résultat Allure n'a été "
                    "généré."
                ),
            )

        directory = Path(self.settings.allure_results_dir) / mission_id
        # Ne jamais réutiliser les résultats d'une génération précédente.
        shutil.rmtree(directory, ignore_errors=True)
        directory.mkdir(parents=True, exist_ok=True)

        mission_dir = (
            Path(self.settings.workspace_dir) / "missions" / mission_id
        )
        secrets = known_secrets(self.settings)
        stopped = int(time.time() * 1000)
        for index, case in enumerate(cases):
            result = redact_structure(
                self._result_payload(
                    mission_id,
                    directory,
                    mission_dir,
                    case,
                    index,
                    stopped,
                    secrets,
                ),
                secrets,
            )
            filename = f"{result['uuid']}-result.json"
            (directory / filename).write_text(
                json.dumps(result, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

        environment = {
            "Mission": mission_id,
            "API de test": self.settings.test_api_url,
            "UI de test": self.settings.test_ui_url,
            "Framework": "pytest + playwright",
        }
        (directory / "environment.properties").write_text(
            "\n".join(
                f"{_escape_property(key)}={_escape_property(value)}"
                for key, value in environment.items()
            )
            + "\n",
            encoding="utf-8",
        )
        (directory / "executor.json").write_text(
            json.dumps(
                {
                    "name": "football-qa-agents",
                    "type": "local",
                    "buildName": f"Mission {mission_id}",
                    "buildOrder": 1,
                    "reportName": "Football QA Agents — Rapport Allure",
                },
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        totals = _totals(cases)
        summary_payload = redact_structure({
            "mission_id": mission_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "status": "completed",
            "totals": {**totals, "anomalies": len(anomalies)},
            "suites": suite_summaries,
            "anomalies": anomalies,
            "results_dir": str(directory),
        }, secrets)
        summary_path = directory / "allure-summary.json"
        summary_path.write_text(
            json.dumps(summary_payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        report_path = directory / "allure-report.md"
        report_path.write_text(
            redact_text(
                _markdown(
                    mission_id,
                    totals,
                    suite_summaries,
                    anomalies,
                    directory,
                ),
                secrets,
            ),
            encoding="utf-8",
        )

        summary = (
            f"Rapport Allure généré : {totals['total']} résultat(s) — "
            f"{totals['passed']} réussi(s), {totals['failed']} échec(s), "
            f"{totals['broken']} cassé(s), {totals['skipped']} ignoré(s), "
            f"{len(anomalies)} anomalie(s)."
        )
        return AllureOutcome(
            status="completed",
            total=totals["total"],
            passed=totals["passed"],
            failed=totals["failed"],
            broken=totals["broken"],
            skipped=totals["skipped"],
            anomalies=len(anomalies),
            results_dir=str(directory),
            summary_path=str(summary_path),
            report_path=str(report_path),
            summary=summary,
            evidence_paths=[str(directory), str(summary_path), str(report_path)],
        )

    # ------------------------------------------------------------------
    # Conversion des preuves
    # ------------------------------------------------------------------
    def _cases_from_payload(self, suite: AllureSuite) -> list[_Case]:
        payload = suite.payload
        if not payload:
            return []
        if payload.get("status") == "blocked":
            return [
                _Case(
                    suite=suite.label,
                    name="Exécution non réalisée",
                    status="skipped",
                    message=payload.get("blocked_reason")
                    or "Cible indisponible ou exécution impossible.",
                    tags=("blocked",),
                )
            ]
        if suite.kind == "probe":
            return self._probe_cases(suite.label, payload)
        if suite.kind == "api":
            return self._api_cases(suite.label, payload)
        if suite.kind == "ui":
            return self._ui_cases(suite.label, payload)
        return []

    @staticmethod
    def _probe_cases(label: str, payload: dict) -> list[_Case]:
        base_url = str(payload.get("base_url", "")).rstrip("/")
        cases: list[_Case] = []
        for check in payload.get("checks", []):
            name = str(check.get("name", "vérification"))
            if check.get("skipped"):
                status = "skipped"
                message = check.get("detail") or "Vérification non exécutée."
            elif check.get("passed"):
                status = "passed"
                message = ""
            else:
                status = "failed"
                message = (
                    f"Attendu : {check.get('expected', 'non précisé')} — "
                    f"obtenu : {check.get('actual', 'non précisé')}"
                )
            reproduction = (
                f"{check.get('method', '')} "
                f"{base_url}{check.get('path', '')}"
            ).strip()
            text_attachments: list[tuple[str, str]] = []
            excerpt = str(check.get("response_excerpt") or "")
            if excerpt:
                text_attachments.append(("Extrait de réponse", excerpt))
            cases.append(
                _Case(
                    suite=label,
                    name=name,
                    status=status,
                    duration_ms=int(check.get("duration_ms") or 0),
                    message=message,
                    trace=str(check.get("detail") or excerpt),
                    reproduction=reproduction,
                    tags=("api", "probe", "phase5"),
                    text_attachments=text_attachments,
                )
            )
        if not cases:
            cases.append(
                _Case(
                    suite=label,
                    name="Aucune vérification",
                    status="skipped",
                    message="La source ne contient aucune vérification.",
                    tags=("absent",),
                )
            )
        return cases

    @staticmethod
    def _api_cases(label: str, payload: dict) -> list[_Case]:
        anomalies = {
            str(anomaly.get("check", "")): anomaly
            for anomaly in payload.get("anomalies", [])
        }
        base_url = str(payload.get("base_url", "")).rstrip("/")
        status_map = {
            "passed": "passed",
            "failed": "failed",
            "error": "broken",
            "skipped": "skipped",
        }
        cases: list[_Case] = []
        for check in payload.get("checks", []):
            name = str(check.get("name", "test"))
            outcome = str(check.get("outcome", "failed"))
            status = status_map.get(outcome, "broken")
            anomaly = anomalies.get(name, {})
            message = ""
            if status != "passed":
                expected = anomaly.get("expected", "")
                actual = anomaly.get("actual", "")
                if expected or actual:
                    message = (
                        f"Attendu : {expected or 'non précisé'} — "
                        f"obtenu : {actual or 'non précisé'}"
                    )
                else:
                    message = str(check.get("detail") or "Échec du test.")
            reproduction = str(anomaly.get("reproduction", ""))
            if not reproduction:
                method = check.get("method", "")
                path = check.get("path", "")
                if method or path:
                    reproduction = f"{method} {base_url}{path}".strip()
            text_attachments: list[tuple[str, str]] = []
            detail = str(check.get("detail") or anomaly.get("evidence") or "")
            if detail and status != "passed":
                text_attachments.append(("Détail de l'échec", detail))
            cases.append(
                _Case(
                    suite=label,
                    name=name,
                    status=status,
                    duration_ms=int(float(check.get("duration_s") or 0.0) * 1000),
                    message=message,
                    trace=str(check.get("detail") or ""),
                    reproduction=reproduction,
                    tags=("api", "pytest", "phase6"),
                    text_attachments=text_attachments,
                )
            )
        if not cases:
            cases.append(
                _Case(
                    suite=label,
                    name="Aucun test",
                    status="skipped",
                    message="La source ne contient aucun test.",
                    tags=("absent",),
                )
            )
        return cases

    @staticmethod
    def _ui_cases(label: str, payload: dict) -> list[_Case]:
        anomalies = {
            str(anomaly.get("check", "")): anomaly
            for anomaly in payload.get("anomalies", [])
        }
        ui_url = str(payload.get("ui_url", "")).rstrip("/")
        cases: list[_Case] = []
        for check in payload.get("checks", []):
            name = str(check.get("name", "scénario"))
            status = str(check.get("status", "failed"))
            if status not in {"passed", "failed", "broken", "skipped"}:
                status = "broken"
            anomaly = anomalies.get(name, {})
            message = ""
            if status != "passed":
                expected = check.get("expected") or anomaly.get("expected", "")
                actual = check.get("detail") or anomaly.get("actual", "")
                if expected or actual:
                    message = (
                        f"Attendu : {expected or 'non précisé'} — "
                        f"obtenu : {actual or 'non précisé'}"
                    )
                else:
                    message = str(check.get("detail") or "Échec du scénario.")
            reproduction = str(anomaly.get("reproduction", ""))
            if not reproduction:
                path = str(check.get("path", ""))
                reproduction = f"Ouvrir {ui_url}{path}".strip()
            screenshot = str(
                anomaly.get("screenshot") or check.get("screenshot") or ""
            )
            text_attachments: list[tuple[str, str]] = []
            detail = str(anomaly.get("actual") or check.get("detail") or "")
            if detail and status != "passed":
                text_attachments.append(("Détail de l'échec", detail))
            cases.append(
                _Case(
                    suite=label,
                    name=name,
                    status=status,
                    duration_ms=int(float(check.get("duration_s") or 0.0) * 1000),
                    message=message,
                    trace=str(check.get("detail") or ""),
                    reproduction=reproduction,
                    tags=("ui", "playwright", "phase6"),
                    text_attachments=text_attachments,
                    screenshot=screenshot,
                )
            )
        if not cases:
            cases.append(
                _Case(
                    suite=label,
                    name="Aucun scénario",
                    status="skipped",
                    message="La source ne contient aucun scénario.",
                    tags=("absent",),
                )
            )
        return cases

    # ------------------------------------------------------------------
    # Écriture d'un résultat Allure
    # ------------------------------------------------------------------
    def _result_payload(
        self,
        mission_id: str,
        directory: Path,
        mission_dir: Path,
        case: _Case,
        index: int,
        stopped: int,
        secrets: tuple[str, ...] = (),
    ) -> dict:
        identifier = str(
            uuid5(
                NAMESPACE_URL,
                f"football-qa/{mission_id}/{case.suite}/{case.name}/{index}",
            )
        )
        start = max(stopped - case.duration_ms, stopped - 86_400_000)
        full_name = f"{mission_id} :: {case.suite} :: {case.name}"

        details: dict = {"known": False, "muted": False, "flaky": False}
        if case.message:
            details["message"] = redact_text(case.message, secrets)
        if case.trace:
            details["trace"] = redact_text(case.trace, secrets)[:4000]

        attachments: list[dict] = []
        for attachment_index, (name, content) in enumerate(case.text_attachments):
            source = f"{identifier}-attachment-{attachment_index}.txt"
            (directory / source).write_text(
                redact_text(content, secrets),
                encoding="utf-8",
            )
            attachments.append(
                {"name": name, "source": source, "type": "text/plain"}
            )
        screenshot = self._resolve_screenshot(mission_dir, case.screenshot)
        if screenshot is not None:
            suffix = screenshot.suffix or ".png"
            source = f"{identifier}-screenshot{suffix}"
            shutil.copyfile(screenshot, directory / source)
            attachments.append(
                {
                    "name": "Capture d'écran",
                    "source": source,
                    "type": "image/png",
                }
            )

        labels = [
            {"name": "parentSuite", "value": f"Mission {mission_id}"},
            {"name": "suite", "value": case.suite},
            {
                "name": "framework",
                "value": "playwright" if "UI" in case.suite else "pytest",
            },
            {"name": "language", "value": "python"},
            {"name": "host", "value": "localhost"},
        ]
        labels.extend({"name": "tag", "value": tag} for tag in case.tags)

        links: list[dict] = []
        reproduction = case.reproduction.strip()
        url_match = re.search(r"https?://\S+", reproduction)
        if url_match:
            links.append(
                {
                    "name": "Reproduction",
                    "url": url_match.group(0).rstrip(".,;)"),
                    "type": "custom",
                }
            )

        return {
            "uuid": identifier,
            "historyId": hashlib.md5(full_name.encode("utf-8")).hexdigest(),
            "fullName": full_name,
            "name": case.name,
            "status": case.status,
            "statusDetails": details,
            "stage": "finished",
            "start": start,
            "stop": stopped,
            "labels": labels,
            "parameters": [],
            "links": links,
            "attachments": attachments,
        }

    @staticmethod
    def _resolve_screenshot(mission_dir: Path, reference: str) -> Path | None:
        if not reference:
            return None
        candidate = Path(reference)
        if candidate.is_absolute():
            return candidate if candidate.is_file() else None
        candidates = [
            mission_dir / candidate,
            mission_dir / "ui-automation" / candidate,
            mission_dir / "ui-automation" / "screenshots" / candidate.name,
        ]
        for path in candidates:
            if path.is_file():
                return path
        return None


def _totals(cases: list[_Case]) -> dict[str, int]:
    return {
        "total": len(cases),
        "passed": sum(1 for case in cases if case.status == "passed"),
        "failed": sum(1 for case in cases if case.status == "failed"),
        "broken": sum(1 for case in cases if case.status == "broken"),
        "skipped": sum(1 for case in cases if case.status == "skipped"),
    }


def _escape_property(value: str) -> str:
    return str(value).replace("\\", "\\\\").replace("\n", "\\n")


def _markdown(
    mission_id: str,
    totals: dict[str, int],
    suites: list[dict],
    anomalies: list[dict],
    directory: Path,
) -> str:
    lines = [
        f"# Rapport Allure — mission {mission_id}",
        "",
        f"- Résultats Allure 2 : `{directory}`",
        f"- Total : {totals['total']}",
        f"- Réussis : {totals['passed']}",
        f"- Échecs : {totals['failed']}",
        f"- Cassés : {totals['broken']}",
        f"- Ignorés : {totals['skipped']}",
        f"- Anomalies : {len(anomalies)}",
        "",
        "## Suites",
        "",
        "| Suite | Statut | Total | Réussis | Échecs | Cassés | Ignorés |",
        "|---|---|---|---|---|---|---|",
    ]
    for suite in suites:
        counts = suite["totals"]
        lines.append(
            f"| {suite['name']} | `{suite['status']}` | {counts['total']} | "
            f"{counts['passed']} | {counts['failed']} | {counts['broken']} | "
            f"{counts['skipped']} |"
        )

    lines.extend(["", "## Anomalies", ""])
    if anomalies:
        for index, anomaly in enumerate(anomalies, start=1):
            lines.extend(
                [
                    f"### {index}. [{anomaly.get('suite', 'source')}] "
                    f"{anomaly.get('check', 'Anomalie')}",
                    "",
                    f"- Attendu : {anomaly.get('expected', 'non précisé')}",
                    f"- Obtenu : {anomaly.get('actual', 'non précisé')}",
                    f"- Reproduction : `{anomaly.get('reproduction', 'non fournie')}`",
                ]
            )
            evidence = anomaly.get("evidence") or anomaly.get("screenshot")
            if evidence:
                lines.append(f"- Preuve : `{evidence}`")
            lines.append("")
    else:
        lines.extend(
            [
                "Aucune anomalie déclarée : les résultats réels n'ont révélé "
                "aucun écart.",
                "",
            ]
        )

    lines.extend(
        [
            "## Rendu HTML",
            "",
            "La CLI Allure (gratuite) reste optionnelle. Résultats standard :",
            "",
            "```powershell",
            f'allure serve "{directory}"',
            "```",
            "",
        ]
    )
    return "\n".join(lines)
