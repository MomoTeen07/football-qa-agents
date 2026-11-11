"""Lance le bureau virtuel 2D en lecture seule.

Exemple :
    .venv\\Scripts\\python.exe scripts\\run_office.py
    .venv\\Scripts\\python.exe scripts\\run_office.py --mission-id 7e30889c18cd

Le script ne crée ni ne lance aucune mission : il sert uniquement le frontend
`office/` et le flux SSE des événements déjà enregistrés.
"""

from __future__ import annotations

import argparse
import sys
import webbrowser
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config import get_settings
from app.office.server import create_server
from app.store.sqlite_store import SqliteStore


def main() -> int:
    parser = argparse.ArgumentParser(description="Bureau virtuel 2D Football QA Agents")
    parser.add_argument("--host", default="127.0.0.1", help="boucle locale uniquement")
    parser.add_argument("--port", type=int, default=5180, help="port HTTP local")
    parser.add_argument(
        "--mission-id",
        default=None,
        help="mission à afficher (par défaut la plus récente)",
    )
    parser.add_argument(
        "--open",
        action="store_true",
        help="ouvre le navigateur après le démarrage",
    )
    args = parser.parse_args()

    settings = get_settings()
    store = SqliteStore(settings.mission_db_path)

    if args.mission_id and store.get_mission(args.mission_id) is None:
        print(f"Mission introuvable : {args.mission_id}", file=sys.stderr)
        return 2

    try:
        server = create_server(
            store,
            host=args.host,
            port=args.port,
            static_dir=PROJECT_ROOT / "office",
            allure_root=settings.allure_results_dir,
        )
    except (OSError, ValueError, FileNotFoundError) as exc:
        print(f"Bureau virtuel indisponible : {exc}", file=sys.stderr)
        return 1

    host, port = server.server_address[:2]
    url = f"http://{host}:{port}/"
    if args.mission_id:
        url += f"?mission_id={args.mission_id}"

    missions = store.list_missions()
    print(f"Bureau virtuel : {url}")
    print(f"Missions disponibles : {len(missions)}")
    if missions and not args.mission_id:
        print(f"Mission affichée : {missions[0].id} ({missions[0].status.value})")
    print("Ctrl+C pour arrêter. Aucune mission n'est lancée automatiquement.")

    if args.open:
        webbrowser.open(url)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nArrêt du bureau virtuel.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
