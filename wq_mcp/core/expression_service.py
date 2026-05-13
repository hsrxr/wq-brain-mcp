from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from wq_mcp.logging_config import get_logger

# Direct import of existing validated code — ported from alphaminingv2/agent/
from wq_mcp.expression_validator import ExpressionValidator
from wq_mcp.expression_fingerprint import (
    expression_fingerprint,
    field_fingerprint,
    structure_distance,
)
from wq_mcp.utils import _check_named_params

logger = get_logger(__name__)

_SUBMITTED_EXPRESSIONS_PATH = Path(__file__).resolve().parent.parent / "data" / "submitted_expressions.json"


class ExpressionService:
    """Expression validation and fingerprinting.

    Pure functions — no IO, no MCP dependency.
    Directly reuses existing agent/ expression_validator and fingerprint modules.
    """

    def __init__(self) -> None:
        self._validator: ExpressionValidator | None = None

    def _get_validator(self) -> ExpressionValidator:
        if self._validator is None:
            self._validator = ExpressionValidator()
        return self._validator

    def validate(self, expression: str, dataset_id: str | None = None) -> dict[str, Any]:
        """Validate a WQ FASTEXPR expression.

        Combines:
          - ExpressionValidator.validate() for syntax/operators/fields
          - _check_named_params() for winsorize/ts_regression/group_backfill pitfalls

        Returns:
            {"valid": bool, "errors": list[str], "warnings": list[str]}
        """
        if not expression or not expression.strip():
            return {"valid": False, "errors": ["Expression is empty"], "warnings": []}

        validator = self._get_validator()
        result = validator.validate(expression, dataset_id=dataset_id)

        # Add named parameter warnings
        named_warnings = _check_named_params(expression)

        return {
            "valid": result.valid,
            "errors": result.errors,
            "warnings": result.warnings + named_warnings,
        }

    def fingerprint(self, expression: str) -> str:
        """Return structural MD5 hash (operator-sequence based)."""
        return expression_fingerprint(expression)

    def field_based_fingerprint(self, expression: str) -> str:
        """Return hash based on sorted field names used in expression."""
        return field_fingerprint(expression)

    def structure_distance(self, expr_a: str, expr_b: str) -> float:
        """Return normalized Levenshtein distance on operator sequences. [0, 1]."""
        return structure_distance(expr_a, expr_b)

    def check_named_params(self, expression: str) -> list[str]:
        """Return warnings about named-parameter pitfalls."""
        return _check_named_params(expression)

    def check_submitted_similarity(
        self, expression: str, threshold: float = 0.3
    ) -> list[dict[str, Any]]:
        """Compare expression against all 22 submitted competition alphas.

        Uses structure_distance (normalized Levenshtein on operator sequences).
        Returns entries where distance < threshold, sorted closest first.
        Each entry: {id, name, distance, sharpe, fitness, grade, expression}
        """
        if not expression or not expression.strip():
            return []

        try:
            refs = json.loads(_SUBMITTED_EXPRESSIONS_PATH.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.warning("Cannot load submitted expressions: %s", e)
            return []

        results = []
        for ref in refs:
            ref_expr = ref.get("expression", "")
            if not ref_expr:
                continue
            dist = structure_distance(expression, ref_expr)
            if dist < threshold:
                results.append({
                    "id": ref.get("id", ""),
                    "name": ref.get("name", ""),
                    "distance": round(dist, 4),
                    "sharpe": ref.get("sharpe", 0),
                    "fitness": ref.get("fitness", 0),
                    "grade": ref.get("grade", ""),
                    "expression": ref_expr,
                })

        results.sort(key=lambda r: r["distance"])
        return results

    def extract_operator_count(self, expression: str) -> int:
        """Count distinct operators used in an expression."""
        from wq_mcp.expression_validator import extract_operator_names
        try:
            ops = extract_operator_names(expression)
            return len(ops) if ops else 0
        except Exception:
            import re
            ops = set(re.findall(r'\b([A-Za-z_][A-Za-z0-9_]*)\s*\(', expression))
            return len(ops)

    def extract_field_count(self, expression: str) -> int:
        """Count distinct fields used in an expression."""
        from wq_mcp.expression_validator import extract_leaf_tokens
        try:
            tokens = extract_leaf_tokens(expression)
            return len(tokens)
        except Exception:
            return 0
