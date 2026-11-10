from __future__ import annotations

import importlib
import io
import logging
import warnings
from pathlib import Path
from types import SimpleNamespace

import pytest
from telegram.error import InvalidToken
from telegram.ext import ApplicationHandlerStop
from telegram.warnings import PTBUserWarning

import app.telegram.gateway as gateway_module
from app.config import Settings
from app.domain.models import Mission, MissionStatus
from app.orchestrator.manager import Manager
from app.telegram.auth import DENIED_MESSAGE
from app.telegram.gateway import TelegramGateway

ALLOWED_USER_ID = 496100274


class FakeMessage:
    def __init__(self, text: str = "") -> None:
        self.text = text
        self.replies: list[str] = []

    async def reply_text(self, text: str) -> None:
        self.replies.append(text)


class FakeUser:
    def __init__(self, user_id: int) -> None:
        self.id = user_id


class FakeUpdate:
    def __init__(
        self,
        user_id: int | None = ALLOWED_USER_ID,
        text: str = "",
    ) -> None:
        self.effective_user = FakeUser(user_id) if user_id is not None else None
        self.effective_message = FakeMessage(text)


class FakeManager:
    def __init__(self, mission: Mission | None = None) -> None:
        self.mission = mission
        self.created: list[str] = []
        self.runs: list[tuple[str, bool]] = []
        self.cancelled: list[str] = []
        self.closed = False

    def create_mission(self, instruction: str) -> Mission:
        self.created.append(instruction)
        assert self.mission is not None
        return self.mission

    def run_mission(self, mission_id: str, *, approved: bool = False) -> Mission:
        self.runs.append((mission_id, approved))
        assert self.mission is not None
        self.mission.status = MissionStatus.COMPLETED
        return self.mission

    def cancel_mission(self, mission_id: str) -> Mission:
        self.cancelled.append(mission_id)
        assert self.mission is not None
        return self.mission

    def status(self, mission_id: str) -> dict:
        assert self.mission is not None
        return {
            "mission": self.mission,
            "tasks": [],
            "events": [],
        }

    def list_missions(self) -> list[Mission]:
        return [self.mission] if self.mission is not None else []

    def close(self) -> None:
        self.closed = True


def make_settings(tmp_path: Path) -> Settings:
    return Settings(
        telegram_bot_token="123456:TESTTOKEN",
        telegram_allowed_user_id=str(ALLOWED_USER_ID),
        mission_db_path=tmp_path / "missions.db",
        reports_dir=tmp_path / "reports",
    )


def make_gateway(tmp_path: Path, manager: FakeManager) -> TelegramGateway:
    return TelegramGateway(
        make_settings(tmp_path),
        manager_factory=lambda: manager,  # type: ignore[arg-type]
    )


def test_import_does_not_instantiate_manager(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("Le Manager ne doit pas être instancié à l'import.")

    monkeypatch.setattr(Manager, "__init__", forbidden)
    # Le rechargement exécute de nouveau le code de haut niveau du module.
    importlib.reload(gateway_module)


def test_building_application_creates_no_manager_and_no_mission(
    tmp_path: Path,
) -> None:
    calls: list[str] = []

    def factory() -> Manager:
        calls.append("manager")
        raise AssertionError("Aucun Manager ne doit être créé à la construction.")

    gateway = TelegramGateway(make_settings(tmp_path), manager_factory=factory)
    application = gateway.build_application()

    assert application is not None
    assert calls == []
    assert not (tmp_path / "missions.db").exists()


def test_gateway_has_no_job_queue(tmp_path: Path) -> None:
    manager = FakeManager(Mission(instruction="Analyse l'application."))
    gateway = make_gateway(tmp_path, manager)

    # PTB signale explicitement qu'aucune file de tâches n'est installée.
    application = gateway.build_application()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        job_queue = application.job_queue

    assert job_queue is None
    assert any(isinstance(item.message, PTBUserWarning) for item in caught)


@pytest.mark.asyncio
async def test_unknown_user_is_denied_without_manager_access(
    tmp_path: Path,
) -> None:
    calls: list[str] = []

    def factory() -> Manager:
        calls.append("manager")
        raise AssertionError("Un utilisateur refusé ne doit pas accéder au Manager.")

    gateway = TelegramGateway(make_settings(tmp_path), manager_factory=factory)
    update = FakeUpdate(user_id=999)

    with pytest.raises(ApplicationHandlerStop):
        await gateway._guard(update, None)  # type: ignore[arg-type]

    assert update.effective_message.replies == [DENIED_MESSAGE]
    assert calls == []


@pytest.mark.asyncio
async def test_missing_user_is_denied(tmp_path: Path) -> None:
    manager = FakeManager(Mission(instruction="Analyse l'application."))
    gateway = make_gateway(tmp_path, manager)
    update = FakeUpdate(user_id=None)

    with pytest.raises(ApplicationHandlerStop):
        await gateway._guard(update, None)  # type: ignore[arg-type]

    assert update.effective_message.replies == [DENIED_MESSAGE]


@pytest.mark.asyncio
async def test_allowed_user_passes_the_guard(tmp_path: Path) -> None:
    manager = FakeManager(Mission(instruction="Analyse l'application."))
    gateway = make_gateway(tmp_path, manager)
    update = FakeUpdate()

    await gateway._guard(update, None)  # type: ignore[arg-type]

    assert update.effective_message.replies == []


@pytest.mark.asyncio
async def test_empty_message_does_not_create_a_mission(tmp_path: Path) -> None:
    manager = FakeManager(Mission(instruction="Analyse l'application."))
    gateway = make_gateway(tmp_path, manager)
    update = FakeUpdate(text="   ")

    await gateway._free_text(update, None)  # type: ignore[arg-type]

    assert manager.created == []
    assert manager.runs == []


@pytest.mark.asyncio
async def test_free_text_creates_then_runs_exactly_one_mission(
    tmp_path: Path,
) -> None:
    mission = Mission(instruction="Analyse l'application et propose un plan.")
    manager = FakeManager(mission)
    gateway = make_gateway(tmp_path, manager)
    update = FakeUpdate(text=mission.instruction)

    await gateway._free_text(update, None)  # type: ignore[arg-type]

    assert manager.created == [mission.instruction]
    assert manager.runs == [(mission.id, False)]
    assert mission.id in update.effective_message.replies[-1]
    assert "completed" in update.effective_message.replies[-1]


@pytest.mark.asyncio
async def test_free_text_requiring_approval_is_not_executed(
    tmp_path: Path,
) -> None:
    mission = Mission(
        instruction="Lance un test de sécurité intrusif sur l'API.",
        requires_approval=True,
        approval_reason="test de sécurité intrusif",
    )
    manager = FakeManager(mission)
    gateway = make_gateway(tmp_path, manager)
    update = FakeUpdate(text=mission.instruction)

    await gateway._free_text(update, None)  # type: ignore[arg-type]

    assert manager.created == [mission.instruction]
    assert manager.runs == []
    reply = update.effective_message.replies[-1]
    assert mission.id in reply
    assert "Approbation requise" in reply
    assert "n'a pas été exécutée" in reply


@pytest.mark.asyncio
async def test_approve_command_runs_with_explicit_approval(
    tmp_path: Path,
) -> None:
    mission = Mission(
        instruction="Lance un test de sécurité intrusif sur l'API.",
        requires_approval=True,
        approval_reason="test de sécurité intrusif",
    )
    manager = FakeManager(mission)
    gateway = make_gateway(tmp_path, manager)
    update = FakeUpdate()
    context = SimpleNamespace(args=[mission.id])

    await gateway._approve(update, context)  # type: ignore[arg-type]

    assert manager.runs == [(mission.id, True)]
    assert "Statut : completed" in update.effective_message.replies[-1]


@pytest.mark.asyncio
async def test_stop_command_requests_cancellation(tmp_path: Path) -> None:
    mission = Mission(instruction="Analyse l'application.")
    manager = FakeManager(mission)
    gateway = make_gateway(tmp_path, manager)
    update = FakeUpdate()
    context = SimpleNamespace(args=[mission.id])

    await gateway._stop(update, context)  # type: ignore[arg-type]

    assert manager.cancelled == [mission.id]
    assert mission.id in update.effective_message.replies[-1]


def test_log_records_never_contain_the_token() -> None:
    """httpx journalise l'URL Bot API : le filtre doit masquer le jeton."""
    fake_token = "123456:FAKE-SECRET-TOKEN"
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.addFilter(gateway_module.SecretRedactionFilter(fake_token))
    logger = logging.getLogger("tests.telegram.redaction")
    logger.propagate = False
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    try:
        logger.info(
            "HTTP Request: POST https://api.telegram.org/bot%s/getMe",
            fake_token,
        )
    finally:
        logger.removeHandler(handler)

    output = stream.getvalue()
    assert fake_token not in output
    assert "FAKE-SECRET-TOKEN" not in output
    assert gateway_module.SECRET_PLACEHOLDER in output


def test_main_refuses_to_start_without_token(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    settings = Settings(
        telegram_bot_token="",
        telegram_allowed_user_id=str(ALLOWED_USER_ID),
    )
    started: list[bool] = []

    monkeypatch.setattr(gateway_module, "get_settings", lambda: settings)
    monkeypatch.setattr(
        gateway_module.TelegramGateway,
        "run",
        lambda self: started.append(True),
    )

    assert gateway_module.main() == 2
    assert started == []
    assert "TELEGRAM_BOT_TOKEN" in capsys.readouterr().out


def test_main_never_prints_a_rejected_token(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    fake_token = "123456:FAKE-SECRET-TOKEN"
    settings = Settings(
        telegram_bot_token=fake_token,
        telegram_allowed_user_id=str(ALLOWED_USER_ID),
    )

    def rejected(self: TelegramGateway) -> None:
        raise InvalidToken(
            f"The token `{fake_token}` was rejected by the server."
        )

    monkeypatch.setattr(gateway_module, "get_settings", lambda: settings)
    monkeypatch.setattr(gateway_module.TelegramGateway, "run", rejected)

    assert gateway_module.main() == 3
    output = capsys.readouterr().out
    assert fake_token not in output
    assert "FAKE-SECRET-TOKEN" not in output
    assert "refus" in output
