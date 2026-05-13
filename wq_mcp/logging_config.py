import logging
import sys
from pathlib import Path

_LOG_FILE = Path(__file__).resolve().parent / "mcp_server.log"


def setup_logging() -> None:
    """Configure logging to file only. NO console output (would break stdio JSON-RPC)."""
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    # Remove any existing handlers (e.g. from pytest or inherited config)
    root.handlers.clear()

    fh = logging.FileHandler(str(_LOG_FILE), mode="a", encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    fh.setFormatter(fmt)
    root.addHandler(fh)

    # Silence noisy third-party loggers
    for name in ("httpx", "httpcore", "urllib3", "asyncio"):
        logging.getLogger(name).setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
