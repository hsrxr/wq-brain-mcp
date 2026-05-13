from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from wq_mcp.core.expression_service import ExpressionService
from wq_mcp.models.common import ErrorResponse
from wq_mcp.logging_config import get_logger

logger = get_logger(__name__)


def register_simcheck_tools(mcp: FastMCP, expression_svc: ExpressionService) -> None:
    """Register pre-submission similarity check tools."""

    @mcp.tool()
    def wq_check_submitted_similarity(expression: str, threshold: float = 0.3) -> dict:
        """Check if a new expression is too similar to already-submitted competition alphas.

        Computes structure_distance (normalized edit distance on operator sequences)
        against all 22 submitted competition alphas. If any are below the threshold,
        they are returned as warnings — submitting a highly similar factor risks
        homogeneity penalties and wasted simulation slots.

        Args:
            expression: The WQ FASTEXPR expression to check
            threshold: Similarity threshold (0-1). Lower = stricter.
                       Default 0.3. Try 0.2 for a stricter check, 0.4 for looser.

        Returns:
            {similar: bool, count: int, matches: [...], message: str}
            Each match: {id, name, distance, sharpe, fitness, grade, expression}
        """
        try:
            matches = expression_svc.check_submitted_similarity(expression, threshold)

            if not matches:
                return {
                    "similar": False,
                    "count": 0,
                    "matches": [],
                    "message": "No similar submitted alphas found — safe to test.",
                }

            closest = matches[0]
            return {
                "similar": True,
                "count": len(matches),
                "matches": matches,
                "message": (
                    f"Found {len(matches)} similar submitted alpha(s). "
                    f"Closest: {closest['name']} ({closest['id']}) "
                    f"at distance={closest['distance']:.3f}. "
                    "Consider modifying your expression to reduce similarity."
                ),
            }

        except Exception as e:
            logger.error("wq_check_submitted_similarity failed", exc_info=True)
            return ErrorResponse(error=str(e), error_code="SIMCHECK_ERROR").model_dump()
