from __future__ import annotations

import argparse
import sys

from rich.console import Console
from rich.table import Table

from app.config import get_settings
from app.orchestrator.manager import Manager
from app.security import validate_mission_id

# La console Windows héritée utilise parfois cp1252. Les rapports contiennent
# des caractères UTF-8 (flèches, accents) : on force une sortie UTF-8.
for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8")

console = Console()


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
    try:
        mission_id = validate_mission_id(args.mission_id)
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        return 2
    manager = build_manager()
    try:
        mission = manager.run_mission(mission_id, approved=args.approve)
        console.print(f"Statut : [bold]{mission.status.value}[/bold]")
        if mission.report_path:
            console.print(f"Rapport : {mission.report_path}")
        return 0
    finally:
        manager.close()


def cmd_approve(args: argparse.Namespace) -> int:
    try:
        mission_id = validate_mission_id(args.mission_id)
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        return 2
    manager = build_manager()
    try:
        mission = manager.approve_mission(mission_id)
        console.print(f"Statut : [bold]{mission.status.value}[/bold]")
        if mission.report_path:
            console.print(f"Rapport : {mission.report_path}")
        return 0
    finally:
        manager.close()


def cmd_status(args: argparse.Namespace) -> int:
    try:
        mission_id = validate_mission_id(args.mission_id)
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        return 2
    manager = build_manager()
    try:
        data = manager.status(mission_id)
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
    try:
        mission_id = validate_mission_id(args.mission_id)
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        return 2
    manager = build_manager()
    try:
        for event in manager.get_events(mission_id):
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
    run.add_argument("mission_id")
    run.add_argument(
        "--approve",
        action="store_true",
        help="Approuver explicitement les actions sensibles",
    )
    run.set_defaults(func=cmd_run)

    approve = subparsers.add_parser("approve", help="Approuver et exécuter")
    approve.add_argument("mission_id")
    approve.set_defaults(func=cmd_approve)

    status = subparsers.add_parser("status", help="Afficher une mission")
    status.add_argument("mission_id")
    status.set_defaults(func=cmd_status)

    events = subparsers.add_parser("events", help="Afficher le journal d'événements")
    events.add_argument("mission_id")
    events.set_defaults(func=cmd_events)

    list_cmd = subparsers.add_parser("list", help="Lister les missions")
    list_cmd.set_defaults(func=cmd_list)

    demo = subparsers.add_parser("demo", help="Créer et exécuter une mission de démonstration")
    demo.set_defaults(func=cmd_demo)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
