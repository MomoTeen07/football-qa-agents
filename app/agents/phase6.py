"""Agents 4 et 5 de la phase 6.

- API Automation : génère et exécute une suite pytest réelle sur la stack de
  test, à partir de la collection Postman et des preuves de la phase 5.
- UI Automation : génère et exécute des scénarios Playwright réels sur le
  frontend de test isolé.

Aucun agent ne déclare d'anomalie sans échec réel reproductible. Une cible
indisponible produit un statut bloqué, sans anomalie applicative.
"""

from __future__ import annotations

import logging

from app.agents.base import BaseAgent
from app.config import Settings, get_settings
from app.domain.models import AgentResult, Mission, Task
from app.tools.api_probe import UnsafeTargetError
from app.tools.api_suite import ApiSuite
from app.tools.ui_suite import UiSuite, UnsafeUiTargetError

logger = logging.getLogger(__name__)

API_FALLBACK = (
    "Suite pytest à produire : fixtures d'authentification, tests pilotés "
    "par les données, validation JSON, cas négatifs, vérification des statuts "
    "et des règles métier. À partir de la collection Postman et des preuves "
    "de la phase 5. Aucun test réel n'a encore été exécuté."
)

UI_FALLBACK = (
    "Scénarios Playwright à produire : accueil, championnats, classement, "
    "matchs, détail d'équipe, inscription, connexion, ajout/suppression d'un "
    "favori, accès refusé aux favoris sans session. Page Object Model, attentes "
    "robustes, captures en cas d'échec. Aucun scénario réel n'a encore été exécuté."
)


class APIAutomationAgent(BaseAgent):
    name = "api_automation"
    label = "API Automation"

    def __init__(
        self,
        settings: Settings | None = None,
        suite: ApiSuite | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.suite = suite or ApiSuite(self.settings)

    def run(self, task: Task, mission: Mission, context: dict | None = None) -> AgentResult:
        if not self.settings.real_agents_enabled:
            return AgentResult(
                agent=self.name,
                summary=API_FALLBACK,
                artifacts=["tests/api/ (déterministe)"],
            )

        try:
            outcome = self.suite.run(mission.id)
        except UnsafeTargetError as exc:
            return AgentResult(
                agent=self.name,
                summary=f"Automatisation API non exécutée : {exc}",
                artifacts=[],
            )
        except Exception as exc:  # pragma: no cover - garde-fou d'exécution
            logger.warning(
                "Automatisation API indisponible (%s).", type(exc).__name__
            )
            return AgentResult(
                agent=self.name,
                summary=(
                    "Automatisation API non exécutée : "
                    f"{type(exc).__name__}. Aucune anomalie déclarée."
                ),
                artifacts=[],
            )

        lines = [
            outcome.summary,
            "",
            "La suite pytest a été générée dans le workspace de la mission et "
            "exécutée réellement par pytest.",
        ]
        if outcome.sources:
            sources = outcome.sources
            lines.extend(
                [
                    "",
                    f"- Requêtes Postman analysées : {sources.get('postman_requests', 0)}",
                    f"- Requêtes Postman rejouées en pytest : "
                    f"{sources.get('postman_safe_cases', 0)}",
                    f"- Sondes phase 5 réutilisées : {sources.get('probe_checks', 0)}",
                ]
            )
        if outcome.anomalies:
            lines.append("")
            lines.append("Anomalies reproductibles :")
            for anomaly in outcome.anomalies:
                lines.append(
                    f"- {anomaly.get('check')} — `{anomaly.get('reproduction')}`"
                )

        artifacts = outcome.evidence_paths[:2]
        return AgentResult(
            agent=self.name,
            summary="\n".join(lines),
            artifacts=artifacts,
            evidence=outcome.evidence_paths,
            anomalies=outcome.anomalies,
        )


class UIAutomationAgent(BaseAgent):
    name = "ui_automation"
    label = "UI Automation"

    def __init__(
        self,
        settings: Settings | None = None,
        suite: UiSuite | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.suite = suite or UiSuite(self.settings)

    def run(self, task: Task, mission: Mission, context: dict | None = None) -> AgentResult:
        if not self.settings.real_agents_enabled:
            return AgentResult(
                agent=self.name,
                summary=UI_FALLBACK,
                artifacts=["tests/ui/ (déterministe)"],
            )

        try:
            outcome = self.suite.run(mission.id)
        except (UnsafeUiTargetError, UnsafeTargetError) as exc:
            return AgentResult(
                agent=self.name,
                summary=f"Automatisation UI non exécutée : {exc}",
                artifacts=[],
            )
        except Exception as exc:  # pragma: no cover - garde-fou d'exécution
            logger.warning(
                "Automatisation UI indisponible (%s).", type(exc).__name__
            )
            return AgentResult(
                agent=self.name,
                summary=(
                    "Automatisation UI non exécutée : "
                    f"{type(exc).__name__}. Aucune anomalie déclarée."
                ),
                artifacts=[],
            )

        lines = [
            outcome.summary,
            "",
            "Les scénarios Playwright ont été générés dans le workspace de la "
            "mission et exécutés réellement dans Chromium.",
        ]
        if outcome.anomalies:
            lines.append("")
            lines.append("Anomalies reproductibles :")
            for anomaly in outcome.anomalies:
                lines.append(
                    f"- {anomaly.get('check')} — `{anomaly.get('reproduction')}`"
                )

        artifacts = outcome.evidence_paths[:2]
        return AgentResult(
            agent=self.name,
            summary="\n".join(lines),
            artifacts=artifacts,
            evidence=outcome.evidence_paths,
            anomalies=outcome.anomalies,
        )
