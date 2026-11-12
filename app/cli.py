from __future__ import annotations

import argparse
import sys
from pathlib import Path

from rich.console import Console
from rich.table import Table

from app.config import get_settings
from app.orchestrator.doctor import diagnose, summarize
from app.orchestrator.manager import Manager
from app.security import validate_mission_id
from app.store.sqlite_store import SqliteStore, StorageError

# La console Windows héritée utilise parfois cp1252. Les rapports contiennent
# des caractères UTF-8 (flèches, accents) : on force une sortie UTF-8.
for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8")

console = Console()


def mission_id_argument(value: str) -> str:
    """Valide un identifiant fourni en ligne de commande."""

    try:
        return validate_mission_id(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def build_manager() -> Manager:
    return Manager(get_settings())


def cmd_create(args: argparse.Namespace) -> int:
    manager = build_manager()
    try:
        mission = manager.create_mission(args.instruction)
        console.print(f"Mission créée : [bold]{mission.id}[/bold]")
        if mission.requires_approval:
            console.print(
                f"[yellow]Approbation requise :[/yellow] {mission.approval_reason}"
            )
        return 0
    finally:
        manager.close()


def cmd_run(args: argparse.Namespace) -> int:
    manager = build_manager()
    try:
        mission = manager.run_mission(args.mission_id, approved=args.approve)
        console.print(f"Statut : [bold]{mission.status.value}[/bold]")
        if mission.report_path:
            console.print(f"Rapport : {mission.report_path}")
        return 0
    finally:
        manager.close()


def cmd_approve(args: argparse.Namespace) -> int:
    manager = build_manager()
    try:
        mission = manager.approve_mission(args.mission_id)
        console.print(f"Statut : [bold]{mission.status.value}[/bold]")
        if mission.report_path:
            console.print(f"Rapport : {mission.report_path}")
        return 0
    finally:
        manager.close()


def cmd_status(args: argparse.Namespace) -> int:
    manager = build_manager()
    try:
        data = manager.status(args.mission_id)
        mission = data["mission"]
        console.print(f"Mission {mission.id} — {mission.status.value}")
        console.print(f"Instruction : {mission.instruction}")
        if mission.report_path:
            console.print(f"Rapport : {mission.report_path}")

        table = Table(title="Tâches")
        table.add_column("Agent")
        table.add_column("Titre")
        table.add_column("Statut")
        for task in data["tasks"]:
            table.add_row(task.agent, task.title, task.status.value)
        console.print(table)

        events = Table(title="Événements")
        events.add_column("Type")
        events.add_column("Agent")
        events.add_column("Détail")
        for event in data["events"]:
            events.add_row(
                event.type,
                event.agent or "-",
                str(event.payload)[:120],
            )
        console.print(events)
        return 0
    finally:
        manager.close()


def cmd_events(args: argparse.Namespace) -> int:
    manager = build_manager()
    try:
        for event in manager.get_events(args.mission_id):
            console.print(
                f"[bold]{event.type}[/bold] "
                f"({event.agent or '-'}) {event.payload}"
            )
        return 0
    finally:
        manager.close()


def cmd_list(args: argparse.Namespace) -> int:
    manager = build_manager()
    try:
        table = Table(title="Missions")
        table.add_column("ID")
        table.add_column("Statut")
        table.add_column("Instruction")
        for mission in manager.list_missions():
            table.add_row(
                mission.id,
                mission.status.value,
                mission.instruction[:80],
            )
        console.print(table)
        return 0
    finally:
        manager.close()


def cmd_demo(args: argparse.Namespace) -> int:
    manager = build_manager()
    try:
        mission = manager.create_mission(
            "Lance une campagne complète de tests API et UI sur l'application."
        )
        console.print(f"Mission de démonstration : [bold]{mission.id}[/bold]")
        mission = manager.run_mission(mission.id)
        console.print(f"Statut final : [bold]{mission.status.value}[/bold]")
        if mission.report_path:
            console.print(f"Rapport : {mission.report_path}")
        return 0
    finally:
        manager.close()


def cmd_doctor(args: argparse.Namespace) -> int:
    settings = get_settings()
    path = Path(settings.mission_db_path)
    if not path.is_file():
        console.print(f"Base de pilotage absente : [bold]{path}[/bold]")
        console.print("Aucune mission enregistrée. Rien n'a été modifié.")
        return 0
    try:
        store = SqliteStore(path, read_only=True)
    except StorageError as exc:
        console.print(f"[red]{exc}[/red]")
        return 1

    report = diagnose(store)
    console.print(f"[bold]{summarize(report)}[/bold]")
    console.print(f"Base : {path} (lecture seule)")

    if report["missions_by_status"]:
        statuses = Table(title="Missions par statut")
        statuses.add_column("Statut")
        statuses.add_column("Nombre", justify="right")
        for status, count in report["missions_by_status"].items():
            statuses.add_row(status, str(count))
        console.print(statuses)

    if report["stale_missions"]:
        stale = Table(title="Missions non terminales (reprise possible)")
        stale.add_column("Mission")
        stale.add_column("Statut")
        stale.add_column("Tâches")
        stale.add_column("Actives")
        stale.add_column("Dernière mise à jour")
        for item in report["stale_missions"]:
            stale.add_row(
                item["id"],
                item["status"],
                str(item["tasks"]),
                str(item["active_tasks"]),
                item["updated_at"],
            )
        console.print(stale)

    if report["inconsistent_missions"]:
        problems = Table(title="Incohérences")
        problems.add_column("Mission")
        problems.add_column("Statut")
        problems.add_column("Détail")
        for item in report["inconsistent_missions"]:
            problems.add_row(item["id"], item["status"], item["reason"])
        console.print(problems)

    for item in report["duplicate_task_keys"]:
        console.print(
            f"[yellow]Clé dupliquée[/yellow] {item['mission_id']} / "
            f"{item['key']} ({item['count']} occurrences)"
        )
    if report["orphan_tasks"]:
        console.print(f"[yellow]Tâches orphelines :[/yellow] {report['orphan_tasks']}")
    if report["orphan_events"]:
        console.print(f"[yellow]Événements orphelins :[/yellow] {report['orphan_events']}")
    console.print("Diagnostic en lecture seule : aucune réparation automatique.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="football-qa-agents",
        description="Manager QA local — fonctionnement uniquement à la demande.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    create = subparsers.add_parser("create", help="Créer une mission")
    create.add_argument("instruction", help="Instruction en langage naturel")
    create.set_defaults(func=cmd_create)

    run = subparsers.add_parser("run", help="Exécuter une mission")
    run.add_argument("mission_id", type=mission_id_argument)
    run.add_argument(
        "--approve",
        action="store_true",
        help="Approuver explicitement les actions sensibles",
    )
    run.set_defaults(func=cmd_run)

    approve = subparsers.add_parser("approve", help="Approuver et exécuter")
    approve.add_argument("mission_id", type=mission_id_argument)
    approve.set_defaults(func=cmd_approve)

    status = subparsers.add_parser("status", help="Afficher une mission")
    status.add_argument("mission_id", type=mission_id_argument)
    status.set_defaults(func=cmd_status)

    events = subparsers.add_parser("events", help="Afficher le journal d'événements")
    events.add_argument("mission_id", type=mission_id_argument)
    events.set_defaults(func=cmd_events)

    list_cmd = subparsers.add_parser("list", help="Lister les missions")
    list_cmd.set_defaults(func=cmd_list)

    demo = subparsers.add_parser("demo", help="Créer et exécuter une mission de démonstration")
    demo.set_defaults(func=cmd_demo)

    doctor = subparsers.add_parser(
        "doctor",
        help="Diagnostiquer la base locale en lecture seule",
    )
    doctor.set_defaults(func=cmd_doctor)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
