"""Catalogue des huit personnages du bureau virtuel.

Les identifiants correspondent exactement aux agents du planificateur
(`app/orchestrator/planner.py`) et à l'agent DevOps. Le Manager QA est le
coordinateur central ; il ne porte pas de tâche dans le graphe.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Department:
    id: str
    label: str
    color: str


@dataclass(frozen=True)
class AgentProfile:
    id: str
    name: str
    role: str
    department: str
    color: str
    sprite: dict
    summary: str


DEPARTMENTS: tuple[Department, ...] = (
    Department("direction", "Direction", "#8b5cf6"),
    Department("analysis", "Analyse & Conception", "#3b82f6"),
    Department("api", "Tests API", "#22c55e"),
    Department("ui", "Automatisation UI", "#ec4899"),
    Department("infra", "Infrastructure", "#f59e0b"),
    Department("reporting", "Reporting", "#06b6d4"),
)

_DEPARTMENT_INDEX = {department.id: department for department in DEPARTMENTS}


def _sprite(**values: object) -> dict:
    return {key: str(value) for key, value in values.items()}


AGENTS: tuple[AgentProfile, ...] = (
    AgentProfile(
        id="manager",
        name="Max",
        role="Manager QA",
        department="direction",
        color="#8b5cf6",
        sprite=_sprite(
            skin="#e8b48c",
            hair="short",
            hair_color="#26324a",
            shirt="#2b3d63",
            pants="#1c2740",
            accessory="tie",
        ),
        summary="Coordonne la mission, distribue les tâches et arbitre les validations.",
    ),
    AgentProfile(
        id="qa_analyst",
        name="Camille",
        role="QA Analyst",
        department="analysis",
        color="#3b82f6",
        sprite=_sprite(
            skin="#f0c19b",
            hair="curly",
            hair_color="#3b2a23",
            shirt="#2563eb",
            pants="#24324f",
            accessory="glasses",
        ),
        summary="Analyse l'application, identifie les risques et définit la stratégie de test.",
    ),
    AgentProfile(
        id="test_designer",
        name="Nora",
        role="Test Designer",
        department="analysis",
        color="#60a5fa",
        sprite=_sprite(
            skin="#e8b48c",
            hair="long",
            hair_color="#7c4a2d",
            shirt="#3b82f6",
            pants="#24324f",
            accessory="none",
        ),
        summary="Conçoit les cas de test, la traçabilité et les jeux de données.",
    ),
    AgentProfile(
        id="api_tester",
        name="Yanis",
        role="API Tester",
        department="api",
        color="#22c55e",
        sprite=_sprite(
            skin="#c98b62",
            hair="short",
            hair_color="#1f2937",
            shirt="#16a34a",
            pants="#20304a",
            accessory="headset",
        ),
        summary="Explore l'API REST, prépare Postman et exécute les sondes HTTP réelles.",
    ),
    AgentProfile(
        id="api_automation",
        name="Léo",
        role="API Automation",
        department="api",
        color="#4ade80",
        sprite=_sprite(
            skin="#f0c19b",
            hair="curly",
            hair_color="#4b2e20",
            shirt="#22c55e",
            pants="#20304a",
            accessory="glasses",
        ),
        summary="Génère et exécute la suite pytest d'automatisation API.",
    ),
    AgentProfile(
        id="ui_automation",
        name="Inès",
        role="UI Automation",
        department="ui",
        color="#ec4899",
        sprite=_sprite(
            skin="#e8b48c",
            hair="ponytail",
            hair_color="#a34b2a",
            shirt="#ec4899",
            pants="#2b2140",
            accessory="headset",
        ),
        summary="Génère et exécute les scénarios Playwright sur le frontend de test.",
    ),
    AgentProfile(
        id="devops",
        name="Sam",
        role="DevOps",
        department="infra",
        color="#f59e0b",
        sprite=_sprite(
            skin="#c98b62",
            hair="cap",
            hair_color="#1f2937",
            shirt="#f59e0b",
            pants="#26324a",
            accessory="beard",
        ),
        summary="Prépare la branche, la pull request et la publication opt-in.",
    ),
    AgentProfile(
        id="qa_reporter",
        name="Aya",
        role="QA Reporter",
        department="reporting",
        color="#06b6d4",
        sprite=_sprite(
            skin="#e8b48c",
            hair="long",
            hair_color="#1f2937",
            shirt="#06b6d4",
            pants="#20304a",
            accessory="glasses",
        ),
        summary="Consolide les preuves, produit le rapport et les résultats Allure 2.",
    ),
)

_AGENT_INDEX = {agent.id: agent for agent in AGENTS}
_AGENT_ORDER = {agent.id: index for index, agent in enumerate(AGENTS)}


def agent_catalog() -> list[dict]:
    """Retourne le catalogue sérialisable, dans l'ordre d'affichage."""

    catalog: list[dict] = []
    for agent in AGENTS:
        department = _DEPARTMENT_INDEX[agent.department]
        item = asdict(agent)
        item["department_label"] = department.label
        item["department_color"] = department.color
        catalog.append(item)
    return catalog


def department_catalog() -> list[dict]:
    return [asdict(department) for department in DEPARTMENTS]


def agent_order(agent_id: str) -> int:
    return _AGENT_ORDER.get(agent_id, len(_AGENT_ORDER))


def profile(agent_id: str) -> AgentProfile | None:
    return _AGENT_INDEX.get(agent_id)
