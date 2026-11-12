from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph

from app.agents.base import BaseAgent
from app.domain.models import MissionStatus, Task, TaskStatus
from app.events.bus import EventBus
from app.orchestrator.planner import build_plan
from app.orchestrator.state import MissionState
from app.store.sqlite_store import SqliteStore


def _ordered_tasks(tasks: list[Task]) -> list[Task]:
    by_key = {task.key: task for task in tasks}
    ordered: list[Task] = []
    visited: set[str] = set()

    def visit(task: Task) -> None:
        if task.key in visited:
            return
        visited.add(task.key)
        for dependency in task.depends_on:
            if dependency in by_key:
                visit(by_key[dependency])
        ordered.append(task)

    for task in tasks:
        visit(task)
    return ordered


def build_graph(
    store: SqliteStore,
    bus: EventBus,
    agents: dict[str, BaseAgent],
    saver: SqliteSaver,
    reports_dir: Path,
    cancel_check: Callable[[str], bool] | None = None,
):
    def plan_node(state: MissionState) -> dict:
        mission_id = state["mission_id"]
        mission = store.get_mission(mission_id)
        if mission is None:
            raise ValueError(f"Mission introuvable : {mission_id}")

        plan = build_plan(mission.instruction)
        existing = {task.key: task for task in store.list_tasks(mission_id)}
        task_ids: dict[str, str] = {}
        created = 0
        for item in plan:
            previous = existing.get(item["key"])
            if previous is not None:
                # Reprise après interruption : ne jamais dupliquer une tâche.
                task_ids[item["key"]] = previous.id
                continue
            task = Task(
                mission_id=mission_id,
                key=item["key"],
                agent=item["agent"],
                title=item["title"],
                depends_on=item["depends_on"],
            )
            store.create_task(task)
            task_ids[item["key"]] = task.id
            created += 1

        store.update_mission(mission_id, status=MissionStatus.PLANNING)
        if created:
            bus.publish(
                mission_id,
                "mission_planned",
                payload={
                    "task_count": len(plan),
                    "agents": [item["agent"] for item in plan],
                },
            )
        return {"plan": plan, "task_ids": task_ids, "status": "planned"}

    def execute_node(state: MissionState) -> dict:
        mission_id = state["mission_id"]
        mission = store.get_mission(mission_id)
        if mission is None:
            raise ValueError(f"Mission introuvable : {mission_id}")

        tasks = store.list_tasks(mission_id)
        statuses = {task.key: task.status.value for task in tasks}
        ordered = _ordered_tasks(tasks)

        for task in ordered:
            if task.status == TaskStatus.COMPLETED:
                # Reprise : une tâche déjà terminée n'est jamais rejouée, ce qui
                # évite les doublons d'événements et de preuves.
                continue

            if cancel_check and cancel_check(mission_id):
                for remaining in store.list_tasks(mission_id):
                    if remaining.status == TaskStatus.PENDING:
                        store.update_task(
                            remaining.id,
                            status=TaskStatus.SKIPPED,
                            result="Mission annulée par l'utilisateur.",
                        )
                return {"status": "cancelled"}

            dependencies_ok = all(
                statuses.get(dependency) == TaskStatus.COMPLETED.value
                for dependency in task.depends_on
            )
            # Le rapport doit pouvoir être produit même si une tâche a échoué.
            if not dependencies_ok and task.agent != "qa_reporter":
                store.update_task(task.id, status=TaskStatus.BLOCKED)
                statuses[task.key] = TaskStatus.BLOCKED.value
                bus.publish(
                    mission_id,
                    "task_blocked",
                    agent=task.agent,
                    payload={
                        "key": task.key,
                        "title": task.title,
                        "reason": "dépendance non satisfaite",
                    },
                )
                continue

            store.update_task(task.id, status=TaskStatus.RUNNING)
            bus.publish(
                mission_id,
                "task_started",
                agent=task.agent,
                payload={"key": task.key, "title": task.title},
            )
            try:
                result = agents[task.agent].run(task, mission)
            except Exception as exc:  # pragma: no cover - garde-fou d'exécution
                store.update_task(
                    task.id,
                    status=TaskStatus.FAILED,
                    result=str(exc),
                )
                statuses[task.key] = TaskStatus.FAILED.value
                bus.publish(
                    mission_id,
                    "task_failed",
                    agent=task.agent,
                    payload={"key": task.key, "title": task.title, "error": str(exc)},
                )
                continue

            store.update_task(
                task.id,
                status=TaskStatus.COMPLETED,
                result=result.summary,
                evidence=result.evidence,
            )
            statuses[task.key] = TaskStatus.COMPLETED.value
            bus.publish(
                mission_id,
                "task_completed",
                agent=task.agent,
                payload={
                    "key": task.key,
                    "title": task.title,
                    "summary": result.summary[:400],
                },
            )

        return {"status": "executed"}

    def review_node(state: MissionState) -> dict:
        mission_id = state["mission_id"]
        if state.get("status") == "cancelled":
            store.update_mission(mission_id, status=MissionStatus.CANCELLED)
            return {"status": "cancelled"}

        tasks = store.list_tasks(mission_id)
        failed = any(
            task.status in {TaskStatus.FAILED, TaskStatus.BLOCKED} for task in tasks
        )
        status = "failed" if failed else "reviewed"
        store.update_mission(mission_id, status=MissionStatus.REVIEWING)
        bus.publish(
            mission_id,
            "mission_reviewed",
            payload={
                "status": status,
                "completed": sum(
                    1 for task in tasks if task.status == TaskStatus.COMPLETED
                ),
                "failed": sum(
                    1
                    for task in tasks
                    if task.status in {TaskStatus.FAILED, TaskStatus.BLOCKED}
                ),
            },
        )
        return {"status": status}

    def report_node(state: MissionState) -> dict:
        mission_id = state["mission_id"]
        mission = store.get_mission(mission_id)
        if mission is None:
            raise ValueError(f"Mission introuvable : {mission_id}")

        tasks = store.list_tasks(mission_id)
        reporter = agents["qa_reporter"]
        report_task = next(
            (task for task in tasks if task.agent == "qa_reporter"), None
        )
        if report_task is None:
            raise ValueError("Tâche de rapport introuvable")

        existing_report = reports_dir / f"{mission_id}.md"
        if report_task.status == TaskStatus.COMPLETED and existing_report.is_file():
            # Reprise : le rapport déjà produit n'est ni régénéré ni annoncé
            # une seconde fois.
            store.update_mission(
                mission_id,
                status=MissionStatus.REPORTING,
                report_path=mission.report_path or str(existing_report),
            )
            return {"report": str(existing_report), "status": "reported"}

        result = reporter.run(
            report_task,
            mission,
            context={
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
            },
        )
        reports_dir.mkdir(parents=True, exist_ok=True)
        report_path = reports_dir / f"{mission_id}.md"
        report_path.write_text(result.summary, encoding="utf-8")

        store.update_task(
            report_task.id,
            status=TaskStatus.COMPLETED,
            result=result.summary,
            evidence=result.evidence,
        )
        store.update_mission(
            mission_id,
            status=MissionStatus.REPORTING,
            report_path=str(report_path),
        )
        bus.publish(
            mission_id,
            "report_ready",
            agent="qa_reporter",
            payload={"path": str(report_path), "evidence": result.evidence},
        )
        return {"report": str(report_path), "status": "reported"}

    def finalize_node(state: MissionState) -> dict:
        mission_id = state["mission_id"]
        mission = store.get_mission(mission_id)
        if mission is None:
            raise ValueError(f"Mission introuvable : {mission_id}")

        tasks = store.list_tasks(mission_id)
        cancelled = state.get("status") == "cancelled" or (
            cancel_check is not None and cancel_check(mission_id)
        )
        failed = any(
            task.status in {TaskStatus.FAILED, TaskStatus.BLOCKED} for task in tasks
        )
        if cancelled:
            final_status = MissionStatus.CANCELLED
            event_type = "mission_cancelled"
        elif failed:
            final_status = MissionStatus.FAILED
            event_type = "mission_failed"
        else:
            final_status = MissionStatus.COMPLETED
            event_type = "mission_completed"

        store.update_mission(mission_id, status=final_status)
        bus.publish(
            mission_id,
            event_type,
            payload={
                "status": final_status.value,
                "report": mission.report_path,
            },
        )
        return {"status": final_status.value}

    graph = StateGraph(MissionState)
    graph.add_node("plan", plan_node)
    graph.add_node("execute", execute_node)
    graph.add_node("review", review_node)
    graph.add_node("report", report_node)
    graph.add_node("finalize", finalize_node)
    graph.add_edge(START, "plan")
    graph.add_edge("plan", "execute")
    graph.add_edge("execute", "review")
    graph.add_edge("review", "report")
    graph.add_edge("report", "finalize")
    graph.add_edge("finalize", END)
    return graph.compile(checkpointer=saver)
