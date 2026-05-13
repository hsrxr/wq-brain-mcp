from __future__ import annotations

from pathlib import Path

from mcp.server.fastmcp import FastMCP

from wq_mcp.config import AppConfig, DATA_DIR
from wq_mcp.logging_config import setup_logging, get_logger
from wq_mcp.core.api_client import WqApiClient
from wq_mcp.core.alpha_service import AlphaService
from wq_mcp.core.research_service import ResearchService
from wq_mcp.core.expression_service import ExpressionService
from wq_mcp.core.queue_manager import FactorQueueManager
from wq_mcp.core.knowledge_service import KnowledgeService
from wq_mcp.core.web_service import WebService
from wq_mcp.tools.registry import register_all_tools

logger = get_logger(__name__)


def main() -> None:
    # 1. Configure logging FIRST (before any output)
    setup_logging()
    logger.info("=" * 60)
    logger.info("WQ Brain MCP Server starting...")

    # 2. Load config
    try:
        cfg = AppConfig.from_env()
        logger.info("Configuration loaded (user=%s)", cfg.username[:4] + "***")
    except ValueError as e:
        logger.critical("Configuration error: %s", e)
        raise

    # 3. Initialize business layer — pure Python, no MCP dependency
    api_client = WqApiClient(cfg.username, cfg.password, proxies=cfg.proxies)
    try:
        api_client.login()
        logger.info("WQ Brain API login successful")
    except Exception as e:
        logger.critical("Failed to login to WQ Brain API: %s", e)
        raise

    research_svc = ResearchService()
    expression_svc = ExpressionService()
    alpha_svc = AlphaService(api_client=api_client)
    queue_mgr = FactorQueueManager(
        api_client=api_client,
        state_path=DATA_DIR / "queue_state.json",
    )
    knowledge_svc = KnowledgeService()
    web_svc = WebService(proxies=cfg.proxies)

    logger.info("Business layer initialized")

    # 4. Create MCP app (no global state — everything injected)
    mcp = FastMCP("WQ Brain Factor Mining")

    # 5. Register all tools with injected service instances
    register_all_tools(
        mcp=mcp,
        research_svc=research_svc,
        expression_svc=expression_svc,
        queue_mgr=queue_mgr,
        knowledge_svc=knowledge_svc,
        web_svc=web_svc,
        api_client=api_client,
        alpha_svc=alpha_svc,
    )

    # 6. Resources — expose key data as MCP resources
    @mcp.resource("wq://operators/count")
    def operator_count() -> str:
        """Number of available WQ operators."""
        ops = research_svc.list_all_operators()
        return f"WQ Brain provides {len(ops)} operators for factor construction."

    @mcp.resource("wq://datasets/count")
    def dataset_count() -> str:
        """Number of locally cached datasets."""
        ds = research_svc.list_datasets()
        return f"WQ Brain has {len(ds)} locally cached datasets available."

    # 7. Start
    logger.info("MCP Server ready, starting transport=stdio")
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
