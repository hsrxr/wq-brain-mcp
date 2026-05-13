from __future__ import annotations

import os
from pathlib import Path
from dataclasses import dataclass

_PROJECT_ROOT = Path(__file__).resolve().parent.parent

# ── Paths ──
OPERATORS_PATH = _PROJECT_ROOT / "wq_operators_cleaned.json"
DATAFIELDS_CACHE_DIR = _PROJECT_ROOT / "datafields_cache"
DATA_DIR = Path(__file__).resolve().parent / "data"
KNOWLEDGE_BASE_PATH = DATA_DIR / "knowledge_base.json"

# ── WQ API ──
API_BASE = "https://api.worldquantbrain.com"
MAX_CONCURRENT = 3
POLL_INTERVAL = 30
MAX_POLL_RETRIES = 3
MAX_QUEUE_RETRIES = 5
MAX_QUEUE_SIZE = 50
RELOGIN_INTERVAL = 13800  # 3h50m

# ── Truncation limits (in words, ~1 token ≈ 0.75 word) ──
MAX_LIST_TOKENS = 2000
DEFAULT_PAGE_SIZE = 20
DEFAULT_FIELD_PAGE_SIZE = 50
DEFAULT_OPERATOR_PAGE_SIZE = 20

# ── Simulation defaults ──
DEFAULT_SETTINGS = {
    "instrumentType": "EQUITY",
    "region": "USA",
    "universe": "TOP3000",
    "delay": 1,
    "decay": 5,
    "neutralization": "MARKET",
    "truncation": 0.08,
    "pasteurization": "ON",
    "nanHandling": "OFF",
    "unitHandling": "VERIFY",
    "visualization": False,
}


@dataclass
class AppConfig:
    username: str
    password: str
    proxies: dict[str, str] | None = None

    @classmethod
    def from_env(cls) -> AppConfig:
        username = os.environ.get("BRAIN_USERNAME")
        password = os.environ.get("BRAIN_PASSWORD")

        if not username or not password:
            env_path = _PROJECT_ROOT / ".env"
            if env_path.exists():
                for line in env_path.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if "=" not in line or line.startswith("#"):
                        continue
                    key, _, val = line.partition("=")
                    key = key.strip()
                    val = val.strip().strip("\"'")
                    if key == "BRAIN_USERNAME":
                        username = val
                    elif key == "BRAIN_PASSWORD":
                        password = val

        if not username or not password:
            raise ValueError(
                "BRAIN_USERNAME and BRAIN_PASSWORD must be set in .env or environment variables"
            )

        proxies = None
        http_proxy = os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy")
        https_proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
        if http_proxy or https_proxy:
            proxies = {}
            if http_proxy:
                proxies["http"] = http_proxy
            if https_proxy:
                proxies["https"] = https_proxy

        return cls(username=username, password=password, proxies=proxies)
