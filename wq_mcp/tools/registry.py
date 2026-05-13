from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from wq_mcp.core.alpha_service import AlphaService
from wq_mcp.core.research_service import ResearchService
from wq_mcp.core.expression_service import ExpressionService
from wq_mcp.core.queue_manager import FactorQueueManager
from wq_mcp.core.knowledge_service import KnowledgeService
from wq_mcp.core.web_service import WebService
from wq_mcp.core.api_client import WqApiClient
from wq_mcp.tools.alpha import register_alpha_tools
from wq_mcp.tools.research import register_research_tools
from wq_mcp.tools.expression import register_expression_tools
from wq_mcp.tools.submission import register_submission_tools
from wq_mcp.tools.simcheck import register_simcheck_tools
from wq_mcp.tools.knowledge import register_knowledge_tools
from wq_mcp.tools.web import register_web_tools
from wq_mcp.logging_config import get_logger

logger = get_logger(__name__)


def register_all_tools(
    mcp: FastMCP,
    research_svc: ResearchService,
    expression_svc: ExpressionService,
    queue_mgr: FactorQueueManager,
    knowledge_svc: KnowledgeService,
    web_svc: WebService,
    api_client: WqApiClient,
    alpha_svc: AlphaService | None = None,
) -> None:
    """Register all MCP tools with dependency-injected services. Zero global variables."""
    logger.info("Registering all MCP tools...")

    register_research_tools(mcp, research_svc)
    logger.debug("Research tools registered")

    register_expression_tools(mcp, expression_svc)
    logger.debug("Expression tools registered")

    register_submission_tools(mcp, queue_mgr, api_client, expression_svc=expression_svc)
    logger.debug("Submission tools registered")

    register_simcheck_tools(mcp, expression_svc)
    logger.debug("Similarity check tools registered")

    register_knowledge_tools(mcp, knowledge_svc)
    logger.debug("Knowledge tools registered")

    register_web_tools(mcp, web_svc)
    logger.debug("Web tools registered")

    if alpha_svc:
        register_alpha_tools(mcp, alpha_svc)
        logger.debug("Alpha analytics tools registered")

    logger.info("All MCP tools registered successfully")
