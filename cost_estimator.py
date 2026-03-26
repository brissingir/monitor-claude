"""Estimate API-equivalent costs based on token usage per model.

Prices are per 1M tokens (USD), sourced from Anthropic's public pricing.
These are informational only — subscription users don't pay per-token.
"""

from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from models import SessionTokenUsage

# Pricing per 1M tokens (USD) — updated 2025-05
MODEL_PRICING: dict[str, dict[str, float]] = {
    "claude-opus-4": {
        "input": 15.0,
        "output": 75.0,
        "cache_creation": 18.75,
        "cache_read": 1.50,
    },
    "claude-sonnet-4": {
        "input": 3.0,
        "output": 15.0,
        "cache_creation": 3.75,
        "cache_read": 0.30,
    },
    "claude-haiku-4": {
        "input": 0.80,
        "output": 4.0,
        "cache_creation": 1.0,
        "cache_read": 0.08,
    },
}

# Map model IDs with version suffixes to base pricing
_ALIAS_MAP: dict[str, str] = {}


def _resolve_model(model_id: str) -> str:
    if model_id in MODEL_PRICING:
        return model_id
    if model_id in _ALIAS_MAP:
        return _ALIAS_MAP[model_id]
    # Try stripping version suffixes: claude-opus-4-6 -> claude-opus-4
    parts = model_id.rsplit("-", 1)
    if parts[0] in MODEL_PRICING:
        _ALIAS_MAP[model_id] = parts[0]
        return parts[0]
    # Try stripping date suffixes: claude-sonnet-4-20250514 -> claude-sonnet-4
    for base in MODEL_PRICING:
        if model_id.startswith(base):
            _ALIAS_MAP[model_id] = base
            return base
    return model_id


def estimate_cost(model_id: str, usage: SessionTokenUsage) -> float:
    base = _resolve_model(model_id)
    prices = MODEL_PRICING.get(base)
    if not prices:
        return 0.0

    cost = (
        usage.input_tokens * prices["input"]
        + usage.output_tokens * prices["output"]
        + usage.cache_creation_tokens * prices["cache_creation"]
        + usage.cache_read_tokens * prices["cache_read"]
    ) / 1_000_000

    return cost


def format_cost(cost: float) -> str:
    if cost < 0.01:
        return f"${cost:.4f}"
    if cost < 1.0:
        return f"${cost:.2f}"
    return f"${cost:.2f}"
