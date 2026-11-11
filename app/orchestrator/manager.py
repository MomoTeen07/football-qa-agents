from __future__ import annotations

import sqlite3
from pathlib import Path

from langgraph.checkpoint.sqlite import SqliteSaver

from app.agents.phase5 import APITesterAgent, QAAnalystAgent, TestDesignerAgent
from app.agents.phase6 import APIAutomationAgent, UIAutomationAgent
from app.agents.phase7 import DevOpsAgent, QAReporterAgent
from app.config import Settings, get_settings
from app.domain.models import Event, Mission, MissionStatus, Task
from app.events.bus import EventBus
from app.llm.gemini import GeminiClient
from app.orchestrator.graph import build_graph
from app.orchestrator.planner import mission_requires_approval
from app.store.sqlite_store import SqliteStore
from app.tools.api_probe import ApiProbe


class Manager:
    """Manager QA déterministe, assisté par LangGraph.

    Aucune mission n'est créée ni exécutée automatiquement. Le Manager
    n'agit que sur appel explicite de `create_mission` puis `run_mission`.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.store = SqliteStore(Path(self.settings.mission_db_path))
        self.bus = EventBus(self.store)
        self._cancelled: set[str] = set()
        self.llm = GeminiClient(self.settings)
        self.api_probe = ApiProbe(self.settings)
        self.agents = {
            "qa_analyst": QAAnalystAgent(self.settings, self.llm),
            "test_designer": TestDesignerAgent(self.settings, self.llm),
            "api_tester": APITesterAgent(self.settings, self.llm, self.api_probe),
            "api_automation": APIAutomationAgent(self.settings),
            "ui_automation": UIAutomationAgent(self.settings),
            "devops": DevOpsAgent(self.settings),
            "qa_reporter": QAReporterAgent(self.settings),
        }
        self._checkpoint_connection = sqlite3.connect(
            self.store.path,
            check_same_thread=False,
        )
        self._saver = SqliteSaver(self._checkpoint_connection)
        if hasattr(self._saver, "setup"):
            self._saver.setup()
        self.graph = build_graph(
            self.store,
            self.bus,
            self.agents,
            self._saver,
            Path(self.settings.reports_dir),
            cancel_check=self.is_cancelled,
        )

    def close(self) -> None:
        self._checkpoint_connection.close()

    def is_cancelled(self, mission_id: str) -> bool:
        return mission_id in self._cancelled

    def cancel_mission(self, mission_id: str) -> Mission:
        mission = self.store.get_mission(mission_id)
        if mission is None:
            raise ValueError(f"Mission introuvable : {mission_id}")
        if mission.status in {
            MissionStatus.COMPLETED,
            MissionStatus.FAILED,
            MissionStatus.CANCELLED,
        }:
            return mission
        self._cancelled.add(mission_id)
        self.bus.publish(
            mission_id,
            "mission_cancel_requested",
            payload={"reason": "demande utilisateur"},
        )
        return mission

    # ------------------------------------------------------------------
    # Cycle de vie d'une mission
    # ------------------------------------------------------------------
    def create_mission(self, instruction: str) -> Mission:
        requires_approval, reason = mission_requires_approval(instruction)
        mission = Mission(
            instruction=instruction,
            requires_approval=requires_approval,
            approval_reason=reason,
        )
        self.store.create_mission(mission)
        self.bus.publish(
            mission.id,
            "mission_created",
            payload={
                "instruction": instruction,
                "requires_approval": requires_approval,
                "approval_reason": reason,
            },
        )
        return mission

    def run_mission(self, mission_id: str, *, approved: bool = False) -> Mission:
        mission = self.store.get_mission(mission_id)
        if mission is None:
            raise ValueError(f"Mission introuvable : {mission_id}")

        if mission.status in {
            MissionStatus.COMPLETED,
            MissionStatus.FAILED,
            MissionStatus.CANCELLED,
        }:
            return mission

        if self.is_cancelled(mission_id):
            self.store.update_mission(mission_id, status=MissionStatus.CANCELLED)
            self.bus.publish(
                mission_id,
                "mission_cancelled",
                payload={"reason": "annulation avant exécution"},
            )
            return self.store.get_mission(mission_id)  # type: ignore[return-value]

        if mission.requires_approval and not approved:
            self.store.update_mission(
                mission_id,
                status=MissionStatus.WAITING_APPROVAL,
            )
            self.bus.publish(
                mission_id,
                "approval_required",
                payload={"reason": mission.approval_reason},
            )
            return self.store.get_mission(mission_id)  # type: ignore[return-value]

        if approved:
            self.bus.publish(
                mission_id,
                "mission_approved",
                payload={"reason": mission.approval_reason},
            )

        self.store.update_mission(mission_id, status=MissionStatus.RUNNING)
        self.bus.publish(
            mission_id,
            "mission_started",
            payload={"instruction": mission.instruction},
        )
        try:
            self.graph.invoke(
                {
                    "mission_id": mission_id,
                    "instruction": mission.instruction,
                },
                config={"configurable": {"thread_id": mission_id}},
            )
        except Exception as exc:  # pragma: no cover - garde-fou
            self.store.update_mission(mission_id, status=MissionStatus.FAILED)
            self.bus.publish(
                mission_id,
                "mission_failed",
                payload={"error": str(exc)},
            )
        return self.store.get_mission(mission_id)  # type: ignore[return-value]

    def approve_mission(self, mission_id: str) -> Mission:
        return self.run_mission(mission_id, approved=True)

    # ------------------------------------------------------------------
    # Consultation
    # ------------------------------------------------------------------
    def get_mission(self, mission_id: str) -> Mission | None:
        return self.store.get_mission(mission_id)

    def list_missions(self) -> list[Mission]:
        return self.store.list_missions()

    def get_tasks(self, mission_id: str) -> list[Task]:
        return self.store.list_tasks(mission_id)

    def get_events(self, mission_id: str) -> list[Event]:
        return self.store.list_events(mission_id)

    def status(self, mission_id: str) -> dict:
        mission = self.store.get_mission(mission_id)
        if mission is None:
            raise ValueError(f"Mission introuvable : {mission_id}")
        return {
            "mission": mission,
            "tasks": self.store.list_tasks(mission_id),
            "events": self.store.list_events(mission_id),
        }
