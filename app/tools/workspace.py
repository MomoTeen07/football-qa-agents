from __future__ import annotations

import json
from pathlib import Path

from app.config import Settings
from app.security import ensure_within, validate_mission_id


def mission_workspace(settings: Settings, mission_id: str) -> Path:
    """Retourne le dossier de travail d'une mission, créé si nécessaire.

    L'identifiant est validé par la barrière unique (`app.security`) : aucun
    chemin ne peut sortir du dossier `workspace/missions`.
    """

    validate_mission_id(mission_id)
    base = Path(settings.workspace_dir) / "missions"
    path = ensure_within(base, mission_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_mission_text(
    settings: Settings,
    mission_id: str,
    relative_path: str,
    content: str,
) -> Path:
    base = mission_workspace(settings, mission_id)
    path = ensure_within(base, relative_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def write_mission_json(
    settings: Settings,
    mission_id: str,
    relative_path: str,
    payload: object,
) -> Path:
    base = mission_workspace(settings, mission_id)
    path = ensure_within(base, relative_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return path
