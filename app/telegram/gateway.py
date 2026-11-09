from __future__ import annotations

import asyncio
import logging
import threading
from collections.abc import Callable

from telegram import Update
from telegram.error import InvalidToken
from telegram.ext import (
    Application,
    ApplicationHandlerStop,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    TypeHandler,
    filters,
)

from app.config import Settings, get_settings
from app.domain.models import Mission, MissionStatus
from app.orchestrator.manager import Manager
from app.telegram.auth import DENIED_MESSAGE, is_allowed

logger = logging.getLogger(__name__)

MAX_MESSAGE_LENGTH = 3900
RECENT_MISSIONS_LIMIT = 10

START_TEXT = (
    "Bonjour, je suis le Manager QA local de Football QA.\n\n"
    "Je fonctionne uniquement à la demande : aucun test planifié, aucune "
    "mission automatique.\n\n"
    "Commandes disponibles :\n"
    "/help — afficher l'aide\n"
    "/missions — lister les missions récentes\n"
    "/status <mission_id> — consulter une mission\n"
    "/approve <mission_id> — approuver puis exécuter une mission\n"
    "/stop <mission_id> — demander l'annulation d'une mission\n\n"
    "Vous pouvez aussi envoyer un texte libre pour créer puis exécuter une "
    "mission."
)

HELP_TEXT = (
    "Aide — Manager QA local\n\n"
    "/start — présentation du bot\n"
    "/help — cette aide\n"
    "/missions — afficher les 10 missions les plus récentes\n"
    "/status <mission_id> — statut, tâches et dernier événement\n"
    "/approve <mission_id> — approuver explicitement puis exécuter\n"
    "/stop <mission_id> — demander l'annulation\n\n"
    "Texte libre : crée une mission puis l'exécute. Si une approbation est "
    "nécessaire, la mission n'est pas exécutée et le motif est affiché.\n\n"
    "Aucune mission n'est lancée sans message explicite. Aucun planificateur "
    "n'est actif."
)


class ManagerProvider:
    """Fournit un seul Manager par processus, avec accès thread-safe."""

    def __init__(self, factory: Callable[[], Manager]) -> None:
        self._factory = factory
        self._manager: Manager | None = None
        self._lock = threading.Lock()

    def get(self) -> Manager:
        with self._lock:
            if self._manager is None:
                self._manager = self._factory()
            return self._manager

    def close(self) -> None:
        with self._lock:
            manager = self._manager
            self._manager = None
        if manager is not None:
            manager.close()


class TelegramGateway:
    """Passerelle Telegram en polling, sans scheduler ni mission automatique."""

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        manager_factory: Callable[[], Manager] | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        factory = manager_factory or (lambda: Manager(self.settings))
        self.managers = ManagerProvider(factory)
        self._run_lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Construction de l'application
    # ------------------------------------------------------------------
    def build_application(self) -> Application:
        token = self.settings.telegram_bot_token.strip()
        if not token:
            raise RuntimeError(
                "TELEGRAM_BOT_TOKEN est vide : renseignez-le dans .env avant "
                "de démarrer le bot."
            )

        allowed_user_id = self.settings.telegram_allowed_user_id.strip()
        if not allowed_user_id:
            raise RuntimeError(
                "TELEGRAM_ALLOWED_USER_ID est vide : démarrage refusé pour "
                "éviter un bot sans allowlist."
            )

        application = Application.builder().token(token).build()

        # Contrôle de l'allowlist avant tout autre handler, pour chaque update.
        application.add_handler(TypeHandler(Update, self._guard), group=-1)

        application.add_handler(CommandHandler("start", self._start))
        application.add_handler(CommandHandler("help", self._help))
        application.add_handler(CommandHandler("status", self._status))
        application.add_handler(CommandHandler("missions", self._missions))
        application.add_handler(CommandHandler("approve", self._approve))
        application.add_handler(CommandHandler("stop", self._stop))
        application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self._free_text)
        )
        application.add_handler(
            MessageHandler(filters.COMMAND, self._unknown_command)
        )
        application.add_error_handler(self._on_error)
        return application

    def run(self) -> None:
        application = self.build_application()
        try:
            application.run_polling(
                allowed_updates=Update.ALL_TYPES,
                drop_pending_updates=False,
            )
        finally:
            self.managers.close()

    # ------------------------------------------------------------------
    # Allowlist
    # ------------------------------------------------------------------
    def _user_is_allowed(self, update: Update) -> bool:
        user = update.effective_user
        return is_allowed(
            user.id if user is not None else None,
            self.settings.telegram_allowed_user_id,
        )

    async def _guard(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        if self._user_is_allowed(update):
            return

        # Message neutre : aucune information sur la configuration.
        await self._reply(update, DENIED_MESSAGE)
        raise ApplicationHandlerStop

    # ------------------------------------------------------------------
    # Commandes
    # ------------------------------------------------------------------
    async def _start(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        if not self._user_is_allowed(update):
            return
        await self._reply(update, START_TEXT)

    async def _help(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        if not self._user_is_allowed(update):
            return
        await self._reply(update, HELP_TEXT)

    async def _status(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        if not self._user_is_allowed(update):
            return

        mission_id = _first_argument(context)
        if not mission_id:
            await self._reply(update, "Usage : /status <mission_id>")
            return

        try:
            text = await asyncio.to_thread(self._status_text, mission_id)
        except ValueError:
            await self._reply(update, f"Mission introuvable : {mission_id}")
            return
        await self._reply(update, text)

    async def _missions(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        if not self._user_is_allowed(update):
            return
        text = await asyncio.to_thread(self._missions_text)
        await self._reply(update, text)

    async def _approve(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        if not self._user_is_allowed(update):
            return

        mission_id = _first_argument(context)
        if not mission_id:
            await self._reply(update, "Usage : /approve <mission_id>")
            return

        try:
            mission = await self._run_mission(mission_id, approved=True)
        except ValueError:
            await self._reply(update, f"Mission introuvable : {mission_id}")
            return
        await self._reply(update, _mission_result_text(mission, "Mission approuvée"))

    async def _stop(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        if not self._user_is_allowed(update):
            return

        mission_id = _first_argument(context)
        if not mission_id:
            await self._reply(update, "Usage : /stop <mission_id>")
            return

        try:
            manager = await asyncio.to_thread(self.managers.get)
            mission = await asyncio.to_thread(manager.cancel_mission, mission_id)
        except ValueError:
            await self._reply(update, f"Mission introuvable : {mission_id}")
            return

        if mission.status in {
            MissionStatus.COMPLETED,
            MissionStatus.FAILED,
            MissionStatus.CANCELLED,
        }:
            await self._reply(
                update,
                f"Mission {mission.id} déjà terminée : {mission.status.value}.",
            )
            return

        await self._reply(
            update,
            f"Annulation demandée pour la mission {mission.id}.\n"
            f"Statut actuel : {mission.status.value}.",
        )

    async def _free_text(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        if not self._user_is_allowed(update):
            return

        message = update.effective_message
        instruction = (message.text or "").strip() if message is not None else ""
        if not instruction:
            return

        manager = await asyncio.to_thread(self.managers.get)
        mission = await asyncio.to_thread(manager.create_mission, instruction)

        if mission.requires_approval:
            await self._reply(
                update,
                f"Mission {mission.id} créée.\n"
                f"Approbation requise : "
                f"{mission.approval_reason or 'action sensible'}.\n"
                f"La mission n'a pas été exécutée. Utilisez "
                f"/approve {mission.id} pour l'autoriser.",
            )
            return

        mission = await self._run_mission(mission.id)
        await self._reply(update, _mission_result_text(mission))

    async def _unknown_command(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        if not self._user_is_allowed(update):
            return
        await self._reply(
            update,
            "Commande inconnue. Utilisez /help pour afficher les commandes.",
        )

    # ------------------------------------------------------------------
    # Exécution synchrone déportée dans un thread
    # ------------------------------------------------------------------
    async def _run_mission(
        self,
        mission_id: str,
        *,
        approved: bool = False,
    ) -> Mission:
        """Exécute une mission hors de la boucle asyncio.

        Le Manager est synchrone. Le verrou empêche deux exécutions
        simultanées dans le même processus.
        """
        async with self._run_lock:
            manager = await asyncio.to_thread(self.managers.get)
            return await asyncio.to_thread(
                manager.run_mission,
                mission_id,
                approved=approved,
            )

    def _status_text(self, mission_id: str) -> str:
        manager = self.managers.get()
        data = manager.status(mission_id)
        mission: Mission = data["mission"]

        lines = [
            f"Mission {mission.id}",
            f"Statut : {mission.status.value}",
            f"Instruction : {mission.instruction}",
        ]
        if mission.requires_approval:
            lines.append(
                f"Approbation : {mission.approval_reason or 'requise'}"
            )
        if mission.report_path:
            lines.append(f"Rapport : {mission.report_path}")

        tasks = data["tasks"]
        lines.append("Tâches :")
        if tasks:
            for task in tasks[:20]:
                lines.append(f"- {task.agent} [{task.status.value}] {task.title}")
            if len(tasks) > 20:
                lines.append(f"- … et {len(tasks) - 20} autre(s)")
        else:
            lines.append("- aucune")

        events = data["events"]
        if events:
            lines.append(f"Dernier événement : {events[-1].type}")
        else:
            lines.append("Dernier événement : aucun")

        return "\n".join(lines)

    def _missions_text(self) -> str:
        missions = self.managers.get().list_missions()[:RECENT_MISSIONS_LIMIT]
        if not missions:
            return "Aucune mission enregistrée."

        lines = ["Missions récentes :"]
        for mission in missions:
            lines.append(
                f"- {mission.id} [{mission.status.value}] "
                f"{mission.instruction[:80]}"
            )
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Réponses et erreurs
    # ------------------------------------------------------------------
    async def _reply(self, update: Update, text: str) -> None:
        message = update.effective_message
        if message is None:
            return

        for start in range(0, max(len(text), 1), MAX_MESSAGE_LENGTH):
            chunk = text[start : start + MAX_MESSAGE_LENGTH]
            try:
                await message.reply_text(chunk)
            except Exception:
                # Aucun détail technique ni secret n'est journalisé.
                logger.warning("Échec de l'envoi d'une réponse Telegram.")
                return

    async def _on_error(
        self,
        update: object,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        error = getattr(context, "error", None)
        logger.error(
            "Erreur interne Telegram : %s",
            type(error).__name__ if error is not None else "inconnue",
        )
        if isinstance(update, Update):
            await self._reply(
                update,
                "Une erreur interne est survenue. Consultez les logs locaux.",
            )


def _first_argument(context: ContextTypes.DEFAULT_TYPE | None) -> str:
    if context is None or not getattr(context, "args", None):
        return ""
    return context.args[0].strip()


def _mission_result_text(mission: Mission, title: str | None = None) -> str:
    lines = [title or "Mission exécutée", f"ID : {mission.id}"]
    lines.append(f"Statut : {mission.status.value}")
    if mission.report_path:
        lines.append(f"Rapport : {mission.report_path}")
    return "\n".join(lines)


def main() -> int:
    settings = get_settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    if not settings.telegram_bot_token.strip():
        print(
            "TELEGRAM_BOT_TOKEN est vide dans .env : le bot Telegram ne "
            "démarre pas. Renseignez-le localement, sans le publier."
        )
        return 2

    if not settings.telegram_allowed_user_id.strip():
        print(
            "TELEGRAM_ALLOWED_USER_ID est vide dans .env : démarrage refusé "
            "pour éviter un bot sans allowlist."
        )
        return 2

    try:
        TelegramGateway(settings).run()
    except InvalidToken:
        # Le message natif de PTB peut contenir le token : on ne l'affiche pas.
        print(
            "TELEGRAM_BOT_TOKEN a été refusé par Telegram. Vérifiez sa valeur "
            "dans .env, sans la publier."
        )
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
