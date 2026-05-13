from __future__ import annotations

from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class DatasetSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset_id: str
    field_count: int = 0
    description: str | None = None
    sample_fields: list[str] = []


class FieldDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    dataset: str
    description: str | None = None
    category: str | None = None
    subcategory: str | None = None
    region: str | None = None
    delay: int | None = Field(default=None, alias="delay")
    universe: str | None = None
    field_type: str | None = Field(default=None, alias="type")
    date_coverage: int | None = Field(default=None, alias="dateCoverage")
    coverage: int | None = None
    user_count: int | None = Field(default=None, alias="userCount")
    alpha_count: int | None = Field(default=None, alias="alphaCount")
    themes: list[str] = []


class OperatorSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    syntax: str
    summary: str | None = None
    level: str | None = None


class OperatorDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    syntax: str
    summary: str | None = None
    level: str | None = None
    detailed_explanation: str | None = None


class DatasetFieldList(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset_id: str
    fields: list[str]
    total_count: int
    returned_count: int
    has_more: bool


class SettingsSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_dict: dict[str, Any] = Field(default={}, alias="schema")
