"""Deterministic model routing for cost-efficient architecture."""

from src.config import MODEL_ROUTING, GEMINI_FLASH, OLLAMA_MODEL, OLLAMA_BASE_URL
import httpx


def get_model(task_type: str) -> str:
    """Return the optimal model name for a given task type."""
    return MODEL_ROUTING.get(task_type, GEMINI_FLASH)


async def ollama_generate(prompt: str, model: str = OLLAMA_MODEL) -> str:
    """Fallback generation using local Ollama model."""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{OLLAMA_BASE_URL}/api/generate",
                json={"model": model, "prompt": prompt, "stream": False},
            )
            response.raise_for_status()
            return response.json().get("response", "")
    except Exception as e:
        return f"[Ollama fallback failed: {e}]"


def get_routing_summary() -> dict:
    """Return the full routing table for audit/display purposes."""
    return {
        "routing_table": MODEL_ROUTING,
        "cost_estimates": {
            "gemini_flash": "$0.10/M input tokens",
            "gemini_pro": "$1.25/M input tokens",
            "ollama_local": "$0.00 (local)",
        },
    }
