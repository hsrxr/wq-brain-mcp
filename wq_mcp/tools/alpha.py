from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from wq_mcp.core.alpha_service import AlphaService
from wq_mcp.models.common import ErrorResponse
from wq_mcp.logging_config import get_logger

logger = get_logger(__name__)


def register_alpha_tools(mcp: FastMCP, alpha_svc: AlphaService) -> None:
    """Register alpha analytics tools (no submission — read-only)."""

    VALID_RECORDS = {"pnl", "daily-pnl", "yearly-stats"}

    @mcp.tool()
    def wq_get_alpha_detail(alpha_id: str) -> dict:
        """Fetch full alpha detail: IS/OS metrics, risk checks, settings, expression.

        Args:
            alpha_id: The alpha ID (e.g. "58LR8RZJ")

        Returns:
            Full alpha detail including is.sharpe, is.turnover, is.fitness,
            is.checks (risk checks), settings, expression, stage, grade.
        """
        try:
            return alpha_svc.get_alpha_detail(alpha_id)
        except Exception as e:
            logger.error("wq_get_alpha_detail failed", exc_info=True)
            return ErrorResponse(error=str(e), error_code="ALPHA_DETAIL_ERROR").model_dump()

    @mcp.tool()
    def wq_get_self_correlation(alpha_id: str) -> list:
        """Fetch self-correlation list: other alphas correlated with this one.

        Use this to check if your alpha is too similar to existing ones
        (high correlation = likely homogeneity penalty).

        Args:
            alpha_id: The alpha ID to check

        Returns:
            List of {alpha_id, name, correlation, sharpe, returns, turnover, fitness, margin}
            sorted by correlation (highest first).
        """
        try:
            return alpha_svc.get_self_correlation(alpha_id)
        except Exception as e:
            logger.error("wq_get_self_correlation failed", exc_info=True)
            return ErrorResponse(error=str(e), error_code="CORRELATION_ERROR").model_dump()

    @mcp.tool()
    def wq_get_alpha_records(alpha_id: str, record_type: str = "pnl") -> dict:
        """Fetch time-series records for an alpha.

        Args:
            alpha_id: The alpha ID
            record_type: One of "pnl" (daily PnL), "daily-pnl", "yearly-stats"
                         yearly-stats gives per-year breakdown of sharpe/pnl/turnover

        Returns:
            {schema: {properties: [{name, title, type}]}, records: [[...], ...]}
        """
        if record_type not in VALID_RECORDS:
            return ErrorResponse(
                error=f"Invalid record_type '{record_type}'. Must be one of: {', '.join(sorted(VALID_RECORDS))}",
                error_code="INVALID_RECORD_TYPE",
            ).model_dump()
        try:
            return alpha_svc.get_records(alpha_id, record_type)
        except Exception as e:
            logger.error("wq_get_alpha_records failed", exc_info=True)
            return ErrorResponse(error=str(e), error_code="RECORDS_ERROR").model_dump()

    @mcp.tool()
    def wq_list_my_alphas(status_filter: str | None = None, limit: int = 10, offset: int = 0) -> dict:
        """List your own alphas with optional status filter.

        Args:
            status_filter: Optional status filter — "UNSUBMITTED" for simulated only,
                          "!UNSUBMITTED" for submitted only, None for all
            limit: Max results (default 10, max 100)
            offset: Pagination offset

        Returns:
            Paginated results with count, next, previous, results[]
        """
        try:
            return alpha_svc.list_my_alphas(status_filter, limit, offset)
        except Exception as e:
            logger.error("wq_list_my_alphas failed", exc_info=True)
            return ErrorResponse(error=str(e), error_code="ALPHA_LIST_ERROR").model_dump()

    @mcp.tool()
    def wq_get_competition_info(competition_id: str = "challenge") -> dict:
        """Fetch competition details.

        Args:
            competition_id: Default "challenge", also "IQC2026S1" for IQC stage 1

        Returns:
            Competition info including name, status, scoring type, team details
        """
        try:
            return alpha_svc.get_competition_info(competition_id)
        except Exception as e:
            logger.error("wq_get_competition_info failed", exc_info=True)
            return ErrorResponse(error=str(e), error_code="COMPETITION_ERROR").model_dump()

    @mcp.tool()
    def wq_list_competition_alphas(competition_id: str = "challenge", limit: int = 10, offset: int = 0) -> dict:
        """List your alphas submitted to a specific competition.

        Args:
            competition_id: "challenge" or "IQC2026S1"
            limit: Max results (max 100)
            offset: Pagination offset

        Returns:
            Paginated list of alphas in the competition with their metrics
        """
        try:
            return alpha_svc.list_competition_alphas(competition_id, limit, offset)
        except Exception as e:
            logger.error("wq_list_competition_alphas failed", exc_info=True)
            return ErrorResponse(error=str(e), error_code="COMP_ALPHAS_ERROR").model_dump()

    @mcp.tool()
    def wq_get_my_team() -> dict:
        """Fetch your current team info (IQC team, members, submission count)."""
        try:
            team = alpha_svc.get_my_team()
            if team:
                return team
            return {"message": "No team found"}
        except Exception as e:
            logger.error("wq_get_my_team failed", exc_info=True)
            return ErrorResponse(error=str(e), error_code="TEAM_ERROR").model_dump()
