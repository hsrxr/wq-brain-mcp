from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from wq_mcp.core.expression_service import ExpressionService
from wq_mcp.models.common import ErrorResponse
from wq_mcp.logging_config import get_logger

logger = get_logger(__name__)


def register_expression_tools(mcp: FastMCP, svc: ExpressionService) -> None:
    """Register all expression tools with dependency-injected service."""

    @mcp.tool()
    def wq_validate_expression(expression: str, dataset_id: str = "") -> dict:
        """Validate a WQ FASTEXPR expression. Returns {valid, errors, warnings}.
        Always call this before submitting a factor to avoid wasting simulation slots."""
        try:
            return svc.validate(expression, dataset_id=dataset_id or None)
        except Exception as e:
            logger.error("wq_validate_expression failed", exc_info=True)
            return ErrorResponse(error=str(e), error_code="VALIDATION_ERROR").model_dump()

    @mcp.tool()
    def wq_expression_fingerprint(expression: str) -> dict:
        """Compute structural hash of an expression (operator-sequence based MD5).
        Use this to check if Claude has already submitted an expression with the same operator structure."""
        try:
            fp = svc.fingerprint(expression)
            op_count = svc.extract_operator_count(expression)
            field_count = svc.extract_field_count(expression)
            return {
                "fingerprint": fp,
                "expression": expression,
                "operator_count": op_count,
                "field_count": field_count,
            }
        except Exception as e:
            logger.error("wq_expression_fingerprint failed", exc_info=True)
            return ErrorResponse(error=str(e), error_code="FINGERPRINT_ERROR").model_dump()

    @mcp.tool()
    def wq_field_fingerprint(expression: str) -> dict:
        """Compute hash based on the data fields used in an expression."""
        try:
            fp = svc.field_based_fingerprint(expression)
            return {"fingerprint": fp, "expression": expression}
        except Exception as e:
            logger.error("wq_field_fingerprint failed", exc_info=True)
            return ErrorResponse(error=str(e), error_code="FINGERPRINT_ERROR").model_dump()

    @mcp.tool()
    def wq_expression_distance(expr_a: str, expr_b: str) -> dict:
        """Compute normalized edit distance [0,1] between two expressions' operator structures.
        0.0 = identical structure, 1.0 = completely different operators."""
        try:
            dist = svc.structure_distance(expr_a, expr_b)
            return {"distance": round(dist, 4), "expr_a": expr_a[:80], "expr_b": expr_b[:80]}
        except Exception as e:
            logger.error("wq_expression_distance failed", exc_info=True)
            return ErrorResponse(error=str(e), error_code="FINGERPRINT_ERROR").model_dump()

    @mcp.tool()
    def wq_check_named_params(expression: str) -> dict:
        """Check for known named-parameter pitfalls in WQ expressions.
        Catches: winsorize without std=, ts_regression without rettype=, group_backfill without std="""
        try:
            warnings = svc.check_named_params(expression)
            return {"expression": expression, "warnings": warnings, "has_issues": len(warnings) > 0}
        except Exception as e:
            logger.error("wq_check_named_params failed", exc_info=True)
            return ErrorResponse(error=str(e), error_code="VALIDATION_ERROR").model_dump()
