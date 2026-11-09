from __future__ import annotations

import httpx

from app.config import Settings, get_settings

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
MAX_PROMPT_CHARS = 30_000


class GeminiError(RuntimeError):
    """Erreur d'appel Gemini, sans jamais contenir la clé ni le corps brut."""


class GeminiUnavailableError(GeminiError):
    """Aucune clé Gemini configurée."""


class GeminiClient:
    """Client minimal du free tier Gemini via l'API REST.

    La clé est lue dans `.env` et n'est jamais journalisée ni renvoyée dans les
    messages d'erreur. Aucun SDK payant n'est utilisé.
    """

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        transport: httpx.BaseTransport | None = None,
        base_url: str = GEMINI_BASE_URL,
    ) -> None:
        self.settings = settings or get_settings()
        self._transport = transport
        self._base_url = base_url

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

        if response.status_code != 200:
            # Le corps brut peut contenir des détails d'authentification.
            raise GeminiError(f"Gemini a répondu HTTP {response.status_code}.")

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
