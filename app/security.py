"""Barrière unique de validation et de rédaction (phase 9, WP1).

Tous les identifiants de mission, chemins d'écriture et références Git passent
par ce module. La rédaction s'applique aux structures sérialisées (dict, list,
str) avant toute écriture de preuve ou réponse HTTP.

Aucune valeur secrète réelle n'est stockée ici : seules les valeurs lues dans
la configuration locale sont utilisées, à la demande, et jamais journalisées.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from app.config import Settings, get_settings
from app.tools.redaction import redact_text

MISSION_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
GIT_REF_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,127}$")
REDACTED = "[redacted]"


def validate_mission_id(value: str | None) -> str:
    """Valide un identifiant de mission et le retourne inchangé.

    Refuse le vide, les séparateurs de chemin, les espaces et tout caractère
    hors ``[A-Za-z0-9_-]`` (1 à 64 caractères).
    """

    if not isinstance(value, str) or not MISSION_ID_PATTERN.fullmatch(value):
        raise ValueError(
            "Identifiant de mission invalide : lettres, chiffres, _ et - "
            "uniquement (1 à 64 caractères)."
        )
    return value


def ensure_within(base: Path, candidate: Path) -> Path:
    """Retourne ``candidate`` résolu s'il reste dans ``base``, sinon lève.

    La comparaison est faite sur les chemins résolus, ce qui couvre les
    traversées ``..``, les chemins absolus et les liens symboliques résolus.
    """

    base_resolved = Path(base).resolve()
    candidate_resolved = Path(candidate).resolve()
    if (
        candidate_resolved != base_resolved
        and not candidate_resolved.is_relative_to(base_resolved)
    ):
        raise ValueError(f"Chemin refusé hors de {base_resolved}.")
    return candidate_resolved


def validate_git_ref(value: str | None) -> str:
    """Valide une référence Git simple (remote, branche de base).

    Refuse les valeurs vides, commençant par ``-``, contenant un espace, une
    séquence ``..`` ou un caractère hors ``[A-Za-z0-9._/-]``.
    """

    if (
        not isinstance(value, str)
        or not GIT_REF_PATTERN.fullmatch(value)
        or ".." in value
        or value.endswith(".")
        or value.endswith("/")
    ):
        raise ValueError(
            "Référence Git invalide : ni espace, ni '..', ni valeur commençant "
            "par '-' (lettres, chiffres, '.', '_', '/' et '-' autorisés)."
        )
    return value


def redact_structure(value: Any, secrets: tuple[str, ...] = ()) -> Any:
    """Expurge récursivement les secrets connus d'une structure sérialisable."""

    if isinstance(value, str):
        return redact_text(value, secrets)
    if isinstance(value, dict):
        return {
            key: redact_structure(item, secrets) for key, item in value.items()
        }
    if isinstance(value, (list, tuple, set)):
        return [redact_structure(item, secrets) for item in value]
    if isinstance(value, Path):
        return redact_text(str(value), secrets)
    return value


def known_secrets(settings: Settings | None = None) -> tuple[str, ...]:
    """Liste les secrets locaux connus, sans jamais les exposer.

    Les valeurs vides et les doublons sont ignorés. Le résultat ne doit
    jamais être journalisé ni sérialisé.
    """

    current = settings or get_settings()
    values = (
        current.gemini_api_key,
        current.groq_api_key,
        current.mistral_api_key,
        current.telegram_bot_token,
        current.test_user1_password,
        current.test_user2_password,
    )
    return tuple(dict.fromkeys(item for item in values if item))
