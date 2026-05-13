from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field


# ── Input models ──


class SubmitRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expression: str = Field(..., min_length=1, max_length=2000)
    settings: dict[str, Any] | None = None


# ── Output models ──


class SubmitResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["submitted", "queued", "failed"]
    job_id: str | None = None
    message: str = ""
    position_in_queue: int | None = None


class FactorMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sharpe: float | None = None
    turnover: float | None = None
    fitness: float | None = None
    mean_return: float | None = None
    drawdown: float | None = None
    margin: float | None = None
    pnl: float | None = None
    long_count: int | None = None
    short_count: int | None = None
    days: int | None = None
    checks: list[str] = []


class ActiveJob(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: str
    expression: str
    settings: dict[str, Any] = Field(default_factory=dict)
    status: Literal["running", "polling"]
    submitted_at: str
    wait_seconds: int | None = None


class CompletedJob(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: str
    expression: str
    settings: dict[str, Any] = Field(default_factory=dict)
    alpha_id: str | None = None
    metrics: FactorMetrics = Field(default_factory=FactorMetrics)
    status: Literal["completed", "failed"]
    error: str = ""
    completed_at: str = ""


class QueuedEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expression: str
    settings: dict[str, Any] = Field(default_factory=dict)
    position: int
    enqueued_at: str
    retry_count: int = 0


class PollResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    completed: list[CompletedJob] = []
    running: list[ActiveJob] = []
    queued: list[QueuedEntry] = []
    active_count: int = 0
    queued_count: int = 0
    connection_ok: bool = True


class QueueStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    active_count: int
    queued_count: int
    completed_count: int
    active_jobs: list[ActiveJob] = []
    queued_entries: list[QueuedEntry] = []
    expression_history_count: int = 0
