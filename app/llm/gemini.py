from __future__ import annotations

import time
from collections.abc import Callable

import httpx

from app.config import Settings, get_settings

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
MAX_PROMPT_CHARS = 30_000

# Le free tier renvoie parfois 429 (quota) ou 5xx passagers. On retente avec un
# backoff exponentiel borné avant de basculer sur le repli déterministe.
RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})
MAX_ATTEMPTS = 3
RETRY_BASE_SECONDS = 1.0
RETRY_MAX_SECONDS = 8.0


class GeminiError(RuntimeError):
    """Erreur d'appel Gemini, sans jamais contenir la clé ni le corps brut."""


class GeminiUnavailableError(GeminiError):
    """Aucune clé Gemini configurée."""


class GeminiClient:
    """Client minimal du free tier Gemini via l'API REST.

    La clé est lue dans `.env` et n'est jamais journalisée ni renvoyée dans les
    messages d'erreur. Aucun SDK payant n'est utilisé.

    Les réponses 429 et 5xx sont retentées (backoff exponentiel borné) ; les
    autres erreurs échouent immédiatement pour ne pas masquer un vrai problème.
    """

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        transport: httpx.BaseTransport | None = None,
        base_url: str = GEMINI_BASE_URL,
        sleep: Callable[[float], None] | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self._transport = transport
        self._base_url = base_url
        self._sleep = sleep or time.sleep

    @property
    def available(self) -> bool:
        return bool(self.settings.gemini_api_key.strip())

    def generate(
        self,
        prompt: str,
        *,
        system_instruction: str | None = None,
    ) -> str:
        key = self.settings.gemini_api_key.strip()
        if not key:
            raise GeminiUnavailableError("GEMINI_API_KEY absente de .env.")

        model = self.settings.llm_model.strip() or "gemini-2.5-flash"
        url = f"{self._base_url}/models/{model}:generateContent"
        payload: dict = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": prompt[:MAX_PROMPT_CHARS]}],
                }
            ],
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 2048,
            },
        }
        if model.startswith("gemini-3"):
            # Réduit la latence et la consommation du free tier.
            payload["generationConfig"]["thinkingConfig"] = {
                "thinkingBudget": 0
            }
        if system_instruction:
            payload["systemInstruction"] = {
                "parts": [{"text": system_instruction}]
            }

        response = self._post_with_retry(url, key, payload)

        try:
            data = response.json()
        except ValueError:
            raise GeminiError("Réponse Gemini invalide : JSON illisible.") from None

        candidates = data.get("candidates") or []
        parts: list[dict] = []
        if candidates:
            content = candidates[0].get("content") or {}
            parts = content.get("parts") or []
        text = "".join(
            str(part.get("text", "")) for part in parts if isinstance(part, dict)
        ).strip()
        if not text:
            raise GeminiError("Réponse Gemini vide.")
        return text

    def _post_with_retry(
        self,
        url: str,
        key: str,
        payload: dict,
    ) -> httpx.Response:
        """Envoie la requête en retentant les statuts transitoires.

        Seuls 429 et 5xx sont retentés. Une erreur réseau ou un 4xx définitif
        échoue immédiatement : on ne masque pas un vrai problème derrière des
        tentatives supplémentaires.
        """
        last_status = 0
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                with httpx.Client(
                    timeout=self.settings.llm_timeout_seconds,
                    transport=self._transport,
                ) as client:
                    response = client.post(
                        url,
                        params={"key": key},
                        json=payload,
                    )
            except httpx.HTTPError as exc:
                raise GeminiError(
                    f"Réseau Gemini indisponible ({type(exc).__name__})."
                ) from None

            if response.status_code == 200:
                return response

            last_status = response.status_code
            if (
                last_status in RETRYABLE_STATUS_CODES
                and attempt < MAX_ATTEMPTS
            ):
                delay = min(
                    RETRY_BASE_SECONDS * (2 ** (attempt - 1)),
                    RETRY_MAX_SECONDS,
                )
                self._sleep(delay)
                continue
            break

        # Le corps brut peut contenir des détails d'authentification : on ne
        # remonte que le code HTTP.
        raise GeminiError(f"Gemini a répondu HTTP {last_status}.")
