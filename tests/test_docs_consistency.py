"""Cohérence documentaire : version, nombre de tests et commandes clés.

Le README est la page d'accueil ; les détails opérationnels (nombre de tests,
commande `doctor`, statut de phase) vivent dans `docs/GUIDE.md`. C'est ce
document qui fait foi ici.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUIDE = "docs/GUIDE.md"


def read(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")


def first_test_count(text: str) -> int:
    match = re.search(r"(\d+) passed", text)
    assert match, "aucun nombre de tests « N passed » trouvé"
    return int(match.group(1))


def last_test_count(text: str) -> int:
    matches = re.findall(r"(\d+) passed", text)
    assert matches, "aucun nombre de tests « N passed » trouvé"
    return int(matches[-1])


def test_pyproject_version_matches_the_changelog() -> None:
    version = tomllib.loads(read("pyproject.toml"))["project"]["version"]
    versions = re.findall(
        r"^## \[(\d+\.\d+\.\d+)\]", read("CHANGELOG.md"), re.MULTILINE
    )

    assert versions, "aucune version datée dans CHANGELOG.md"
    assert versions[0] == version, (
        f"pyproject.toml ({version}) diverge de la première version du "
        f"CHANGELOG ({versions[0]})"
    )


def test_documented_test_count_is_consistent() -> None:
    guide = first_test_count(read(GUIDE))
    context = first_test_count(read("PROJECT_CONTEXT.md"))
    # Seule la section de la version courante compte : les jalons antérieurs
    # conservent leurs propres chiffres historiques.
    sections = re.split(r"^## \[", read("CHANGELOG.md"), flags=re.MULTILINE)
    changelog = last_test_count(sections[1])

    assert guide == context == changelog, (
        f"le nombre de tests annoncé diverge entre {GUIDE} "
        f"({guide}), PROJECT_CONTEXT ({context}) et CHANGELOG ({changelog})"
    )


def test_docs_document_the_doctor_command_and_phase_status() -> None:
    guide = read(GUIDE)
    context = read("PROJECT_CONTEXT.md")

    assert "app.cli doctor" in guide
    assert "doctor" in context
    assert "0.9.0" in guide
    assert "phase 9" in guide.lower() and "J3" in guide
    assert "phase 9" in context.lower() and "J3" in context
