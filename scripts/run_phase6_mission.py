"""Exécute une mission réelle de phase 6 sur la stack de test.

Aucune mission automatique : ce script doit être lancé explicitement.
Il ne lit ni n'affiche aucun secret.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config import get_settings
from app.orchestrator.manager import Manager

INSTRUCTION = (
    "Lance une campagne complète de tests API et UI : génère et exécute la "
    "suite pytest d'automatisation API puis les scénarios Playwright sur la "
    "stack de test isolée."
)


def read_results(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")

    settings = get_settings()
    if not settings.real_agents_enabled:
        print(
            "REAL_AGENTS_ENABLED=false : les agents réels ne sont pas activés. "
            "Renseignez REAL_AGENTS_ENABLED=true dans .env."
        )
        return 1

    manager = Manager(settings)
    try:
        mission = manager.create_mission(INSTRUCTION)
        print(f"MISSION_ID={mission.id}")
        final = manager.run_mission(mission.id)
        print(f"FINAL_STATUS={final.status.value}")
        print(f"REPORT_PATH={final.report_path}")

        for task in manager.get_tasks(mission.id):
            print(f"TASK {task.agent} {task.status.value}")
            for evidence in task.evidence:
                print(f"  EVIDENCE {evidence}")

        base = Path(settings.workspace_dir) / "missions" / mission.id
        for label, relative, count_key in (
            ("API", "api-automation/api-automation-results.json", "tests"),
            ("UI", "ui-automation/ui-automation-results.json", "checks"),
        ):
            payload = read_results(base / relative)
            if not payload:
                print(f"{label}_STATUS=absent")
                continue
            summary = payload.get("summary") or {}
            print(f"{label}_STATUS={payload.get('status')}")
            print(f"{label}_{count_key.upper()}={summary.get(count_key, 0)}")
            print(f"{label}_PASSED={summary.get('passed', 0)}")
            print(f"{label}_FAILED={summary.get('failed', 0)}")
            print(f"{label}_ANOMALIES={summary.get('anomalies', 0)}")
            if payload.get("blocked_reason"):
                print(f"{label}_BLOCKED_REASON={payload['blocked_reason']}")

        return 0 if final.status.value == "completed" else 1
    finally:
        manager.close()


if __name__ == "__main__":
    raise SystemExit(main())
