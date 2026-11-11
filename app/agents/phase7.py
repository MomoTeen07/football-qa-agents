"""Agents 6 et 7 (phase 7).

- DevOps : prépare ou publie une branche et une pull request pour les suites
  générées, sans jamais pousser sur `main`. Mode préparation par défaut.
- QA Reporter : agrège les preuves des phases 5 et 6, produit le rapport
  Markdown enrichi, une synthèse JSON et des résultats Allure 2 standards.

Aucun agent ne déclare d'anomalie sans preuve réelle. Une cible indisponible,
un dépôt non propre ou un outil absent produit un statut bloqué sans anomalie.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from app.agents.base import BaseAgent
from app.config import Settings, get_settings
from app.domain.models import AgentResult, Mission, Task
from app.tools.allure_report import AllureOutcome, AllureReport, AllureSuite
from app.tools.devops import DevOpsOutcome, DevOpsPromotion

logger = logging.getLogger(__name__)

DEVOPS_FALLBACK = (
    "Préparation DevOps à exécuter : branche dédiée, commit des suites "
    "générées, pull request, CI passive. Aucun push direct sur main, aucune "
    "fusion automatique. Aucune opération Git n'a été exécutée."
)


class DevOpsAgent(BaseAgent):
    name = "devops"
    label = "DevOps"

    def __init__(
        self,
        settings: Settings | None = None,
        promotion: DevOpsPromotion | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.promotion = promotion or DevOpsPromotion(self.settings)

    def run(self, task: Task, mission: Mission, context: dict | None = None) -> AgentResult:
        if not self.settings.real_agents_enabled:
            return AgentResult(
                agent=self.name,
                summary=DEVOPS_FALLBACK,
                artifacts=["branche + PR (déterministe)"],
            )

        try:
            outcome = self.promotion.run(mission.id)
        except Exception as exc:  # pragma: no cover - garde-fou d'exécution
            logger.warning(
                "Promotion DevOps indisponible (%s).", type(exc).__name__
            )
            return AgentResult(
                agent=self.name,
                summary=(
                    "Promotion Git non exécutée : "
                    f"{type(exc).__name__}. Aucune anomalie déclarée."
                ),
                artifacts=[],
            )

        lines = [outcome.summary]
        if outcome.branch:
            lines.append(f"- Branche : `{outcome.branch}`")
        if outcome.commit:
            lines.append(f"- Commit : `{outcome.commit}`")
        if outcome.pr_url:
            lines.append(f"- Pull request : {outcome.pr_url}")
        if outcome.blocked_reason:
            lines.append(f"- Non exécution : {outcome.blocked_reason}")

        artifacts = [outcome.pr_url] if outcome.pr_url else []
        return AgentResult(
            agent=self.name,
            summary="\n".join(lines),
            artifacts=artifacts,
            evidence=outcome.evidence_paths,
        )


class QAReporterAgent(BaseAgent):
    name = "qa_reporter"
    label = "QA Reporter"

    def __init__(
        self,
        settings: Settings | None = None,
        allure: AllureReport | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.allure = allure or AllureReport(self.settings)

    def run(self, task: Task, mission: Mission, context: dict | None = None) -> AgentResult:
        tasks = (context or {}).get("tasks", [])
        probe = self._load_results(mission.id, "api/probe-results.json")
        api_auto = self._load_results(
            mission.id, "api-automation/api-automation-results.json"
        )
        ui_auto = self._load_results(
            mission.id, "ui-automation/ui-automation-results.json"
        )

        anomalies: list[tuple[str, dict]] = []
        for source, payload in (
            ("Sonde API", probe),
            ("Automatisation API", api_auto),
            ("Automatisation UI", ui_auto),
        ):
            if payload:
                anomalies.extend(
                    (source, item) for item in payload.get("anomalies", [])
                )

        suites = [
            AllureSuite("Sondes API (phase 5)", "probe", probe),
            AllureSuite("Automatisation API pytest (phase 6)", "api", api_auto),
            AllureSuite(
                "Automatisation UI Playwright (phase 6)", "ui", ui_auto
            ),
        ]
        allure_outcome: AllureOutcome | None = None
        allure_error: str | None = None
        try:
            allure_outcome = self.allure.generate(mission.id, suites)
        except Exception as exc:  # pragma: no cover - garde-fou d'exécution
            logger.warning(
                "Rapport Allure indisponible (%s).", type(exc).__name__
            )
            allure_error = type(exc).__name__

        lines = [
            f"# Rapport de mission — {mission.id}",
            "",
            f"**Instruction :** {mission.instruction}",
            "",
            "## Statut",
            "",
            "Mission exécutée par le Manager QA.",
            "",
        ]
        lines.extend(self._synthesis_lines(probe, api_auto, ui_auto))
        lines.extend(["## Tâches", ""])
        for item in tasks:
            lines.append(
                f"- **{item['agent']}** — {item['title']} : `{item['status']}`"
            )

        lines.extend(["", "## Résultats", ""])
        if not (probe or api_auto or ui_auto):
            lines.extend(
                [
                    "Les agents ont produit des plans et des livrables à exécuter. "
                    "Aucun test réel n'a été exécuté durant cette mission.",
                    "",
                ]
            )
        else:
            lines.extend(
                [
                    "Des exécutions réelles ont été réalisées ; les preuves sont "
                    "conservées localement.",
                    "",
                ]
            )
            if probe:
                lines.extend(self._probe_lines(mission.id, probe))
            if api_auto:
                lines.extend(
                    self._automation_lines(
                        "Automatisation API pytest (phase 6)",
                        mission.id,
                        "api-automation",
                        "tests",
                        api_auto,
                    )
                )
            if ui_auto:
                lines.extend(
                    self._automation_lines(
                        "Automatisation UI Playwright (phase 6)",
                        mission.id,
                        "ui-automation",
                        "checks",
                        ui_auto,
                    )
                )

        lines.extend(["## Anomalies", ""])
        if anomalies:
            for index, (source, anomaly) in enumerate(anomalies, start=1):
                lines.extend(
                    [
                        f"### {index}. [{source}] {anomaly.get('check', 'Anomalie')}",
                        "",
                        f"- Reproduction : `{anomaly.get('reproduction', 'non fournie')}`",
                        f"- Attendu : {anomaly.get('expected', 'non précisé')}",
                        f"- Obtenu : {anomaly.get('actual', 'non précisé')}",
                    ]
                )
                evidence = anomaly.get("evidence") or anomaly.get("screenshot")
                if evidence:
                    lines.append(f"- Preuve : `{evidence}`")
                lines.append("")
        else:
            lines.extend(self._no_anomaly_lines(probe, api_auto, ui_auto))

        lines.extend(["", *self._allure_lines(allure_outcome, allure_error)])
        lines.extend(["## Prochaine étape", ""])
        if probe or api_auto or ui_auto:
            lines.extend(
                [
                    "Consulter le rapport Allure, la synthèse JSON et les preuves "
                    "de mission. La phase 8 (bureau virtuel 2D) reste à démarrer "
                    "sur demande explicite.",
                    "",
                ]
            )
        else:
            lines.extend(
                [
                    "Exécuter les suites sur la stack de test isolée et joindre "
                    "les preuves.",
                    "",
                ]
            )

        json_path = self._write_json_report(
            mission,
            tasks=tasks,
            probe=probe,
            api_auto=api_auto,
            ui_auto=ui_auto,
            anomalies=anomalies,
            allure_outcome=allure_outcome,
            allure_error=allure_error,
        )
        evidence = ([str(json_path)] if json_path else []) + (
            allure_outcome.evidence_paths if allure_outcome else []
        )
        artifacts = (
            [allure_outcome.results_dir]
            if allure_outcome and allure_outcome.results_dir
            else []
        )
        return AgentResult(
            agent=self.name,
            summary="\n".join(lines),
            artifacts=artifacts,
            evidence=evidence,
        )

    # ------------------------------------------------------------------
    # Chargement et synthèse
    # ------------------------------------------------------------------
    def _load_results(self, mission_id: str, relative_path: str) -> dict | None:
        path = (
            Path(self.settings.workspace_dir)
            / "missions"
            / mission_id
            / relative_path
        )
        if not path.is_file():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    @staticmethod
    def _synthesis_lines(
        probe: dict | None,
        api_auto: dict | None,
        ui_auto: dict | None,
    ) -> list[str]:
        rows: list[tuple] = []
        if probe:
            checks = probe.get("checks", [])
            executed = [check for check in checks if not check.get("skipped")]
            rows.append(
                (
                    "Sondes API (phase 5)",
                    probe.get("status", "inconnu"),
                    len(checks),
                    sum(1 for check in executed if check.get("passed")),
                    sum(1 for check in executed if not check.get("passed")),
                    sum(1 for check in checks if check.get("skipped")),
                    len(probe.get("anomalies", [])),
                )
            )
        if api_auto:
            summary = api_auto.get("summary") or {}
            rows.append(
                (
                    "Automatisation API (phase 6)",
                    api_auto.get("status", "inconnu"),
                    int(summary.get("tests", 0) or 0),
                    int(summary.get("passed", 0) or 0),
                    int(summary.get("failed", 0) or 0),
                    int(summary.get("skipped", 0) or 0),
                    int(
                        summary.get(
                            "anomalies", len(api_auto.get("anomalies", []))
                        )
                        or 0
                    ),
                )
            )
        if ui_auto:
            summary = ui_auto.get("summary") or {}
            rows.append(
                (
                    "Automatisation UI (phase 6)",
                    ui_auto.get("status", "inconnu"),
                    int(summary.get("checks", 0) or 0),
                    int(summary.get("passed", 0) or 0),
                    int(summary.get("failed", 0) or 0),
                    int(summary.get("skipped", 0) or 0),
                    int(
                        summary.get(
                            "anomalies", len(ui_auto.get("anomalies", []))
                        )
                        or 0
                    ),
                )
            )

        lines = ["## Synthèse globale", ""]
        if not rows:
            lines.extend(
                ["Aucune source d'exécution réelle pour cette mission.", ""]
            )
            return lines

        lines.extend(
            [
                "| Source | Statut | Total | Réussis | Échecs | Ignorés | Anomalies |",
                "|---|---|---|---|---|---|---|",
            ]
        )
        for row in rows:
            lines.append(
                f"| {row[0]} | `{row[1]}` | {row[2]} | {row[3]} | {row[4]} | "
                f"{row[5]} | {row[6]} |"
            )
        total = (
            sum(row[2] for row in rows),
            sum(row[3] for row in rows),
            sum(row[4] for row in rows),
            sum(row[5] for row in rows),
            sum(row[6] for row in rows),
        )
        lines.append(
            f"| **Total** | — | {total[0]} | {total[1]} | {total[2]} | "
            f"{total[3]} | {total[4]} |"
        )
        lines.append("")
        return lines

    @staticmethod
    def _allure_lines(
        outcome: AllureOutcome | None,
        error: str | None,
    ) -> list[str]:
        lines = ["## Rapport Allure", ""]
        if error:
            lines.extend(
                [
                    f"Rapport Allure non généré ({error}). "
                    "Les synthèses Markdown/JSON restent disponibles.",
                    "",
                ]
            )
        elif outcome and outcome.status == "completed":
            lines.extend(
                [
                    f"- Résultats Allure 2 : `{outcome.results_dir}`",
                    f"- Synthèse JSON : `{outcome.summary_path}`",
                    f"- Aperçu Markdown : `{outcome.report_path}`",
                    f"- Résultats : {outcome.total} — {outcome.passed} réussi(s), "
                    f"{outcome.failed} échec(s), {outcome.broken} cassé(s), "
                    f"{outcome.skipped} ignoré(s), "
                    f"{outcome.anomalies} anomalie(s).",
                    "- Rendu HTML : `allure serve \"<dossier>\"` "
                    "(CLI Allure gratuite, optionnelle).",
                    "",
                ]
            )
        else:
            lines.extend(
                [
                    "Aucune exécution réelle : aucun résultat Allure généré.",
                    "",
                ]
            )
        return lines

    # ------------------------------------------------------------------
    # Rapport machine
    # ------------------------------------------------------------------
    def _write_json_report(
        self,
        mission: Mission,
        *,
        tasks: list[dict],
        probe: dict | None,
        api_auto: dict | None,
        ui_auto: dict | None,
        anomalies: list[tuple[str, dict]],
        allure_outcome: AllureOutcome | None,
        allure_error: str | None,
    ) -> Path | None:
        reports_dir = Path(self.settings.reports_dir)
        payload = {
            "mission_id": mission.id,
            "instruction": mission.instruction,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "tasks": tasks,
            "sources": {
                "probe": _source_summary(probe),
                "api_automation": _source_summary(api_auto),
                "ui_automation": _source_summary(ui_auto),
            },
            "anomalies": [
                {"source": source, **anomaly} for source, anomaly in anomalies
            ],
            "allure": (
                {
                    "status": allure_outcome.status,
                    "total": allure_outcome.total,
                    "passed": allure_outcome.passed,
                    "failed": allure_outcome.failed,
                    "broken": allure_outcome.broken,
                    "skipped": allure_outcome.skipped,
                    "anomalies": allure_outcome.anomalies,
                    "results_dir": allure_outcome.results_dir,
                    "summary_path": allure_outcome.summary_path,
                    "report_path": allure_outcome.report_path,
                }
                if allure_outcome
                else {"status": "error", "error": allure_error}
            ),
        }
        try:
            reports_dir.mkdir(parents=True, exist_ok=True)
            path = reports_dir / f"{mission.id}.json"
            path.write_text(
                json.dumps(payload, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            return path
        except OSError:  # pragma: no cover - garde-fou d'écriture
            logger.warning("Synthèse JSON non écrite.")
            return None

    # ------------------------------------------------------------------
    # Sections existantes (phases 5 et 6)
    # ------------------------------------------------------------------
    @staticmethod
    def _probe_lines(mission_id: str, probe: dict) -> list[str]:
        checks = probe.get("checks", [])
        executed = [check for check in checks if not check.get("skipped")]
        passed = [check for check in executed if check.get("passed")]
        return [
            "### Sondes API réelles (phase 5)",
            "",
            "Des sondes API réelles ont été exécutées sur la stack de test.",
            "",
            f"- Statut des sondes : `{probe.get('status', 'inconnu')}`",
            f"- Vérifications exécutées : {len(executed)}",
            f"- Réussies : {len(passed)}",
            f"- Anomalies : {len(probe.get('anomalies', []))}",
            f"- Preuves : `workspace/missions/{mission_id}/api/`",
            "",
        ]

    @staticmethod
    def _automation_lines(
        title: str,
        mission_id: str,
        folder: str,
        count_key: str,
        payload: dict,
    ) -> list[str]:
        summary = payload.get("summary") or {}
        total = int(summary.get(count_key, 0) or 0)
        skipped = int(summary.get("skipped", 0) or 0)
        lines = [
            f"### {title}",
            "",
            f"- Statut : `{payload.get('status', 'inconnu')}`",
            f"- Exécutés : {max(total - skipped, 0)}",
            f"- Réussis : {summary.get('passed', 0)}",
            f"- Échecs : {summary.get('failed', 0)}",
            f"- Ignorés : {skipped}",
            f"- Anomalies : {summary.get('anomalies', len(payload.get('anomalies', [])))}",
            f"- Preuves : `workspace/missions/{mission_id}/{folder}/`",
        ]
        blocked_reason = payload.get("blocked_reason")
        if blocked_reason:
            lines.append(f"- Non exécution : {blocked_reason}")
        lines.append("")
        return lines

    @staticmethod
    def _no_anomaly_lines(
        probe: dict | None,
        api_auto: dict | None,
        ui_auto: dict | None,
    ) -> list[str]:
        payloads = [payload for payload in (probe, api_auto, ui_auto) if payload]
        if not payloads:
            return [
                "Aucune anomalie déclarée : aucune exécution réelle n'a eu lieu.",
                "",
            ]
        if all(payload.get("status") == "completed" for payload in payloads):
            return [
                "Aucune anomalie déclarée : les exécutions réelles n'ont révélé "
                "aucun écart avec les résultats attendus.",
                "",
            ]
        return [
            "Aucune anomalie déclarée : au moins une exécution n'a pas pu être "
            "réalisée.",
            "",
        ]


def _source_summary(payload: dict | None) -> dict | None:
    if not payload:
        return None
    return {
        "status": payload.get("status"),
        "summary": payload.get("summary"),
        "blocked_reason": payload.get("blocked_reason"),
    }
