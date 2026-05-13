from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from wq_mcp.config import KNOWLEDGE_BASE_PATH
from wq_mcp.logging_config import get_logger

logger = get_logger(__name__)


class KnowledgeService:
    """Persistent knowledge base backed by JSON file.

    Ported from agent/wq_tools.py add_knowledge/search_knowledge/etc.
    """

    def __init__(self, kb_path: Path | None = None) -> None:
        self._kb_path = kb_path or KNOWLEDGE_BASE_PATH

    # ── Internal helpers ──

    def _ensure_file(self) -> Path:
        self._kb_path.parent.mkdir(parents=True, exist_ok=True)
        if not self._kb_path.exists():
            self._kb_path.write_text("[]", encoding="utf-8")
        return self._kb_path

    def _load(self) -> list[dict[str, Any]]:
        try:
            data = json.loads(self._ensure_file().read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except (json.JSONDecodeError, IOError) as e:
            logger.warning("Failed to load knowledge base: %s", e)
            return []

    def _save(self, entries: list[dict[str, Any]]) -> None:
        self._ensure_file().write_text(
            json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    # ── Public API ──

    def add(
        self,
        topic: str,
        insight: str,
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        """Add a knowledge entry.

        Returns:
            {"status": "ok", "message": str, "entry_count": int}
        """
        entries = self._load()
        entry = {
            "topic": topic,
            "insight": insight,
            "tags": tags or [],
            "source": "mcp",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        entries.append(entry)
        self._save(entries)
        logger.info("Knowledge added: topic=%s tags=%s", topic, tags)
        return {"status": "ok", "message": "Knowledge saved", "entry_count": len(entries)}

    def search(
        self,
        keyword: str = "",
        tags: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Search knowledge base by keyword and/or tag filter."""
        entries = self._load()
        kw = keyword.lower().strip()

        results = []
        for entry in entries:
            # Keyword filter
            if kw:
                text_to_search = " ".join([
                    entry.get("topic", ""),
                    entry.get("insight", ""),
                ]).lower()
                if kw not in text_to_search:
                    continue

            # Tag filter (AND logic: entry must have ALL specified tags)
            if tags:
                entry_tags = [t.lower() for t in entry.get("tags", [])]
                if not all(t.lower() in entry_tags for t in tags):
                    continue

            results.append({
                "topic": entry.get("topic"),
                "insight": entry.get("insight"),
                "tags": entry.get("tags", []),
                "source": entry.get("source", ""),
                "created_at": entry.get("created_at", ""),
            })

        return results

    def list_topics(self) -> list[dict[str, Any]]:
        """List all unique topics with entry count and last-updated."""
        entries = self._load()
        topic_map: dict[str, dict[str, Any]] = {}
        for entry in entries:
            topic = entry.get("topic", "untitled")
            if topic not in topic_map:
                topic_map[topic] = {"topic": topic, "count": 0, "last_updated": ""}
            topic_map[topic]["count"] += 1
            created = entry.get("created_at", "")
            if created > topic_map[topic]["last_updated"]:
                topic_map[topic]["last_updated"] = created
        return sorted(topic_map.values(), key=lambda x: x["last_updated"], reverse=True)

    def list_tags(self) -> list[dict[str, Any]]:
        """List all unique tags with counts."""
        entries = self._load()
        tag_count: dict[str, int] = {}
        for entry in entries:
            for tag in entry.get("tags", []):
                tag_count[tag] = tag_count.get(tag, 0) + 1
        return sorted(
            [{"tag": k, "count": v} for k, v in tag_count.items()],
            key=lambda x: x["count"],
            reverse=True,
        )
