from __future__ import annotations

import json
from pathlib import Path

from app.config import Settings
from app.security import ensure_within, validate_mission_id


def mission_workspace(settings: Settings, mission_id: str) -> Path:
    """Retourne le dossier de travail d'une mission, créé si nécessaire.

    L'identifiant est validé et le chemin reste confiné dans
    ``workspace/missions``.
    """

    safe_id = validate_mission_id(mission_id)
    missions_dir = Path(settings.workspace_dir) / "missions"
    path = ensure_within(missions_dir, missions_dir / safe_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _mission_path(
    settings: Settings,
    mission_id: str,
    relative_path: str,
) -> Path:
    mission_dir = mission_workspace(settings, mission_id)
    return ensure_within(mission_dir, mission_dir / relative_path)


def write_mission_text(
    settings: Settings,
    mission_id: str,
    relative_path: str,
    content: str,
) -> Path:
    path = _mission_path(settings, mission_id, relative_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def write_mission_json(
    settings: Settings,
    mission_id: str,
    relative_path: str,
    payload: object,
) -> Path:
    path = _mission_path(settings, mission_id, relative_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return path
