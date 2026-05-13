from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from wq_mcp.config import OPERATORS_PATH, DATAFIELDS_CACHE_DIR, DEFAULT_SETTINGS
from wq_mcp.logging_config import get_logger

logger = get_logger(__name__)


class ResearchService:
    """Pure file-based research queries. No HTTP, no MCP dependency.

    Reads from:
      - datafields_cache/    (dataset/field metadata cached from WQ)
      - wq_operators_cleaned.json  (51 operator definitions)
    """

    def __init__(self) -> None:
        self._operators: list[dict[str, Any]] | None = None

    # ── Operators ──

    @staticmethod
    def _op_name(op: dict) -> str:
        """Extract operator name from operator_syntax field."""
        raw = op.get("operator_syntax") or op.get("name", "")
        return raw.split("(")[0].strip() if raw else ""

    @staticmethod
    def _op_syntax(op: dict) -> str:
        """Get operator syntax (normalized)."""
        return op.get("operator_syntax") or op.get("syntax", "")

    def _load_operators(self) -> list[dict[str, Any]]:
        """Lazy-load operators JSON file."""
        if self._operators is None:
            if OPERATORS_PATH.exists():
                with open(OPERATORS_PATH, encoding="utf-8") as f:
                    self._operators = json.load(f)
            else:
                self._operators = []
                logger.warning("Operators file not found: %s", OPERATORS_PATH)
        return self._operators

    def search_operators(self, keyword: str) -> list[dict[str, Any]]:
        """Search operators by keyword in name, syntax, summary, and explanation."""
        kw = keyword.lower()
        operators = self._load_operators()
        results = []
        for op in operators:
            if (
                kw in self._op_name(op).lower()
                or kw in self._op_syntax(op).lower()
                or kw in op.get("summary", "").lower()
                or kw in op.get("detailed_explanation", "").lower()
            ):
                results.append({
                    "name": self._op_name(op),
                    "syntax": self._op_syntax(op),
                    "summary": op.get("summary"),
                    "level": op.get("level"),
                })
        return results

    def get_operator_detail(self, name: str) -> dict[str, Any] | None:
        """Return full detail for a single operator by name (case-insensitive)."""
        operators = self._load_operators()
        name_lower = name.lower()
        for op in operators:
            if self._op_name(op).lower() == name_lower:
                return {
                    "name": self._op_name(op),
                    "syntax": self._op_syntax(op),
                    "summary": op.get("summary"),
                    "level": op.get("level"),
                    "detailed_explanation": op.get("detailed_explanation"),
                }
        return None

    def list_all_operators(self) -> list[dict[str, Any]]:
        """Return compact summary of all operators."""
        operators = self._load_operators()
        return [
            {
                "name": self._op_name(op),
                "syntax": self._op_syntax(op),
                "summary": op.get("summary"),
                "level": op.get("level"),
            }
            for op in operators
        ]

    # ── Datasets ──

    def list_datasets(self) -> list[dict[str, Any]]:
        """Scan datafields_cache directory, return datasets with field counts."""
        if not DATAFIELDS_CACHE_DIR.exists():
            return []

        results = []
        for entry in sorted(DATAFIELDS_CACHE_DIR.iterdir()):
            if entry.is_dir():
                dataset_id = entry.name
                field_count = self._count_fields(dataset_id)
                description = self._read_description(dataset_id)
                sample_fields = self.list_fields(dataset_id)[:5]
                results.append({
                    "dataset_id": dataset_id,
                    "field_count": field_count,
                    "description": description,
                    "sample_fields": sample_fields,
                })
        return results

    def _get_page_files(self, dataset_id: str) -> list[Path]:
        """Find all page_*.json files, searching in timestamp subdirectory if needed."""
        dataset_dir = DATAFIELDS_CACHE_DIR / dataset_id
        if not dataset_dir.exists():
            return []

        # Direct match (flat structure)
        pages = sorted(dataset_dir.glob("page_*.json"))
        if pages:
            return pages

        # Nested: look for timestamp subdirectory (YYYYMMDD_HHMMSS/)
        subdirs = sorted([d for d in dataset_dir.iterdir() if d.is_dir()], reverse=True)
        for subdir in subdirs:
            pages = sorted(subdir.glob("page_*.json"))
            if pages:
                return pages

        return []

    def _count_fields(self, dataset_id: str) -> int:
        """Count fields by reading page JSON files for a dataset."""
        page_files = self._get_page_files(dataset_id)
        if not page_files:
            return 0
        fields = set()
        for page_file in page_files:
            try:
                with open(page_file, encoding="utf-8") as f:
                    data = json.load(f)
                for item in self._extract_page_fields(data):
                    fid = item.get("id") if isinstance(item, dict) else item
                    if fid:
                        fields.add(str(fid))
            except (json.JSONDecodeError, IOError) as e:
                logger.warning("Failed to read %s: %s", page_file, e)
        return len(fields)

    def _read_description(self, dataset_id: str) -> str | None:
        """Read description.md for a dataset if it exists."""
        desc_file = DATAFIELDS_CACHE_DIR / dataset_id / "description.md"
        if desc_file.exists():
            try:
                text = desc_file.read_text(encoding="utf-8").strip()
                return text if text else None
            except IOError:
                return None
        return None

    def list_fields(self, dataset_id: str) -> list[str]:
        """Return all field IDs for a dataset."""
        page_files = self._get_page_files(dataset_id)
        if not page_files:
            return []
        fields: list[str] = []
        seen: set[str] = set()
        for page_file in page_files:
            try:
                with open(page_file, encoding="utf-8") as f:
                    data = json.load(f)
                for item in self._extract_page_fields(data):
                    fid = item.get("id") if isinstance(item, dict) else item
                    if fid and str(fid) not in seen:
                        seen.add(str(fid))
                        fields.append(str(fid))
            except (json.JSONDecodeError, IOError) as e:
                logger.warning("Failed to read %s: %s", page_file, e)
        return fields

    def get_field_detail(self, field_id: str, dataset_id: str) -> dict[str, Any] | None:
        """Return full metadata for one field."""
        page_files = self._get_page_files(dataset_id)
        if not page_files:
            return None
        fid_lower = field_id.lower()
        for page_file in page_files:
            try:
                with open(page_file, encoding="utf-8") as f:
                    data = json.load(f)
                for item in self._extract_page_fields(data):
                    if isinstance(item, dict) and item.get("id", "").lower() == fid_lower:
                        return {
                            "id": item.get("id"),
                            "dataset": dataset_id,
                            "description": item.get("description"),
                            "category": item.get("category"),
                            "subcategory": item.get("subcategory"),
                            "region": item.get("region"),
                            "delay": self._safe_int(item.get("delay")),
                            "universe": item.get("universe"),
                            "type": item.get("type"),
                            "dateCoverage": self._safe_int(item.get("dateCoverage")),
                            "coverage": self._safe_int(item.get("coverage")),
                            "userCount": self._safe_int(item.get("userCount")),
                            "alphaCount": self._safe_int(item.get("alphaCount")),
                            "themes": item.get("themes", []),
                        }
            except (json.JSONDecodeError, IOError):
                continue
        return None

    def get_dataset_detail(self, dataset_id: str) -> dict[str, Any] | None:
        """Return dataset metadata."""
        dataset_dir = DATAFIELDS_CACHE_DIR / dataset_id
        if not dataset_dir.exists():
            return None
        description = self._read_description(dataset_id)
        field_count = self._count_fields(dataset_id)
        # Try to determine category from first field
        category = None
        fields = self.list_fields(dataset_id)
        if fields:
            detail = self.get_field_detail(fields[0], dataset_id)
            if detail:
                category = detail.get("category")
        return {
            "dataset_id": dataset_id,
            "category": category,
            "description": description,
            "field_count": field_count,
        }

    # ── Settings ──

    def get_setting_schema(self) -> dict[str, Any]:
        """Return settings schema with descriptions."""
        # Basic descriptions for each setting
        descriptions = {
            "instrumentType": "Type of instrument (EQUITY, FUTURES, OPTION)",
            "region": "Market region (USA, CHINA, EMEA, etc.)",
            "universe": "Stock universe (TOP3000, TOP500, etc.)",
            "delay": "Delay in days between signal and trade (1 = next day)",
            "decay": "Decay factor for the alpha expression",
            "neutralization": "Risk neutralization (MARKET, INDUSTRY, SECTOR, NONE)",
            "truncation": "Winsorization truncation level (0.08 = 8%)",
            "pasteurization": "Pasteurization filter (ON, OFF)",
            "nanHandling": "NaN handling (OFF, ON)",
            "unitHandling": "Unit handling (VERIFY)",
            "visualization": "Generate visualization charts",
        }
        schema = {}
        for key, default_val in DEFAULT_SETTINGS.items():
            schema[key] = {
                "default": default_val,
                "description": descriptions.get(key, ""),
            }
        return schema

    def get_setting_detail(self, name: str) -> dict[str, Any] | None:
        """Return detail for one setting parameter."""
        schema = self.get_setting_schema()
        if name not in schema:
            return None
        return {"name": name, **schema[name]}

    @staticmethod
    def _extract_page_fields(data: dict | list) -> list:
        """Extract field list from page JSON — handles list, data, results, or error keys."""
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            for key in ("results", "data", "fields", "items"):
                val = data.get(key)
                if isinstance(val, list):
                    return val
        return []

    @staticmethod
    def _safe_int(value: Any) -> int | None:
        if value is None:
            return None
        try:
            return int(value)
        except (ValueError, TypeError):
            return None
