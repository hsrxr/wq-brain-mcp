from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from wq_mcp.core.queue_manager import FactorQueueManager
from wq_mcp.core.expression_service import ExpressionService
from wq_mcp.core.api_client import WqApiClient
from wq_mcp.models.common import ErrorResponse
from wq_mcp.config import DEFAULT_SETTINGS
from wq_mcp.logging_config import get_logger

logger = get_logger(__name__)

SIMILARITY_THRESHOLD = 0.3


def register_submission_tools(
    mcp: FastMCP,
    queue_mgr: FactorQueueManager,
    api_client: WqApiClient,
    expression_svc: ExpressionService | None = None,
) -> None:
    """Register all submission tools with dependency-injected queue manager."""

    @mcp.tool()
    def wq_submit_factor(expression: str, settings: dict | None = None) -> dict:
        """Submit a factor expression to WQ Brain for backtest SIMULATION only.

        This is a SIMULATION (backtest), NOT a formal competition submission.
        It runs IS simulation to get metrics (Sharpe, turnover, checks, etc.).
        Formal submission to competition (/alphas/{id}/submit) is PERMANENTLY BLOCKED
        in the API client and can never be called from MCP tools.

        If 3 simulations are already active, the expression is auto-queued and submitted
        when a slot frees up. Settings merge with defaults — only specify overrides.

        Use wq_validate_expression() first to avoid wasting a slot on an invalid expression.

        ⚠️  Auto-checks similarity against submitted competition alphas.
           If a similar factor is detected, a warning is included in the response.
           Call wq_check_submitted_similarity() beforehand to preview matches.

        Args:
            expression: The WQ FASTEXPR expression string
            settings: Optional overrides for simulation parameters
                      (instrumentType, region, universe, delay, decay, neutralization, truncation, etc.)

        Returns:
            {status: "submitted"|"queued"|"failed", job_id, message, position_in_queue,
             similarity_warning?: {...}}
        """
        try:
            merged_settings = dict(DEFAULT_SETTINGS)
            if settings:
                merged_settings.update(settings)

            # ── Pre-submit similarity check ──
            similarity_warning = None
            if expression_svc is not None:
                matches = expression_svc.check_submitted_similarity(
                    expression, threshold=SIMILARITY_THRESHOLD
                )
                if matches:
                    closest = matches[0]
                    similarity_warning = {
                        "similar": True,
                        "count": len(matches),
                        "closest_match": {
                            "id": closest["id"],
                            "name": closest["name"],
                            "distance": closest["distance"],
                        },
                        "message": (
                            f"This expression is similar to submitted alpha "
                            f"'{closest['name']}' ({closest['id']}) "
                            f"at distance={closest['distance']:.3f}. "
                            "Consider modifying to reduce self-correlation risk."
                        ),
                    }

            result = queue_mgr.submit(expression=expression, settings=merged_settings)

            if similarity_warning:
                result["similarity_warning"] = similarity_warning

            return result

        except Exception as e:
            logger.error("wq_submit_factor failed", exc_info=True)
            return ErrorResponse(error=str(e), error_code="SUBMISSION_ERROR").model_dump()

    @mcp.tool()
    def wq_poll_results() -> dict:
        """Poll all active simulations for completion.

        Automatically dequeues and submits waiting expressions when slots free up.
        Completed results since last poll are returned in the 'completed' list.

        Returns:
            {completed: [...], running: [...], queued: [...],
             active_count, queued_count, connection_ok}
        """
        try:
            return queue_mgr.poll()
        except Exception as e:
            logger.error("wq_poll_results failed", exc_info=True)
            return ErrorResponse(error=str(e), error_code="POLL_ERROR").model_dump()

    @mcp.tool()
    def wq_get_queue_status() -> dict:
        """Get the current submission queue status. Use this before submitting
        to check if there are free slots or how many are queued."""
        try:
            return queue_mgr.get_status()
        except Exception as e:
            logger.error("wq_get_queue_status failed", exc_info=True)
            return ErrorResponse(error=str(e), error_code="QUEUE_ERROR").model_dump()
