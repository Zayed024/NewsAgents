"""Deterministic model routing for cost-efficient 3-provider architecture."""

from src.config import (
    MODEL_ROUTING, ACTIVE_PROVIDER,
    NVIDIA_PRO, NVIDIA_FLASH,
    GEMINI_PRO, GEMINI_FLASH,
    OLLAMA_MODEL,
)


def get_model(task_type: str) -> str:
    """Return the semantic model hint for a given task type."""
    return MODEL_ROUTING.get(task_type, "flash")


def get_routing_summary() -> dict:
    """Return the full routing table for audit/display purposes."""
    return {
        "active_provider": ACTIVE_PROVIDER,
        "routing_table": MODEL_ROUTING,
        "provider_models": {
            "nvidia": {"pro": NVIDIA_PRO, "flash": NVIDIA_FLASH, "cost": "Free endpoint"},
            "gemini": {"pro": GEMINI_PRO, "flash": GEMINI_FLASH, "cost": "$0.10-$1.25/M tokens"},
            "ollama": {"model": OLLAMA_MODEL, "cost": "$0.00 (local)"},
        },
        "fallback_chain": f"{ACTIVE_PROVIDER} -> {'gemini' if ACTIVE_PROVIDER == 'nvidia' else 'nvidia'} -> ollama",
    }
