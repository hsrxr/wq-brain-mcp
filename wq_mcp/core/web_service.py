from __future__ import annotations

from typing import Any

from wq_mcp.logging_config import get_logger

logger = get_logger(__name__)


class WebService:
    """Web search and page fetching. No MCP dependency.

    Ported from agent/wq_tools.py web_search() and fetch_webpage().
    """

    def __init__(self, proxies: dict[str, str] | None = None) -> None:
        self._proxies = proxies

    def search(self, query: str, max_results: int = 10) -> list[dict[str, Any]]:
        """Search the web via DuckDuckGo.

        Tries ddgs library first, falls back to duckduckgo_search, then REST API.

        Returns:
            list of {"title": str, "url": str, "snippet": str}
        """
        results: list[dict[str, Any]] = []

        # Strategy 1: ddgs library
        try:
            from ddgs import DuckDuckGoSearch
            ddgs = DuckDuckGoSearch(proxies=self._proxies)
            raw = list(ddgs.text(query, max_results=max_results))
            for item in raw:
                if isinstance(item, dict):
                    results.append({
                        "title": item.get("title", ""),
                        "url": item.get("href", item.get("link", "")),
                        "snippet": item.get("body", item.get("snippet", "")),
                    })
            if results:
                return results[:max_results]
        except ImportError:
            pass
        except Exception as e:
            logger.debug("ddgs search failed: %s", e)

        # Strategy 2: duckduckgo_search library
        try:
            from duckduckgo_search import DDGS
            with DDGS(proxies=self._proxies) as ddgs:
                raw = list(ddgs.text(query, max_results=max_results))
                for item in raw:
                    if isinstance(item, dict):
                        results.append({
                            "title": item.get("title", ""),
                            "url": item.get("href", item.get("link", "")),
                            "snippet": item.get("body", item.get("snippet", "")),
                        })
                if results:
                    return results[:max_results]
        except ImportError:
            pass
        except Exception as e:
            logger.debug("duckduckgo_search failed: %s", e)

        # Strategy 3: REST API fallback
        try:
            import requests
            params = {"q": query, "format": "json", "max_results": max_results}
            resp = requests.get(
                "https://api.duckduckgo.com/",
                params=params,
                proxies=self._proxies,
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                for topic in data.get("RelatedTopics", []):
                    if "Text" in topic and "FirstURL" in topic:
                        results.append({
                            "title": topic.get("Text", "").split(" - ")[0],
                            "url": topic.get("FirstURL", ""),
                            "snippet": topic.get("Text", ""),
                        })
        except Exception as e:
            logger.debug("REST fallback search failed: %s", e)

        return results[:max_results]

    def fetch_page(self, url: str, max_chars: int = 8000) -> str:
        """Fetch a URL and return its text content with HTML stripped.

        Handles PDFs, timeouts, and errors gracefully.
        """
        try:
            import requests
            from bs4 import BeautifulSoup

            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                )
            }
            resp = requests.get(url, headers=headers, proxies=self._proxies, timeout=30)

            if resp.status_code != 200:
                return f"[Failed to fetch: HTTP {resp.status_code}]"

            content_type = resp.headers.get("Content-Type", "")
            if "pdf" in content_type.lower():
                return "[PDF content — use a PDF reader to view]"

            soup = BeautifulSoup(resp.text, "lxml")
            for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
                tag.decompose()
            text = soup.get_text(separator="\n", strip=True)

            if len(text) > max_chars:
                text = text[:max_chars] + f"\n... [truncated at {max_chars} characters]"

            return text

        except ImportError:
            return "[Error: BeautifulSoup or requests not available]"
        except requests.exceptions.Timeout:
            return "[Error: Request timed out]"
        except requests.exceptions.RequestException as e:
            return f"[Error fetching page: {e}]"
        except Exception as e:
            return f"[Unexpected error: {e}]"
