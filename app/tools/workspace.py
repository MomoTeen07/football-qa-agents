from __future__ import annotations

import json
from pathlib import Path

from app.config import Settings


def mission_workspace(settings: Settings, mission_id: str) -> Path:
    """Retourne le dossier de travail d'une mission, créé si nécessaire."""
    path = Path(settings.workspace_dir) / "missions" / mission_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_mission_text(
    settings: Settings,
    mission_id: str,
    relative_path: str,
    content: str,
) -> Path:
    path = mission_workspace(settings, mission_id) / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def write_mission_json(
    settings: Settings,
    mission_id: str,
    relative_path: str,
    payload: object,
) -> Path:
    path = mission_workspace(settings, mission_id) / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return path
