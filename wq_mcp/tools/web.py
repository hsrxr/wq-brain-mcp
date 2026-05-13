from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from wq_mcp.core.web_service import WebService
from wq_mcp.models.common import ErrorResponse, PaginatedResponse, TruncatedText
from wq_mcp.logging_config import get_logger

logger = get_logger(__name__)

_MAX_SEARCH_RESULTS = 20
_MAX_PAGE_CHARS = 8000
_MAX_PAGE_TOKENS = 2000


def register_web_tools(mcp: FastMCP, svc: WebService) -> None:
    """Register all web tools with dependency-injected service."""

    @mcp.tool()
    def wq_web_search(query: str, max_results: int = 10) -> dict:
        """Search the web via DuckDuckGo for factor ideas and research. Capped at 20 results."""
        try:
            count = min(max_results, _MAX_SEARCH_RESULTS)
            results = svc.search(query=query, max_results=count)
            total = len(results)
            return PaginatedResponse(
                items=results,
                total_count=total,
                returned_count=total,
                has_more=False,
            ).model_dump()
        except Exception as e:
            logger.error("wq_web_search failed", exc_info=True)
            return ErrorResponse(error=str(e), error_code="WEB_SEARCH_ERROR").model_dump()

    @mcp.tool()
    def wq_fetch_webpage(url: str) -> dict:
        """Fetch a URL and return its text content (HTML stripped).
        Content is truncated to ~2000 words to respect context limits."""
        try:
            text = svc.fetch_page(url=url, max_chars=_MAX_PAGE_CHARS)
            words = text.split()
            total_words = len(words)
            if total_words > _MAX_PAGE_TOKENS:
                truncated = " ".join(words[:_MAX_PAGE_TOKENS])
                return TruncatedText(
                    text=truncated,
                    full_length=len(text),
                    truncated_length=len(truncated),
                    is_truncated=True,
                    truncated_note=f"全文共 {total_words} 词，返回前 {_MAX_PAGE_TOKENS} 词",
                ).model_dump()
            return TruncatedText(
                text=text,
                full_length=len(text),
                truncated_length=len(text),
                is_truncated=False,
            ).model_dump()
        except Exception as e:
            logger.error("wq_fetch_webpage failed", exc_info=True)
            return ErrorResponse(error=str(e), error_code="FETCH_ERROR").model_dump()
