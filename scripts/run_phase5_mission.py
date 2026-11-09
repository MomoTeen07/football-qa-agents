"""Exécute une mission réelle de phase 5 sur la stack de test.

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
    "Analyse l'API réelle, prépare la collection Postman et exécute les "
    "premiers tests API sur la stack de test isolée."
)


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
        print(f"REQUIRES_APPROVAL={mission.requires_approval}")

        final = manager.run_mission(mission.id)
        print(f"FINAL_STATUS={final.status.value}")
        print(f"REPORT_PATH={final.report_path}")

        for task in manager.get_tasks(mission.id):
            print(f"TASK {task.agent} {task.status.value}")
            for evidence in task.evidence:
                print(f"  EVIDENCE {evidence}")

        probe_path = (
            Path(settings.workspace_dir)
            / "missions"
            / mission.id
            / "api"
            / "probe-results.json"
        )
        if probe_path.is_file():
            probe = json.loads(probe_path.read_text(encoding="utf-8"))
            checks = probe.get("checks", [])
            executed = [check for check in checks if not check.get("skipped")]
            passed = [check for check in executed if check.get("passed")]
            print(f"PROBE_STATUS={probe.get('status')}")
            print(f"PROBE_CHECKS={len(executed)}")
            print(f"PROBE_PASSED={len(passed)}")
            print(f"PROBE_ANOMALIES={len(probe.get('anomalies', []))}")

        return 0 if final.status.value == "completed" else 1
    finally:
        manager.close()


if __name__ == "__main__":
    raise SystemExit(main())
