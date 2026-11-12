"""Barrière de validation et de rédaction (phase 9).

Un seul module décide de ce qui est un identifiant acceptable, de ce qui reste
confiné dans le workspace et de ce qui doit être expurgé avant sérialisation.
Les appelants (bureau, CLI, scripts, outils, agents) s'appuient dessus pour
éviter les chemins construits avec une entrée non fiable et les fuites de
secrets connus.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from app.tools.redaction import redact_text

MISSION_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")

# Caractères interdits dans une référence Git (approximation des règles
# `git check-ref-format` utiles ici). On reste volontairement strict.
_GIT_REF_FORBIDDEN = set(" ~^:?*[\\\t\n\r")


def validate_mission_id(value: str) -> str:
    """Valide un identifiant de mission, ou lève `ValueError`.

    Seuls les identifiants ``[A-Za-z0-9_-]{1,64}`` sont acceptés : ni
    traversée de chemin, ni séparateur, ni identifiant vide.
    """

    if not isinstance(value, str) or not MISSION_ID_PATTERN.fullmatch(value):
        raise ValueError("Identifiant de mission invalide.")
    return value


def validate_git_ref(value: str, *, label: str = "référence Git") -> str:
    """Valide une référence Git (remote, branche) utilisée dans une commande.

    Refuse le vide, un nom commençant par ``-`` (option déguisée), les espaces,
    ``..`` et les caractères réservés par Git.
    """

    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} invalide.")
    if value.startswith("-") or value.startswith("/") or value.endswith("/"):
        raise ValueError(f"{label} invalide.")
    if value.endswith(".") or value.endswith(".lock") or "//" in value:
        raise ValueError(f"{label} invalide.")
    if ".." in value or "@{" in value:
        raise ValueError(f"{label} invalide.")
    if any(char in _GIT_REF_FORBIDDEN for char in value):
        raise ValueError(f"{label} invalide.")
    return value


def ensure_within(base: Path, candidate: Path | str) -> Path:
    """Résout `candidate` et vérifie qu'il reste sous `base`.

    Lève `ValueError` si le chemin sort du dossier autorisé, y compris via une
    traversée relative (`../`) ou un lien symbolique.
    """

    base_path = Path(base).resolve()
    candidate_path = Path(candidate)
    target = candidate_path if candidate_path.is_absolute() else base_path / candidate_path
    resolved = target.resolve()
    if not resolved.is_relative_to(base_path):
        raise ValueError("Chemin hors du dossier autorisé.")
    return resolved


def redact_structure(value: Any, secrets: tuple[str, ...] = ()) -> Any:
    """Expurge récursivement les secrets connus d'une structure sérialisable."""

    if isinstance(value, str):
        return redact_text(value, secrets)
    if isinstance(value, dict):
        return {
            redact_text(str(key), secrets): redact_structure(item, secrets)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [redact_structure(item, secrets) for item in value]
    return value


def known_secrets(settings: Any) -> tuple[str, ...]:
    """Liste les secrets configurés, sans jamais les exposer ailleurs."""

    candidates = (
        getattr(settings, "gemini_api_key", ""),
        getattr(settings, "groq_api_key", ""),
        getattr(settings, "mistral_api_key", ""),
        getattr(settings, "telegram_bot_token", ""),
        getattr(settings, "test_user1_password", ""),
        getattr(settings, "test_user2_password", ""),
    )
    unique: list[str] = []
    for candidate in candidates:
        if isinstance(candidate, str) and candidate and candidate not in unique:
            unique.append(candidate)
    return tuple(unique)
