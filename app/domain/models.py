from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

from pydantic import BaseModel, Field


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_id() -> str:
    return uuid4().hex[:12]


class MissionStatus(str, Enum):
    CREATED = "created"
    WAITING_APPROVAL = "waiting_approval"
    PLANNING = "planning"
    RUNNING = "running"
    REVIEWING = "reviewing"
    REPORTING = "reporting"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"
    SKIPPED = "skipped"


class Mission(BaseModel):
    id: str = Field(default_factory=new_id)
    instruction: str
    status: MissionStatus = MissionStatus.CREATED
    requires_approval: bool = False
    approval_reason: str | None = None
    report_path: str | None = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class Task(BaseModel):
    id: str = Field(default_factory=new_id)
    mission_id: str
    key: str
    agent: str
    title: str
    status: TaskStatus = TaskStatus.PENDING
    depends_on: list[str] = Field(default_factory=list)
    result: str | None = None
    evidence: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class Event(BaseModel):
    id: int | None = None
    mission_id: str
    type: str
    agent: str | None = None
    payload: dict = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utcnow)


class AgentResult(BaseModel):
    agent: str
    summary: str
    status: str = "completed"
    artifacts: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    anomalies: list[dict] = Field(default_factory=list)
    requires_approval: bool = False
    approval_reason: str | None = None
