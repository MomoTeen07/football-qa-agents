"""Agents 1 à 3 de la phase 5.

- QA Analyst : analyse enrichie par Gemini, avec repli déterministe.
- Test Designer : conception de cas enrichie par Gemini, avec repli.
- API Tester : analyse OpenAPI réelle, collection Postman et sondes API réelles.

Aucun agent ne déclare d'anomalie sans preuve d'exécution reproductible.
"""

from __future__ import annotations

import logging

from app.agents.base import BaseAgent
from app.config import Settings, get_settings
from app.domain.models import AgentResult, Mission, Task
from app.llm.gemini import GeminiClient
from app.tools.api_probe import ApiProbe, UnsafeTargetError, ensure_test_api_url
from app.tools.openapi_postman import (
    analyze_openapi,
    build_postman_collection,
    build_postman_environment,
    fetch_openapi,
    write_postman_assets,
)
from app.tools.workspace import write_mission_json, write_mission_text

logger = logging.getLogger(__name__)

QA_SYSTEM_PROMPT = (
    "Tu es un analyste QA senior pour une application locale de football. "
    "Tu réponds en français, de façon concise et structurée. Tu ne déclares "
    "jamais d'anomalie sans preuve d'exécution reproductible. Tu n'inventes "
    "aucun résultat de test. Tu ne demandes ni ne révèles aucun secret."
)

DESIGN_SYSTEM_PROMPT = (
    "Tu es un test designer ISTQB pour une application locale de football. "
    "Tu réponds en français. Tu produis des cas de test vérifiables, avec "
    "données, résultat attendu et traçabilité. Tu n'inventes aucun résultat "
    "d'exécution et tu ne déclares aucune anomalie sans preuve."
)

API_SYSTEM_PROMPT = (
    "Tu es un testeur API senior. Tu analyses un contrat OpenAPI et des "
    "résultats de sondes réelles. Tu réponds en français. Tu ne déclares une "
    "anomalie que si elle est explicitement présente dans les résultats "
    "fournis, avec méthode et chemin reproductibles. Tu n'inventes rien et tu "
    "ne révèles aucun secret."
)


class QAAnalystAgent(BaseAgent):
    name = "qa_analyst"
    label = "QA Analyst"

    def __init__(
        self,
        settings: Settings | None = None,
        llm: GeminiClient | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.llm = llm or GeminiClient(self.settings)

    def run(self, task: Task, mission: Mission, context: dict | None = None) -> AgentResult:
        baseline = (
            "Stratégie de test proposée : analyser les parcours d'authentification, "
            "de consultation des championnats, de classement, de détail d'équipe et "
            "de gestion des favoris. Risques principaux : isolation des favoris entre "
            "utilisateurs, expiration JWT, cohérence des données football, états "
            "d'erreur de l'interface. Aucun test réel n'a été exécuté."
        )
        if not self.settings.real_agents_enabled:
            return AgentResult(
                agent=self.name,
                summary=baseline,
                artifacts=["plan de test (déterministe)"],
            )

        if not self.llm.available:
            return AgentResult(
                agent=self.name,
                summary=baseline + "\n\nAnalyse Gemini non exécutée : clé absente.",
                artifacts=["plan de test (déterministe)"],
            )

        prompt = (
            f"Instruction de la mission : {mission.instruction}\n\n"
            "Produis une analyse QA pour une API et une UI locales de football. "
            "Structure attendue :\n"
            "1. Périmètre fonctionnel observé.\n"
            "2. Risques principaux et hypothèses.\n"
            "3. Stratégie de test priorisée (API et UI).\n"
            "4. Données de test et comptes de test à utiliser.\n"
            "5. Critères d'arrêt et éléments de preuve attendus.\n\n"
            "Rappel : aucun test n'a encore été exécuté à ce stade ; ne déclare "
            "aucune anomalie et n'invente aucun résultat. "
            f"API de test : {self.settings.test_api_url}. "
            f"UI de test : {self.settings.test_ui_url}."
        )
        try:
            analysis = self.llm.generate(
                prompt, system_instruction=QA_SYSTEM_PROMPT
            )
        except Exception as exc:
            logger.warning(
                "Analyse Gemini indisponible (%s).", type(exc).__name__
            )
            return AgentResult(
                agent=self.name,
                summary=(
                    baseline
                    + f"\n\nAnalyse Gemini indisponible ({type(exc).__name__})."
                ),
                artifacts=["plan de test (déterministe)"],
            )

        path = write_mission_text(
            self.settings,
            mission.id,
            "analysis/qa-analyst-gemini.md",
            f"# Analyse QA — mission {mission.id}\n\n"
            f"**Instruction :** {mission.instruction}\n\n{analysis}\n",
        )
        return AgentResult(
            agent=self.name,
            summary=baseline + "\n\n## Analyse Gemini\n\n" + analysis,
            artifacts=[str(path)],
            evidence=[str(path)],
        )


class TestDesignerAgent(BaseAgent):
    name = "test_designer"
    label = "Test Designer"

    def __init__(
        self,
        settings: Settings | None = None,
        llm: GeminiClient | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.llm = llm or GeminiClient(self.settings)

    def run(self, task: Task, mission: Mission, context: dict | None = None) -> AgentResult:
        baseline = (
            "Cas de test proposés selon les techniques ISTQB : partitionnement "
            "d'équivalence sur les champs email/mot de passe, valeurs limites sur "
            "les identifiants, transitions d'état pour la session, tests négatifs "
            "sur les favoris en double et les accès non authentifiés. "
            "Traçabilité prévue : exigence → cas de test → exécution → anomalie."
        )
        if not self.settings.real_agents_enabled:
            return AgentResult(
                agent=self.name,
                summary=baseline,
                artifacts=["matrice de traçabilité (déterministe)"],
            )

        if not self.llm.available:
            return AgentResult(
                agent=self.name,
                summary=baseline + "\n\nConception Gemini non exécutée : clé absente.",
                artifacts=["matrice de traçabilité (déterministe)"],
            )

        prompt = (
            f"Instruction de la mission : {mission.instruction}\n\n"
            "Conçois une matrice de cas de test pour l'API et l'UI de football. "
            "Colonnes : ID, exigence, technique ISTQB, préconditions, données, "
            "étapes, résultat attendu, priorité. Couvre au minimum : santé, "
            "championnats, classement, matchs, détail d'équipe, inscription, "
            "connexion, jeton absent/invalide, favoris (liste, ajout, doublon, "
            "suppression, isolation entre utilisateurs).\n\n"
            "Ne déclare aucune anomalie et n'invente aucun résultat d'exécution."
        )
        try:
            design = self.llm.generate(
                prompt, system_instruction=DESIGN_SYSTEM_PROMPT
            )
        except Exception as exc:
            logger.warning(
                "Conception Gemini indisponible (%s).", type(exc).__name__
            )
            return AgentResult(
                agent=self.name,
                summary=(
                    baseline
                    + f"\n\nConception Gemini indisponible ({type(exc).__name__})."
                ),
                artifacts=["matrice de traçabilité (déterministe)"],
            )

        path = write_mission_text(
            self.settings,
            mission.id,
            "design/test-designer-gemini.md",
            f"# Conception des tests — mission {mission.id}\n\n"
            f"**Instruction :** {mission.instruction}\n\n{design}\n",
        )
        return AgentResult(
            agent=self.name,
            summary=baseline + "\n\n## Matrice proposée par Gemini\n\n" + design,
            artifacts=[str(path)],
            evidence=[str(path)],
        )


class APITesterAgent(BaseAgent):
    name = "api_tester"
    label = "API Tester"

    def __init__(
        self,
        settings: Settings | None = None,
        llm: GeminiClient | None = None,
        probe: ApiProbe | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.llm = llm or GeminiClient(self.settings)
        self.probe = probe or ApiProbe(self.settings)

    def run(self, task: Task, mission: Mission, context: dict | None = None) -> AgentResult:
        baseline = (
            "Collection Postman à produire : santé, leagues, standings, matches, "
            "team, register, login, users/me, favorites (GET/POST/DELETE). "
            "Vérifications : méthodes HTTP, codes 200/201/204/400/401/404/409/422, "
            "JWT Bearer, isolation entre utilisateurs, schémas JSON. "
            "Aucune requête n'a encore été exécutée."
        )
        if not self.settings.real_agents_enabled:
            return AgentResult(
                agent=self.name,
                summary=baseline,
                artifacts=["postman/collections/football-qa.json (déterministe)"],
            )

        try:
            ensure_test_api_url(self.settings.test_api_url)
        except UnsafeTargetError as exc:
            return AgentResult(
                agent=self.name,
                summary=f"Analyse API non exécutée : {exc}",
                artifacts=[],
            )

        try:
            spec = fetch_openapi(
                self.settings.test_api_url,
                timeout=self.settings.api_probe_timeout_seconds,
            )
        except Exception as exc:
            return AgentResult(
                agent=self.name,
                summary=(
                    "Analyse OpenAPI impossible : "
                    f"{type(exc).__name__}. Aucun test réel exécuté, aucune "
                    "anomalie déclarée."
                ),
                artifacts=[],
            )

        openapi_path = write_mission_json(
            self.settings,
            mission.id,
            "api/openapi.json",
            spec,
        )
        analysis = analyze_openapi(spec)
        analysis_path = write_mission_json(
            self.settings,
            mission.id,
            "api/openapi-analysis.json",
            analysis,
        )

        collection = build_postman_collection(
            spec, self.settings.test_api_url.rstrip("/")
        )
        environment = build_postman_environment(
            self.settings.test_api_url.rstrip("/"),
            test_user_email=self.settings.test_user1_email,
            test_user_password=self.settings.test_user1_password,
        )
        collection_path, environment_path = write_postman_assets(
            self.settings, collection, environment
        )

        try:
            outcome = self.probe.run(mission.id)
        except UnsafeTargetError as exc:
            return AgentResult(
                agent=self.name,
                summary=f"Sondes API non exécutées : {exc}",
                artifacts=[str(collection_path), str(environment_path)],
                evidence=[str(openapi_path), str(analysis_path)],
            )
        except Exception as exc:
            logger.warning(
                "Sondes API indisponibles (%s).", type(exc).__name__
            )
            return AgentResult(
                agent=self.name,
                summary=(
                    "Sondes API non exécutées : "
                    f"{type(exc).__name__}. Aucune anomalie déclarée."
                ),
                artifacts=[str(collection_path), str(environment_path)],
                evidence=[str(openapi_path), str(analysis_path)],
            )

        llm_text = self._llm_analysis(analysis, outcome, mission)
        llm_path = None
        if llm_text is not None:
            llm_path = write_mission_text(
                self.settings,
                mission.id,
                "api/api-tester-gemini.md",
                f"# Analyse API — mission {mission.id}\n\n{llm_text}\n",
            )

        summary_lines = [
            f"Analyse OpenAPI réelle : {analysis['operation_count']} opérations, "
            f"{len(analysis['schemas'])} schémas.",
            f"Collection Postman générée : {collection_path}",
            f"Environnement Postman : {environment_path}",
            outcome.summary,
        ]
        if outcome.anomalies:
            summary_lines.append(
                "Anomalies reproductibles : "
                + ", ".join(
                    f"{item['method']} {item['path']}"
                    for item in outcome.anomalies
                )
            )
        if llm_text:
            summary_lines.append("\n## Analyse Gemini\n\n" + llm_text)

        evidence = [
            str(openapi_path),
            str(analysis_path),
            str(collection_path),
            str(environment_path),
            *outcome.evidence_paths,
        ]
        if llm_path is not None:
            evidence.append(str(llm_path))

        return AgentResult(
            agent=self.name,
            summary="\n".join(summary_lines),
            artifacts=[str(collection_path), str(environment_path)],
            evidence=evidence,
        )

    def _llm_analysis(self, analysis: dict, outcome, mission: Mission) -> str | None:
        if not self.llm.available:
            return None
        checks = [
            {
                "name": check.name,
                "method": check.method,
                "path": check.path,
                "expected": check.expected,
                "actual": check.actual,
                "passed": check.passed,
                "skipped": check.skipped,
            }
            for check in outcome.checks
        ]
        prompt = (
            f"Instruction de la mission : {mission.instruction}\n\n"
            f"OpenAPI analysé : {analysis['operation_count']} opérations.\n"
            f"Opérations : {analysis['operations']}\n\n"
            f"Résultats réels des sondes : {checks}\n\n"
            "Produis une synthèse en français : couverture actuelle, risques "
            "résiduels, tests prioritaires pour la phase suivante. Tu peux "
            "reprendre uniquement les anomalies explicitement présentes dans "
            "les résultats. N'invente aucune anomalie et ne révèle aucun secret."
        )
        try:
            return self.llm.generate(
                prompt, system_instruction=API_SYSTEM_PROMPT
            )
        except Exception as exc:
            logger.warning(
                "Synthèse Gemini indisponible (%s).", type(exc).__name__
            )
            return None
