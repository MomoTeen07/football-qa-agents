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
        probe = self._probe_results(mission.id)
        anomalies = probe.get("anomalies", []) if probe else []
        checks = probe.get("checks", []) if probe else []

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

        if probe is None:
            lines.extend(
                [
                    "Les agents ont produit des plans et des livrables à exécuter. "
                    "Aucun test réel n'a été exécuté durant cette mission.",
                    "",
                ]
            )
        else:
            executed = [check for check in checks if not check.get("skipped")]
            passed = [check for check in executed if check.get("passed")]
            status = probe.get("status", "inconnu")
            lines.extend(
                [
                    "Des sondes API réelles ont été exécutées sur la stack de test.",
                    "",
                    f"- Statut des sondes : `{status}`",
                    f"- Vérifications exécutées : {len(executed)}",
                    f"- Réussies : {len(passed)}",
                    f"- Anomalies : {len(anomalies)}",
                    f"- Preuves : `workspace/missions/{mission.id}/api/`",
                    "",
                ]
            )

        lines.extend(["## Anomalies", ""])
        if anomalies:
            for index, anomaly in enumerate(anomalies, start=1):
                lines.extend(
                    [
                        f"### {index}. {anomaly.get('check', 'Anomalie')}",
                        "",
                        f"- Reproduction : `{anomaly.get('reproduction', '')}`",
                        f"- Attendu : {anomaly.get('expected', '')}",
                        f"- Obtenu : {anomaly.get('actual', '')}",
                        "- Preuve : "
                        f"`workspace/missions/{mission.id}/api/probe-results.json`",
                        "",
                    ]
                )
        elif probe is not None and probe.get("status") == "completed":
            lines.extend(
                [
                    "Aucune anomalie déclarée : les sondes réelles n'ont révélé "
                    "aucun écart avec les résultats attendus.",
                    "",
                ]
            )
        elif probe is not None:
            lines.extend(
                [
                    "Aucune anomalie déclarée : les sondes n'ont pas pu être "
                    "exécutées.",
                    "",
                ]
            )
        else:
            lines.extend(
                [
                    "Aucune anomalie déclarée : aucune exécution réelle n'a eu lieu.",
                    "",
                ]
            )

        lines.extend(
            [
                "## Prochaine étape",
                "",
                "Exécuter les suites sur la stack de test isolée et joindre les preuves.",
                "",
            ]
        )
        return AgentResult(agent=self.name, summary="\n".join(lines), artifacts=[])

    def _probe_results(self, mission_id: str) -> dict | None:
        path = (
            Path(self.settings.workspace_dir)
            / "missions"
            / mission_id
            / "api"
            / "probe-results.json"
        )
        if not path.is_file():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
