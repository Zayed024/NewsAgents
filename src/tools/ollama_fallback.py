"""Ollama HTTP client for graceful degradation fallback."""

import httpx
from src.config import OLLAMA_BASE_URL, OLLAMA_MODEL


async def ollama_generate(prompt: str, model: str = OLLAMA_MODEL) -> str:
    """Generate text using local Ollama model as fallback."""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{OLLAMA_BASE_URL}/api/generate",
                json={"model": model, "prompt": prompt, "stream": False},
            )
            response.raise_for_status()
            return response.json().get("response", "")
    except Exception as e:
        return f"[Ollama fallback unavailable: {e}]"


async def check_ollama_health() -> bool:
    """Check if Ollama is running and responsive."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{OLLAMA_BASE_URL}/api/tags")
            return response.status_code == 200
    except Exception:
        return False
