from __future__ import annotations

from typing import TypedDict


class MissionState(TypedDict, total=False):
    mission_id: str
    instruction: str
    plan: list[dict]
    task_ids: dict[str, str]
    status: str
    report: str
    error: str
