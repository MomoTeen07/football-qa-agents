from __future__ import annotations

import re

BEARER_PATTERN = re.compile(r"(Bearer\s+)[A-Za-z0-9._~+/=-]+", re.IGNORECASE)
SECRET_JSON_PATTERN = re.compile(
    r'("(?:access_token|token|password|secret|api_key)"\s*[:=]\s*")[^"]*(")',
    re.IGNORECASE,
)


def redact_text(text: str, secrets: tuple[str, ...] = ()) -> str:
    """Expurge les secrets connus et les motifs de jeton d'un texte libre."""
    if not text:
        return ""
    result = text
    for secret in secrets:
        if secret:
            result = result.replace(secret, "[redacted]")
    result = BEARER_PATTERN.sub(r"\1[redacted]", result)
    result = SECRET_JSON_PATTERN.sub(r"\1[redacted]\2", result)
    return result
