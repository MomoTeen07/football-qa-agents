from __future__ import annotations

DENIED_MESSAGE = "Accès refusé."


def is_allowed(
    user_id: int | None,
    allowed_user_id: str | int | None,
) -> bool:
    """Vérifie l'allowlist Telegram de façon stricte.

    Un identifiant absent, vide ou différent est refusé. Aucun détail sur la
    configuration n'est renvoyé à l'appelant ni à l'utilisateur refusé.
    """
    if user_id is None or allowed_user_id is None:
        return False

    expected = str(allowed_user_id).strip()
    if not expected:
        return False

    return str(user_id).strip() == expected
