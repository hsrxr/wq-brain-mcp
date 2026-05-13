from __future__ import annotations

import threading
import time
from typing import Any

import requests
from requests.auth import HTTPBasicAuth

from wq_mcp.config import API_BASE, RELOGIN_INTERVAL
from wq_mcp.logging_config import get_logger

logger = get_logger(__name__)


# ── Custom exceptions (pure business, no MCP dependency) ──


class WqApiError(Exception):
    """Base exception for all WQ API errors. Never leaks PII into message."""

    def __init__(self, message: str, status_code: int | None = None, details: str | None = None):
        self.status_code = status_code
        self.details = details
        super().__init__(message)


class AuthError(WqApiError):
    """Authentication failure: 401, 403, or missing credentials."""


class RateLimitError(WqApiError):
    """HTTP 429 with retry_after."""

    def __init__(self, retry_after: int, message: str = "Rate limited by WQ API"):
        self.retry_after = retry_after
        super().__init__(message, status_code=429)


class ValidationError(WqApiError):
    """HTTP 400: expression rejected by API."""


# ── WQ API stats helpers (extracted from wq_tools.py _extract_metrics) ──


def _extract_metrics(alpha_detail: dict) -> dict[str, Any]:
    """Extract performance metrics from WQ alpha detail response.

    Handles missing or None fields gracefully — returns None for each.
    The WQ API returns metrics under 'is', 'statistics', or 'stats' keys.
    """
    # Determine which key holds the metrics
    metrics_source = alpha_detail.get("is") or alpha_detail.get("statistics") or alpha_detail.get("stats") or {}

    if not isinstance(metrics_source, dict):
        metrics_source = {}

    def _safe_float(key: str) -> float | None:
        v = metrics_source.get(key)
        if v is None:
            return None
        try:
            return float(v)
        except (ValueError, TypeError):
            return None

    def _safe_int(key: str) -> int | None:
        v = metrics_source.get(key)
        if v is None:
            return None
        try:
            return int(v)
        except (ValueError, TypeError):
            return None

    return {
        "sharpe": _safe_float("sharpe"),
        "turnover": _safe_float("turnover"),
        "fitness": _safe_float("fitness"),
        "mean_return": _safe_float("meanReturn"),
        "drawdown": _safe_float("drawdown"),
        "margin": _safe_float("margin"),
        "pnl": _safe_float("pnl"),
        "long_count": _safe_int("longCount"),
        "short_count": _safe_int("shortCount"),
        "days": _safe_int("days"),
        "checks": metrics_source.get("checks", []),
    }


# ── WQ API Client ──


class WqApiClient:
    """Thread-safe WQ Brain API HTTP client with periodic relogin.

    Knows NOTHING about MCP. Handles all HTTP communication, auth, and retry.
    Business methods return raw dicts (Pydantic validation happens in service/tool layer).
    """

    def __init__(self, username: str, password: str, proxies: dict[str, str] | None = None):
        self._username = username
        self._password = password
        self._proxies = proxies
        self._session: requests.Session | None = None
        self._last_login: float = 0.0
        self._lock = threading.Lock()

    # ── Session management ──

    def login(self) -> None:
        """Authenticate with WQ Brain API. Raises AuthError on failure."""
        session = requests.Session()
        session.auth = HTTPBasicAuth(self._username, self._password)
        if self._proxies:
            session.proxies.update(self._proxies)

        url = f"{API_BASE}/authentication"
        try:
            resp = session.post(url, timeout=30)
        except requests.exceptions.RequestException as e:
            raise WqApiError(f"Network error during login: {e}", details=str(e)) from e

        if resp.status_code == 201:
            self._session = session
            self._last_login = time.monotonic()
            logger.info("WQ Brain API login successful")
        elif resp.status_code == 401:
            raise AuthError("Invalid WQ Brain credentials (HTTP 401)")
        elif resp.status_code == 403:
            raise AuthError("WQ Brain access denied (HTTP 403)")
        else:
            raise WqApiError(
                f"Login failed with HTTP {resp.status_code}",
                status_code=resp.status_code,
                details=resp.text[:500],
            )

    def ensure_session(self) -> requests.Session:
        """Return valid session, re-logging if needed. Thread-safe."""
        with self._lock:
            elapsed = time.monotonic() - self._last_login
            if self._session is None or elapsed > RELOGIN_INTERVAL:
                logger.info("Session expired or missing, re-logging...")
                self.login()
            return self._session  # type: ignore[return-value]

    def request(self, method: str, path: str, **kwargs: Any) -> requests.Response:
        """Unified HTTP request with auto-relogin on 401/403, rate-limit detection.

        Raises:
            AuthError: on 401/403 after relogin retry
            RateLimitError: on 429
            ValidationError: on 400
            WqApiError: on other failures
        """
        # 🚫 BLOCKED: alpha submission (formal submit to competition).
        # Simulation (POST /simulations) is fine; /alphas/{id}/submit is FORBIDDEN.
        if "/submit" in path:
            raise WqApiError(
                "Alpha submission is disabled. Simulation (wq_submit_factor) is allowed, "
                "but formal submission to competition is blocked by policy.",
                status_code=403,
            )

        session = self.ensure_session()
        url = f"{API_BASE}{path}" if not path.startswith("http") else path

        try:
            resp = session.request(method, url, timeout=kwargs.pop("timeout", 120), **kwargs)
        except requests.exceptions.RequestException as e:
            raise WqApiError(f"Network error: {e}", details=str(e)) from e

        # 401/403 — force relogin and retry once
        if resp.status_code in (401, 403):
            logger.warning("Got HTTP %d, forcing relogin and retry...", resp.status_code)
            with self._lock:
                self._session = None
            session = self.ensure_session()
            try:
                resp = session.request(method, url, timeout=120, **kwargs)
            except requests.exceptions.RequestException as e:
                raise WqApiError(f"Network error on retry: {e}", details=str(e)) from e

            if resp.status_code in (401, 403):
                raise AuthError(
                    f"WQ API access denied after relogin (HTTP {resp.status_code})",
                    status_code=resp.status_code,
                    details=resp.text[:500],
                )

        # 429 — rate limit
        if resp.status_code == 429:
            retry_after = 60
            try:
                retry_after = int(resp.headers.get("Retry-After", "60"))
            except (ValueError, TypeError):
                pass
            raise RateLimitError(retry_after=retry_after)

        # 400 — bad request (e.g. invalid expression)
        if resp.status_code == 400:
            raise ValidationError(
                "Expression rejected by WQ API",
                status_code=400,
                details=resp.text[:1000],
            )

        # Other 4xx
        if 400 <= resp.status_code < 500:
            raise WqApiError(
                f"WQ API client error (HTTP {resp.status_code})",
                status_code=resp.status_code,
                details=resp.text[:500],
            )

        # 5xx
        if resp.status_code >= 500:
            raise WqApiError(
                f"WQ API server error (HTTP {resp.status_code})",
                status_code=resp.status_code,
                details=resp.text[:500],
            )

        return resp

    # ── Business API methods ──

    def submit_simulation(self, expression: str, settings: dict[str, Any]) -> dict[str, Any]:
        """Submit a factor expression for simulation.

        Returns:
            dict with keys: job_id (str), location_url (str)
        """
        # Build payload — WQ Brain API expects:
        #   {"type": "regular", "settings": {..., "language": "FASTEXPR"}, "regular": "<expr>"}
        payload_settings = dict(settings) if settings else {}
        payload_settings.setdefault("language", "FASTEXPR")
        payload_settings.setdefault("visualization", False)
        payload = {
            "type": "regular",
            "settings": payload_settings,
            "regular": expression,
        }
        resp = self.request("POST", "/simulations", json=payload)
        # Expect 201 with Location header
        location = resp.headers.get("Location") or resp.headers.get("location", "")
        # Extract job_id from URL (last path segment)
        job_id = location.rstrip("/").split("/")[-1] if location else ""
        return {"job_id": job_id, "location_url": location}

    def poll_simulation(self, job_url: str) -> dict[str, Any]:
        """Poll a simulation job for completion status.

        Returns:
            dict with keys: status (str), retry_after (int|None), alpha_id (str|None)
        """
        resp = self.request("GET", job_url)

        # Finished: HTTP 200 with no Retry-After header > 0
        retry_after = resp.headers.get("Retry-After", "0")
        try:
            retry_after_int = int(retry_after)
        except (ValueError, TypeError):
            retry_after_int = 0

        if resp.status_code == 200 and retry_after_int <= 0:
            data = resp.json()
            # WQ API may return {progress: 0.xx} while still running (no Retry-After header)
            if "progress" in data and data.get("alpha") is None:
                return {"status": "running", "retry_after": 10, "alpha_id": None}
            # Extract alpha ID from response
            alpha_raw = data.get("alpha")
            alpha_id = alpha_raw.get("id") if isinstance(alpha_raw, dict) else alpha_raw
            alpha_id = alpha_id or data.get("id")
            return {"status": "completed", "retry_after": 0, "alpha_id": str(alpha_id) if alpha_id else None}

        # Still running
        if resp.status_code == 202 or (resp.status_code == 200 and retry_after_int > 0):
            return {"status": "running", "retry_after": retry_after_int, "alpha_id": None}

        # Unexpected status
        return {"status": "failed", "retry_after": 0, "alpha_id": None}

    def get_alpha_detail(self, alpha_id: str) -> dict[str, Any]:
        """Fetch full alpha detail including performance metrics."""
        resp = self.request("GET", f"/alphas/{alpha_id}")
        return resp.json()

    def get_settings_doc(self) -> str:
        """Fetch the official Brain simulation settings documentation.

        Returns plain text (HTML stripped).
        """
        url = "https://platform.worldquantbrain.com/learn/documentation/create-alphas/simulation-settings"
        session = self.ensure_session()
        try:
            resp = session.get(url, timeout=30)
            if resp.status_code == 200:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(resp.text, "lxml")
                for tag in soup(["script", "style", "nav", "footer", "header"]):
                    tag.decompose()
                return soup.get_text(separator="\n", strip=True)
            else:
                return f"[Failed to fetch settings guide: HTTP {resp.status_code}]"
        except requests.exceptions.RequestException as e:
            return f"[Failed to fetch settings guide: {e}]"
