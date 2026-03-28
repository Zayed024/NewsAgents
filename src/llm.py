"""Unified LLM call interface with smart routing and Ollama fallback."""

import json
from google import genai
from google.genai import types
from src.config import get_genai_client, GEMINI_FLASH, GEMINI_PRO, OLLAMA_BASE_URL, OLLAMA_MODEL
import httpx


async def call_llm(
    prompt: str,
    model: str = GEMINI_FLASH,
    system_instruction: str = "",
    response_mime_type: str = "",
    temperature: float = 0.7,
) -> str:
    """Call an LLM with automatic Ollama fallback on Gemini failure.

    Args:
        prompt: The user prompt
        model: Model name (gemini-2.0-flash, gemini-2.0-pro, etc.)
        system_instruction: System-level instruction
        response_mime_type: Set to "application/json" for JSON output
        temperature: Sampling temperature

    Returns:
        The model's text response
    """
    # Try Gemini first
    try:
        client = get_genai_client()
        config = types.GenerateContentConfig(
            temperature=temperature,
        )
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
    except Exception as e:
        error_msg = str(e)
        # Fall back to Ollama
        return await _ollama_fallback(prompt, system_instruction, error_msg)


async def _ollama_fallback(prompt: str, system_instruction: str = "", error_msg: str = "") -> str:
    """Fallback to local Ollama model."""
    try:
        full_prompt = f"{system_instruction}\n\n{prompt}" if system_instruction else prompt
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{OLLAMA_BASE_URL}/api/generate",
                json={
                    "model": OLLAMA_MODEL,
                    "prompt": full_prompt,
                    "stream": False,
                },
            )
            response.raise_for_status()
            return response.json().get("response", "")
    except Exception as e2:
        return f"[LLM unavailable. Gemini error: {error_msg[:100]}. Ollama error: {e2}]"


def call_llm_sync(
    prompt: str,
    model: str = GEMINI_FLASH,
    system_instruction: str = "",
    response_mime_type: str = "",
    temperature: float = 0.7,
) -> str:
    """Synchronous version of call_llm (Gemini only, no fallback)."""
    try:
        client = get_genai_client()
        config = types.GenerateContentConfig(
            temperature=temperature,
        )
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
    except Exception as e:
        # Sync Ollama fallback
        try:
            full_prompt = f"{system_instruction}\n\n{prompt}" if system_instruction else prompt
            resp = httpx.post(
                f"{OLLAMA_BASE_URL}/api/generate",
                json={"model": OLLAMA_MODEL, "prompt": full_prompt, "stream": False},
                timeout=60.0,
            )
            return resp.json().get("response", "")
        except Exception as e2:
            return f"[LLM unavailable: {e}]"


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
    """Return True if text appears to be a synthetic failure message from LLM fallback chain."""
    if not text:
        return True
    lowered = text.lower().strip()
    return lowered.startswith("[llm unavailable") or "resource_exhausted" in lowered
