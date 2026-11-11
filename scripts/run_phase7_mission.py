"""Régénère le rapport phase 7 d'une mission existante (explicite uniquement).

Aucune mission automatique, aucun scheduler. Le script :

1. recharge une mission réelle et ses tâches depuis la base SQLite locale ;
2. régénère le rapport Markdown, la synthèse JSON et les résultats Allure 2 ;
3. prépare la promotion Git des suites générées (mode préparation par défaut).

La publication réelle (copie, commit, push, pull request) exige à la fois
`DEVOPS_PUBLISH_ENABLED=true` dans `.env` et l'option `--publish`, qui sert de
confirmation explicite. Le script ne fusionne jamais la pull request.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config import get_settings
from app.domain.models import Task
from app.orchestrator.manager import Manager

EVIDENCE_FILES = (
    "api/probe-results.json",
    "api-automation/api-automation-results.json",
    "ui-automation/ui-automation-results.json",
)


def has_evidence(settings, mission_id: str) -> bool:
    base = Path(settings.workspace_dir) / "missions" / mission_id
    return any((base / relative).is_file() for relative in EVIDENCE_FILES)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Rapport phase 7 (Allure + Markdown/JSON) d'une mission."
    )
    parser.add_argument(
        "--mission-id",
        help="Mission source ; par défaut, la plus récente avec des preuves.",
    )
    parser.add_argument(
        "--publish",
        action="store_true",
        help=(
            "Confirme la publication Git. Sans DEVOPS_PUBLISH_ENABLED=true, "
            "le mode préparation est conservé."
        ),
    )
    return parser.parse_args()


def select_mission(manager: Manager, settings, requested: str | None):
    if requested:
        mission = manager.get_mission(requested)
        if mission is None:
            raise SystemExit(f"MISSION_INTROUVABLE={requested}")
        return mission
    for mission in manager.list_missions():
        if has_evidence(settings, mission.id):
            return mission
    raise SystemExit(
        "AUCUNE_MISSION_AVEC_PREUVES : précisez --mission-id ou exécutez "
        "d'abord une mission API/UI."
    )


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")

    args = parse_args()
    settings = get_settings()
    manager = Manager(settings)
    try:
        mission = select_mission(manager, settings, args.mission_id)
        tasks = manager.get_tasks(mission.id)
        context = {
            "tasks": [
                {
                    "agent": task.agent,
                    "title": task.title,
                    "status": task.status.value,
                    "result": task.result or "",
                    "evidence": task.evidence,
                }
                for task in tasks
            ]
        }
        report_task = next(
            (task for task in tasks if task.agent == "qa_reporter"), None
        ) or Task(
            mission_id=mission.id,
            key="report",
            agent="qa_reporter",
            title="Consolider les résultats et produire le rapport",
        )

        reporter = manager.agents["qa_reporter"]
        report = reporter.run(report_task, mission, context=context)

        reports_dir = Path(settings.reports_dir)
        reports_dir.mkdir(parents=True, exist_ok=True)
        report_path = reports_dir / f"{mission.id}.md"
        report_path.write_text(report.summary, encoding="utf-8")

        print(f"MISSION_ID={mission.id}")
        print(f"REPORT_PATH={report_path}")
        for evidence in report.evidence:
            if evidence.endswith(".json") and "allure-results" not in evidence:
                print(f"REPORT_JSON={evidence}")
            if evidence.endswith("allure-summary.json"):
                summary = json.loads(
                    Path(evidence).read_text(encoding="utf-8")
                )
                totals = summary.get("totals", {})
                print(f"ALLURE_STATUS={summary.get('status')}")
                print(f"ALLURE_TOTAL={totals.get('total', 0)}")
                print(f"ALLURE_PASSED={totals.get('passed', 0)}")
                print(f"ALLURE_FAILED={totals.get('failed', 0)}")
                print(f"ALLURE_BROKEN={totals.get('broken', 0)}")
                print(f"ALLURE_SKIPPED={totals.get('skipped', 0)}")
                print(f"ALLURE_ANOMALIES={totals.get('anomalies', 0)}")
                print(f"ALLURE_RESULTS_DIR={summary.get('results_dir')}")

        devops = manager.agents["devops"]
        devops_task = next(
            (task for task in tasks if task.agent == "devops"), None
        ) or Task(
            mission_id=mission.id,
            key="devops",
            agent="devops",
            title="Préparer la branche, la PR et la CI passive",
        )
        if args.publish and not settings.devops_publish_enabled:
            print(
                "DEVOPS_PUBLISH_ENABLED=false : publication refusée, "
                "mode préparation conservé."
            )
        devops_result = devops.run(devops_task, mission)
        for evidence in devops_result.evidence:
            if not evidence.endswith("devops-results.json"):
                continue
            payload = json.loads(Path(evidence).read_text(encoding="utf-8"))
            print(f"DEVOPS_STATUS={payload.get('status')}")
            print(f"DEVOPS_BRANCH={payload.get('branch')}")
            print(f"DEVOPS_COMMIT={payload.get('commit')}")
            print(f"DEVOPS_PR_URL={payload.get('pr_url')}")
            print(f"DEVOPS_FILES={len(payload.get('promoted_files', []))}")
            if payload.get("blocked_reason"):
                print(f"DEVOPS_BLOCKED_REASON={payload['blocked_reason']}")
            print(f"DEVOPS_RESULTS={evidence}")

        return 0
    finally:
        manager.close()


if __name__ == "__main__":
    raise SystemExit(main())
