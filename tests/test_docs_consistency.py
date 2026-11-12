"""Cohérence documentaire : version, nombre de tests et commandes clés."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


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
    readme = first_test_count(read("README.md"))
    context = first_test_count(read("PROJECT_CONTEXT.md"))
    # Seule la section de la version courante compte : les jalons antérieurs
    # conservent leurs propres chiffres historiques.
    sections = re.split(r"^## \[", read("CHANGELOG.md"), flags=re.MULTILINE)
    changelog = last_test_count(sections[1])

    assert readme == context == changelog, (
        "le nombre de tests annoncé diverge entre README "
        f"({readme}), PROJECT_CONTEXT ({context}) et CHANGELOG ({changelog})"
    )


def test_docs_document_the_doctor_command_and_phase_status() -> None:
    readme = read("README.md")
    context = read("PROJECT_CONTEXT.md")

    assert "app.cli doctor" in readme
    assert "doctor" in context
    assert "0.9.0" in readme
    assert "phase 9" in readme.lower() and "J3" in readme
    assert "phase 9" in context.lower() and "J3" in context
