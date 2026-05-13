from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from wq_mcp.core.research_service import ResearchService
from wq_mcp.models.common import ErrorResponse, PaginatedResponse, TruncatedText
from wq_mcp.logging_config import get_logger

logger = get_logger(__name__)


def register_research_tools(mcp: FastMCP, svc: ResearchService) -> None:
    """Register all research tools with dependency-injected service."""

    @mcp.tool()
    def wq_list_datasets(page: int = 0, page_size: int = 20) -> dict:
        """List all locally cached WQ datasets with field counts (paginated)."""
        try:
            datasets = svc.list_datasets()
            total = len(datasets)
            start = page * page_size
            end = start + page_size
            paged = datasets[start:end]
            return PaginatedResponse(
                items=paged,
                total_count=total,
                returned_count=len(paged),
                has_more=end < total,
                page=page,
                page_size=page_size,
            ).model_dump()
        except Exception as e:
            logger.error("wq_list_datasets failed", exc_info=True)
            return ErrorResponse(error=str(e), error_code="RESEARCH_ERROR").model_dump()

    @mcp.tool()
    def wq_get_dataset_detail(dataset_id: str) -> dict:
        """Get detailed information about a specific dataset."""
        try:
            result = svc.get_dataset_detail(dataset_id)
            if result is None:
                return ErrorResponse(error=f"Dataset '{dataset_id}' not found", error_code="NOT_FOUND").model_dump()
            return result
        except Exception as e:
            logger.error("wq_get_dataset_detail failed", exc_info=True)
            return ErrorResponse(error=str(e), error_code="RESEARCH_ERROR").model_dump()

    @mcp.tool()
    def wq_list_fields(dataset_id: str, page: int = 0, page_size: int = 50) -> dict:
        """List all field IDs in a dataset (paginated)."""
        try:
            fields = svc.list_fields(dataset_id)
            total = len(fields)
            start = page * page_size
            end = start + page_size
            paged = fields[start:end]
            return PaginatedResponse(
                items=[{"field_id": f} for f in paged],
                total_count=total,
                returned_count=len(paged),
                has_more=end < total,
                page=page,
                page_size=page_size,
            ).model_dump()
        except Exception as e:
            logger.error("wq_list_fields failed", exc_info=True)
            return ErrorResponse(error=str(e), error_code="RESEARCH_ERROR").model_dump()

    @mcp.tool()
    def wq_get_field_detail(field_id: str, dataset_id: str) -> dict:
        """Get complete metadata for a specific data field."""
        try:
            result = svc.get_field_detail(field_id, dataset_id)
            if result is None:
                return ErrorResponse(
                    error=f"Field '{field_id}' not found in dataset '{dataset_id}'",
                    error_code="NOT_FOUND",
                ).model_dump()
            return result
        except Exception as e:
            logger.error("wq_get_field_detail failed", exc_info=True)
            return ErrorResponse(error=str(e), error_code="RESEARCH_ERROR").model_dump()

    @mcp.tool()
    def wq_list_all_operators(page: int = 0, page_size: int = 20) -> dict:
        """List all 51 WQ operators with name, syntax, and summary (paginated)."""
        try:
            operators = svc.list_all_operators()
            total = len(operators)
            start = page * page_size
            end = start + page_size
            paged = operators[start:end]
            return PaginatedResponse(
                items=paged,
                total_count=total,
                returned_count=len(paged),
                has_more=end < total,
                page=page,
                page_size=page_size,
            ).model_dump()
        except Exception as e:
            logger.error("wq_list_all_operators failed", exc_info=True)
            return ErrorResponse(error=str(e), error_code="RESEARCH_ERROR").model_dump()

    @mcp.tool()
    def wq_search_operators(keyword: str, page: int = 0, page_size: int = 20) -> dict:
        """Search WQ operators by keyword in name, syntax, summary, or explanation."""
        try:
            operators = svc.search_operators(keyword)
            total = len(operators)
            start = page * page_size
            end = start + page_size
            paged = operators[start:end]
            return PaginatedResponse(
                items=paged,
                total_count=total,
                returned_count=len(paged),
                has_more=end < total,
                page=page,
                page_size=page_size,
            ).model_dump()
        except Exception as e:
            logger.error("wq_search_operators failed", exc_info=True)
            return ErrorResponse(error=str(e), error_code="RESEARCH_ERROR").model_dump()

    @mcp.tool()
    def wq_get_operator_detail(name: str) -> dict:
        """Get full specification for one WQ operator by name."""
        try:
            result = svc.get_operator_detail(name)
            if result is None:
                return ErrorResponse(error=f"Operator '{name}' not found", error_code="NOT_FOUND").model_dump()
            return result
        except Exception as e:
            logger.error("wq_get_operator_detail failed", exc_info=True)
            return ErrorResponse(error=str(e), error_code="RESEARCH_ERROR").model_dump()

    @mcp.tool()
    def wq_get_setting_schema() -> dict:
        """Get the full simulation settings schema with defaults and descriptions."""
        try:
            return svc.get_setting_schema()
        except Exception as e:
            logger.error("wq_get_setting_schema failed", exc_info=True)
            return ErrorResponse(error=str(e), error_code="SETTINGS_ERROR").model_dump()

    @mcp.tool()
    def wq_get_setting_detail(name: str) -> dict:
        """Get detail for one simulation setting parameter."""
        try:
            result = svc.get_setting_detail(name)
            if result is None:
                return ErrorResponse(error=f"Setting '{name}' not found", error_code="NOT_FOUND").model_dump()
            return result
        except Exception as e:
            logger.error("wq_get_setting_detail failed", exc_info=True)
            return ErrorResponse(error=str(e), error_code="SETTINGS_ERROR").model_dump()
