"""Unified LLM call interface — NVIDIA (primary) > Gemini (secondary) > Ollama (fallback)."""

import json
import httpx
from src.config import (
    ACTIVE_PROVIDER, NVIDIA_API_KEY, NVIDIA_API_BASE, NVIDIA_PRO, NVIDIA_FLASH,
    GEMINI_FLASH, GEMINI_PRO, OLLAMA_BASE_URL, OLLAMA_MODEL,
)


def _resolve_model(model_hint: str) -> tuple[str, str]:
    """Resolve a model hint (pro/flash/specific name) to (provider, model_name).

    Returns:
        Tuple of (provider, full_model_name)
    """
    hint = model_hint.lower().strip()

    if ACTIVE_PROVIDER == "nvidia":
        if hint in ("pro", "synthesis", "creative_writing", "complex_reasoning"):
            return "nvidia", NVIDIA_PRO
        if hint in ("flash", "extraction", "classification", "ranking", "fact_checking"):
            return "nvidia", NVIDIA_FLASH
        if "gemini" in hint or "flash" in hint:
            return "nvidia", NVIDIA_FLASH
        if "mistral" in hint or "llama" in hint or "nvidia" in hint:
            return "nvidia", hint
        return "nvidia", NVIDIA_FLASH

    if ACTIVE_PROVIDER == "gemini":
        if hint in ("pro", "synthesis"):
            return "gemini", GEMINI_PRO
        if hint in ("flash", "extraction"):
            return "gemini", GEMINI_FLASH
        if "gemini" in hint:
            return "gemini", hint
        return "gemini", GEMINI_FLASH

    return "ollama", OLLAMA_MODEL


async def call_llm(
    prompt: str,
    model: str = "flash",
    system_instruction: str = "",
    response_mime_type: str = "",
    temperature: float = 0.7,
) -> str:
    """Call an LLM with automatic fallback chain: NVIDIA > Gemini > Ollama.

    Args:
        prompt: The user prompt
        model: Model hint — "pro", "flash", or a specific model name
        system_instruction: System-level instruction
        response_mime_type: Set to "application/json" for JSON output
        temperature: Sampling temperature

    Returns:
        The model's text response
    """
    provider, model_name = _resolve_model(model)

    # Try primary provider
    try:
        if provider == "nvidia":
            return await _nvidia_call(prompt, model_name, system_instruction, temperature)
        elif provider == "gemini":
            return _gemini_call(prompt, model_name, system_instruction, response_mime_type, temperature)
    except Exception as e:
        primary_error = str(e)[:150]
        # Fall through to fallback chain
        pass

    # Fallback: try the other cloud provider
    try:
        if provider == "nvidia" and _has_gemini():
            return _gemini_call(prompt, GEMINI_FLASH, system_instruction, response_mime_type, temperature)
        elif provider == "gemini" and NVIDIA_API_KEY:
            return await _nvidia_call(prompt, NVIDIA_FLASH, system_instruction, temperature)
    except Exception:
        pass

    # Final fallback: Ollama
    return await _ollama_fallback(prompt, system_instruction, primary_error if 'primary_error' in dir() else "")


def call_llm_sync(
    prompt: str,
    model: str = "flash",
    system_instruction: str = "",
    response_mime_type: str = "",
    temperature: float = 0.7,
) -> str:
    """Synchronous version of call_llm."""
    provider, model_name = _resolve_model(model)

    try:
        if provider == "nvidia":
            return _nvidia_call_sync(prompt, model_name, system_instruction, temperature)
        elif provider == "gemini":
            return _gemini_call(prompt, model_name, system_instruction, response_mime_type, temperature)
    except Exception:
        pass

    # Sync Ollama fallback
    try:
        full_prompt = f"{system_instruction}\n\n{prompt}" if system_instruction else prompt
        resp = httpx.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json={"model": OLLAMA_MODEL, "prompt": full_prompt, "stream": False},
            timeout=180.0,
        )
        return resp.json().get("response", "")
    except Exception as e:
        return f"[LLM unavailable: {e}]"


# --- NVIDIA API (OpenAI-compatible) ---

async def _nvidia_call(
    prompt: str,
    model: str,
    system_instruction: str = "",
    temperature: float = 0.7,
) -> str:
    """Call NVIDIA API (OpenAI-compatible format)."""
    messages = []
    if system_instruction:
        messages.append({"role": "system", "content": system_instruction})
    messages.append({"role": "user", "content": prompt})

    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            f"{NVIDIA_API_BASE}/chat/completions",
            headers={
                "Authorization": f"Bearer {NVIDIA_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": 4096,
            },
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]


def _nvidia_call_sync(
    prompt: str,
    model: str,
    system_instruction: str = "",
    temperature: float = 0.7,
) -> str:
    """Synchronous NVIDIA API call."""
    messages = []
    if system_instruction:
        messages.append({"role": "system", "content": system_instruction})
    messages.append({"role": "user", "content": prompt})

    response = httpx.post(
        f"{NVIDIA_API_BASE}/chat/completions",
        headers={
            "Authorization": f"Bearer {NVIDIA_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": 4096,
        },
        timeout=120.0,
    )
    response.raise_for_status()
    data = response.json()
    return data["choices"][0]["message"]["content"]


# --- Gemini API ---

def _has_gemini() -> bool:
    from src.config import GEMINI_API_KEY
    return bool(GEMINI_API_KEY)


def _gemini_call(
    prompt: str,
    model: str,
    system_instruction: str = "",
    response_mime_type: str = "",
    temperature: float = 0.7,
) -> str:
    """Call Gemini API."""
    from google.genai import types
    from src.config import get_genai_client

    client = get_genai_client()
    config = types.GenerateContentConfig(temperature=temperature)
    if system_instruction:
        config.system_instruction = system_instruction
    if response_mime_type:
        config.response_mime_type = response_mime_type

    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=config,
    )
    return response.text or ""


# --- Ollama Fallback ---

async def _ollama_fallback(prompt: str, system_instruction: str = "", error_msg: str = "") -> str:
    """Fallback to local Ollama model."""
    try:
        full_prompt = f"{system_instruction}\n\n{prompt}" if system_instruction else prompt
        async with httpx.AsyncClient(timeout=180.0) as client:
            response = await client.post(
                f"{OLLAMA_BASE_URL}/api/generate",
                json={"model": OLLAMA_MODEL, "prompt": full_prompt, "stream": False},
            )
            response.raise_for_status()
            return response.json().get("response", "")
    except Exception as e2:
        return f"[LLM unavailable. Primary error: {error_msg[:100]}. Ollama error: {e2}]"


# --- Utilities ---

def parse_json_response(text: str) -> dict | list:
    """Parse JSON from LLM response, handling markdown code blocks."""
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()
    return json.loads(text)


def is_llm_unavailable_response(text: str) -> bool:
    """Return True if text appears to be a synthetic failure message."""
    if not text:
        return True
    lowered = text.lower().strip()
    return lowered.startswith("[llm unavailable") or "resource_exhausted" in lowered
