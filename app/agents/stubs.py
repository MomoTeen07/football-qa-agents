"""Agents de planification et de reporting.

Les agents 1 à 3 disposent d'implémentations réelles dans
`app.agents.phase5`. Les agents 4 à 7 restent des stubs de planification.
Aucun agent ne déclare d'anomalie sans preuve d'exécution.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.agents.base import BaseAgent
from app.config import get_settings
from app.domain.models import AgentResult, Mission, Task


class QAAnalystAgent(BaseAgent):
    name = "qa_analyst"
    label = "QA Analyst"

    def run(self, task: Task, mission: Mission, context: dict | None = None) -> AgentResult:
        return AgentResult(
            agent=self.name,
            summary=(
                "Stratégie de test proposée : analyser les parcours d'authentification, "
                "de consultation des championnats, de classement, de détail d'équipe et "
                "de gestion des favoris. Risques principaux : isolation des favoris entre "
                "utilisateurs, expiration JWT, cohérence des données football, états "
                "d'erreur de l'interface. Aucun test réel n'a été exécuté."
            ),
            artifacts=["plan de test (à produire en phase d'exécution)"],
        )


class TestDesignerAgent(BaseAgent):
    name = "test_designer"
    label = "Test Designer"

    def run(self, task: Task, mission: Mission, context: dict | None = None) -> AgentResult:
        return AgentResult(
            agent=self.name,
            summary=(
                "Cas de test proposés selon les techniques ISTQB : partitionnement "
                "d'équivalence sur les champs email/mot de passe, valeurs limites sur "
                "les identifiants, transitions d'état pour la session, tests négatifs "
                "sur les favoris en double et les accès non authentifiés. "
                "Traçabilité prévue : exigence → cas de test → exécution → anomalie."
            ),
            artifacts=["matrice de traçabilité (à produire)"],
        )


class APITesterAgent(BaseAgent):
    name = "api_tester"
    label = "API Tester"

    def run(self, task: Task, mission: Mission, context: dict | None = None) -> AgentResult:
        return AgentResult(
            agent=self.name,
            summary=(
                "Collection Postman à produire : santé, leagues, standings, matches, "
                "team, register, login, users/me, favorites (GET/POST/DELETE). "
                "Vérifications : méthodes HTTP, codes 200/201/204/400/401/404/409/422, "
                "JWT Bearer, isolation entre utilisateurs, schémas JSON. "
                "Aucune requête n'a encore été exécutée."
            ),
            artifacts=["postman/collections/football-qa.json (à produire)"],
        )


class APIAutomationAgent(BaseAgent):
    name = "api_automation"
    label = "API Automation"

    def run(self, task: Task, mission: Mission, context: dict | None = None) -> AgentResult:
        return AgentResult(
            agent=self.name,
            summary=(
                "Suite pytest à produire : fixtures d'authentification, tests pilotés "
                "par les données, validation JSON Schema, cas négatifs, vérification "
                "des statuts et des règles métier. Les résultats devront être exportés "
                "en JSON et en Allure."
            ),
            artifacts=["tests/api/ (à produire)", "reports/allure-results/ (à produire)"],
        )


class UIAutomationAgent(BaseAgent):
    name = "ui_automation"
    label = "UI Automation"

    def run(self, task: Task, mission: Mission, context: dict | None = None) -> AgentResult:
        return AgentResult(
            agent=self.name,
            summary=(
                "Scénarios Playwright à produire : accueil, championnats, classement, "
                "matchs, détail d'équipe, inscription, connexion, ajout/suppression "
                "d'un favori, persistance après reconnexion, accès refusé aux favoris "
                "sans session. Page Object Model, attentes robustes, captures et traces "
                "en cas d'échec."
            ),
            artifacts=["tests/ui/ (à produire)", "pages/ (à produire)"],
        )


class DevOpsAgent(BaseAgent):
    name = "devops"
    label = "DevOps"

    def run(self, task: Task, mission: Mission, context: dict | None = None) -> AgentResult:
        return AgentResult(
            agent=self.name,
            summary=(
                "Préparation prévue : branche dédiée, commit, pull request, CI passive "
                "sur GitHub Actions. Aucun push direct sur main, aucun merge automatique, "
                "aucun déclenchement de mission par la CI."
            ),
            artifacts=["branche + PR (à préparer)"],
        )


class QAReporterAgent(BaseAgent):
    name = "qa_reporter"
    label = "QA Reporter"

    def __init__(self, settings=None) -> None:
        self.settings = settings or get_settings()

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

        lines = [
            f"# Rapport de mission — {mission.id}",
            "",
            f"**Instruction :** {mission.instruction}",
            "",
            "## Statut",
            "",
            "Mission exécutée par le Manager QA.",
            "",
            "## Tâches",
            "",
        ]
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

        lines.extend(["", "## Prochaine étape", ""])
        if probe or api_auto or ui_auto:
            lines.append(
                "Consolider les preuves et préparer le rapport Allure (phase 7)."
            )
        else:
            lines.append(
                "Exécuter les suites sur la stack de test isolée et joindre les preuves."
            )
        lines.append("")
        return AgentResult(agent=self.name, summary="\n".join(lines), artifacts=[])

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

