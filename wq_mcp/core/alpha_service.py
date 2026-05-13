from __future__ import annotations

from typing import Any

from wq_mcp.core.api_client import WqApiClient, WqApiError
from wq_mcp.logging_config import get_logger

logger = get_logger(__name__)


class AlphaService:
    """Alpha analytics service — detail, correlations, recordsets, etc.

    All methods delegate to WqApiClient for HTTP and return raw dicts.
    """

    def __init__(self, api_client: WqApiClient) -> None:
        self._api = api_client

    def get_alpha_detail(self, alpha_id: str) -> dict[str, Any]:
        """Fetch full alpha detail including IS/OS metrics and checks."""
        return self._api.request("GET", f"/alphas/{alpha_id}").json()

    def get_self_correlation(self, alpha_id: str) -> list[dict[str, Any]]:
        """Fetch self-correlation list (other alphas correlated with this one).

        Returns list of {alpha_id, name, correlation, sharpe, returns, turnover, fitness, margin}.
        """
        resp = self._api.request("GET", f"/alphas/{alpha_id}/correlations/self")
        data = resp.json()
        schema = data.get("schema", {})
        props = [p["name"] for p in schema.get("properties", [])]
        records = data.get("records", [])

        results = []
        for row in records:
            entry = dict(zip(props, row))
            results.append(entry)
        return results

    def get_records(self, alpha_id: str, record_type: str = "pnl") -> dict[str, Any]:
        """Fetch time-series records for an alpha.

        record_type: pnl, daily-pnl, yearly-stats
        """
        resp = self._api.request("GET", f"/alphas/{alpha_id}/recordsets/{record_type}")
        return resp.json()

    def list_my_alphas(
        self,
        status_filter: str | None = None,
        limit: int = 10,
        offset: int = 0,
    ) -> dict[str, Any]:
        """List user's own alphas with optional status filter.

        status_filter examples: "UNSUBMITTED", "!UNSUBMITTED" (submitted only), None (all).
        """
        params = {"limit": min(limit, 100), "offset": offset}
        if status_filter:
            params["status"] = status_filter
        resp = self._api.request("GET", "/users/self/alphas", params=params)
        return resp.json()

    def get_competition_info(self, competition_id: str) -> dict[str, Any]:
        """Fetch competition details including scoring type and team info."""
        resp = self._api.request("GET", f"/competitions/{competition_id}")
        return resp.json()

    def list_competition_alphas(
        self, competition_id: str, limit: int = 10, offset: int = 0
    ) -> dict[str, Any]:
        """List user's alphas submitted to a specific competition."""
        params = {"limit": min(limit, 100), "offset": offset}
        resp = self._api.request("GET", f"/competitions/{competition_id}/alphas", params=params)
        return resp.json()

    def get_my_team(self) -> dict[str, Any] | None:
        """Fetch current user's team info from /users/self/teams."""
        resp = self._api.request("GET", "/users/self/teams")
        data = resp.json()
        results = data.get("results", [])
        return results[0] if results else None
