from __future__ import annotations

API_KEYWORDS = (
    "api",
    "endpoint",
    "rest",
    "postman",
    "contrat",
    "http",
)

UI_KEYWORDS = (
    "ui",
    "interface",
    "playwright",
    "fonctionnel",
    "parcours",
    "écran",
    "ecran",
    "navigateur",
)

FULL_KEYWORDS = (
    "complet",
    "complète",
    "complete",
    "campagne",
    "tout",
    "global",
    "non-régression",
    "non regression",
    "régression",
    "regression",
    "fonctionne",
)

DEVOPS_KEYWORDS = (
    "git",
    "github",
    " ci ",
    "ci/",
    "pipeline",
    "branche",
    "pull request",
    " pr ",
)

INTRUSIVE_KEYWORDS = (
    "intrusif",
    "intrusive",
    "brute force",
    "fuzz",
    "stress",
    "charge",
    "déni de service",
    "deni de service",
    "scan de ports",
    "pentest",
)

DESTRUCTIVE_KEYWORDS = (
    "supprimer",
    "supprime",
    "effacer",
    "reset",
    "drop",
    "truncate",
    "destruct",
    "vider",
)

REAL_APP_KEYWORDS = (
    "application réelle",
    "application reelle",
    "base réelle",
    "base reelle",
    "production",
    "prod",
)

EXTERNAL_KEYWORDS = (
    "jira",
    "xray",
    "squash",
    "créer une anomalie",
    "creer une anomalie",
    "publier",
)


def mission_requires_approval(instruction: str) -> tuple[bool, str | None]:
    text = f" {instruction.lower()} "
    groups = [
        ("test de sécurité intrusif", INTRUSIVE_KEYWORDS),
        ("action destructrice sur les données", DESTRUCTIVE_KEYWORDS),
        ("action sur l'application réelle", REAL_APP_KEYWORDS),
        ("publication dans un outil externe", EXTERNAL_KEYWORDS),
        ("publication d'une branche et d'une pull request", DEVOPS_KEYWORDS),
    ]
    for reason, keywords in groups:
        if any(keyword in text for keyword in keywords):
            return True, reason
    return False, None


def build_plan(instruction: str) -> list[dict]:
    text = f" {instruction.lower()} "
    full = any(keyword in text for keyword in FULL_KEYWORDS)
    wants_api = full or any(keyword in text for keyword in API_KEYWORDS)
    wants_ui = full or any(keyword in text for keyword in UI_KEYWORDS)
    wants_devops = any(keyword in text for keyword in DEVOPS_KEYWORDS)

    plan: list[dict] = [
        {
            "key": "analysis",
            "agent": "qa_analyst",
            "title": "Analyser l'application et définir la stratégie de test",
            "depends_on": [],
        },
        {
            "key": "design",
            "agent": "test_designer",
            "title": "Concevoir les cas de test et la traçabilité",
            "depends_on": ["analysis"],
        },
    ]

    if wants_api:
        plan.append(
            {
                "key": "api_design",
                "agent": "api_tester",
                "title": "Analyser l'API REST et préparer la collection Postman",
                "depends_on": ["design"],
            }
        )
        plan.append(
            {
                "key": "api_automation",
                "agent": "api_automation",
                "title": "Préparer la suite pytest d'automatisation API",
                "depends_on": ["api_design"],
            }
        )

    if wants_ui:
        plan.append(
            {
                "key": "ui_automation",
                "agent": "ui_automation",
                "title": "Préparer les scénarios Playwright et le Page Object Model",
                "depends_on": ["design"],
            }
        )

    if wants_devops:
        plan.append(
            {
                "key": "devops",
                "agent": "devops",
                "title": "Préparer la branche, la PR et la CI passive",
                "depends_on": ["design"],
            }
        )

    report_dependencies = [item["key"] for item in plan]
    plan.append(
        {
            "key": "report",
            "agent": "qa_reporter",
            "title": "Consolider les résultats et produire le rapport",
            "depends_on": report_dependencies,
        }
    )
    return plan
