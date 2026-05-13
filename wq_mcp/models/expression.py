from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ValidationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    valid: bool
    errors: list[str] = []
    warnings: list[str] = []


class FingerprintResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fingerprint: str
    expression: str
    operator_count: int = 0
    field_count: int = 0


class StructureDistanceResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    distance: float
    operator_overlap: float = 0.0
