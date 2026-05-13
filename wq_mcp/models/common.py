from __future__ import annotations

from typing import Any, Generic, TypeVar
from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class ErrorResponse(BaseModel):
    """Standardized error response for ALL tool failures."""

    model_config = ConfigDict(extra="forbid")

    error: str
    error_code: str
    details: str | None = None
    status_code: int | None = None


class PaginatedResponse(BaseModel):
    """Wrapper for all list-returning tools. Enforces truncation."""

    model_config = ConfigDict(extra="forbid")

    items: list[Any]
    total_count: int
    returned_count: int
    has_more: bool
    page: int = 0
    page_size: int = 20


class TruncatedText(BaseModel):
    """Wrapper for long text content that may be truncated."""

    model_config = ConfigDict(extra="forbid")

    text: str
    full_length: int
    truncated_length: int
    is_truncated: bool
    truncated_note: str = ""
