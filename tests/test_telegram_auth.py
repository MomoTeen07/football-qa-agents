from __future__ import annotations

from app.telegram.auth import DENIED_MESSAGE, is_allowed


def test_configured_user_is_allowed() -> None:
    assert is_allowed(496100274, "496100274") is True
    assert is_allowed(496100274, " 496100274 ") is True
    assert is_allowed(496100274, 496100274) is True


def test_unknown_user_is_rejected() -> None:
    assert is_allowed(123456789, "496100274") is False


def test_missing_user_id_is_rejected() -> None:
    assert is_allowed(None, "496100274") is False


def test_empty_allowlist_rejects_everyone() -> None:
    assert is_allowed(496100274, "") is False
    assert is_allowed(496100274, "   ") is False
    assert is_allowed(496100274, None) is False
    assert is_allowed(None, None) is False


def test_denied_message_reveals_no_configuration() -> None:
    assert "496100274" not in DENIED_MESSAGE
    assert "TELEGRAM" not in DENIED_MESSAGE.upper()
    assert "ALLOWED" not in DENIED_MESSAGE.upper()
