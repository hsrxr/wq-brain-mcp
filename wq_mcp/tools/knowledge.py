from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from wq_mcp.core.knowledge_service import KnowledgeService
from wq_mcp.models.common import ErrorResponse, PaginatedResponse
from wq_mcp.logging_config import get_logger

logger = get_logger(__name__)

# Pagination limit for knowledge base queries
_MAX_KB_RETURN = 50


def register_knowledge_tools(mcp: FastMCP, svc: KnowledgeService) -> None:
    """Register all knowledge base tools with dependency-injected service."""

    @mcp.tool()
    def wq_add_knowledge(topic: str, insight: str, tags: list[str] | None = None) -> dict:
        """Save an insight to the persistent knowledge base.
        Use this to record successful factor patterns, dataset quirks,
        or lessons learned so Claude can access them in future sessions."""
        try:
            return svc.add(topic=topic, insight=insight, tags=tags)
        except Exception as e:
            logger.error("wq_add_knowledge failed", exc_info=True)
            return ErrorResponse(error=str(e), error_code="KNOWLEDGE_ERROR").model_dump()

    @mcp.tool()
    def wq_search_knowledge(keyword: str = "", tags: list[str] | None = None) -> dict:
        """Search the knowledge base by keyword and/or tag filter.
        Returns matching entries, most recent first. Capped at 50 results."""
        try:
            results = svc.search(keyword=keyword, tags=tags)
            total = len(results)
            paged = results[:_MAX_KB_RETURN]
            return PaginatedResponse(
                items=paged,
                total_count=total,
                returned_count=len(paged),
                has_more=total > _MAX_KB_RETURN,
            ).model_dump()
        except Exception as e:
            logger.error("wq_search_knowledge failed", exc_info=True)
            return ErrorResponse(error=str(e), error_code="KNOWLEDGE_ERROR").model_dump()

    @mcp.tool()
    def wq_list_knowledge_topics() -> dict:
        """List all topics in the knowledge base with entry counts and last-updated timestamps."""
        try:
            topics = svc.list_topics()
            return {"topics": topics, "total_count": len(topics)}
        except Exception as e:
            logger.error("wq_list_knowledge_topics failed", exc_info=True)
            return ErrorResponse(error=str(e), error_code="KNOWLEDGE_ERROR").model_dump()

    @mcp.tool()
    def wq_list_knowledge_tags() -> dict:
        """List all tags used in the knowledge base with counts."""
        try:
            tags = svc.list_tags()
            return {"tags": tags, "total_count": len(tags)}
        except Exception as e:
            logger.error("wq_list_knowledge_tags failed", exc_info=True)
            return ErrorResponse(error=str(e), error_code="KNOWLEDGE_ERROR").model_dump()
