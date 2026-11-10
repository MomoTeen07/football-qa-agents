from __future__ import annotations

import httpx
import pytest

from app.config import Settings
from app.llm.gemini import GeminiClient, GeminiError, GeminiUnavailableError


def make_settings(**overrides) -> Settings:
    values = {
        "gemini_api_key": "fake-key-for-tests",
        "llm_model": "gemini-2.5-flash",
        "llm_timeout_seconds": 5,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_gemini_generates_text() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {"content": {"parts": [{"text": "Analyse Gemini OK"}]}}
                ]
            },
        )

    client = GeminiClient(make_settings(), transport=httpx.MockTransport(handler))
    assert client.available is True
    assert client.generate("Prompt de test") == "Analyse Gemini OK"


def test_gemini_missing_key_is_explicit_and_safe() -> None:
    client = GeminiClient(make_settings(gemini_api_key=""))
    assert client.available is False
    with pytest.raises(GeminiUnavailableError):
        client.generate("Prompt")


def test_gemini_http_error_does_not_leak_the_key() -> None:
    secret = "fake-key-for-tests"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"error": {"message": secret}})

    client = GeminiClient(make_settings(), transport=httpx.MockTransport(handler))
    with pytest.raises(GeminiError) as error:
        client.generate("Prompt")
    assert secret not in str(error.value)
    assert "HTTP 400" in str(error.value)


def test_gemini_network_error_does_not_leak_the_key() -> None:
    secret = "fake-key-for-tests"

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError(secret, request=request)

    client = GeminiClient(make_settings(), transport=httpx.MockTransport(handler))
    with pytest.raises(GeminiError) as error:
        client.generate("Prompt")
    assert secret not in str(error.value)


def test_gemini_empty_response_is_rejected() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"candidates": []})

    client = GeminiClient(make_settings(), transport=httpx.MockTransport(handler))
    with pytest.raises(GeminiError):
        client.generate("Prompt")


def test_gemini_retries_a_transient_429_then_succeeds() -> None:
    calls: list[int] = []
    sleeps: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        if len(calls) == 1:
            return httpx.Response(429, json={"error": {"code": 429}})
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {"content": {"parts": [{"text": "Après reprise"}]}}
                ]
            },
        )

    client = GeminiClient(
        make_settings(),
        transport=httpx.MockTransport(handler),
        sleep=sleeps.append,
    )

    assert client.generate("Prompt") == "Après reprise"
    assert len(calls) == 2
    assert sleeps == [1.0]


def test_gemini_gives_up_after_max_attempts_without_leaking_the_key() -> None:
    secret = "fake-key-for-tests"
    calls: list[int] = []
    sleeps: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(503, json={"error": {"message": secret}})

    client = GeminiClient(
        make_settings(),
        transport=httpx.MockTransport(handler),
        sleep=sleeps.append,
    )

    with pytest.raises(GeminiError) as error:
        client.generate("Prompt")

    assert len(calls) == 3
    assert sleeps == [1.0, 2.0]
    assert "HTTP 503" in str(error.value)
    assert secret not in str(error.value)


def test_gemini_does_not_retry_a_definitive_error() -> None:
    calls: list[int] = []
    sleeps: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(400, json={"error": {"code": 400}})

    client = GeminiClient(
        make_settings(),
        transport=httpx.MockTransport(handler),
        sleep=sleeps.append,
    )

    with pytest.raises(GeminiError):
        client.generate("Prompt")

    assert len(calls) == 1
    assert sleeps == []
