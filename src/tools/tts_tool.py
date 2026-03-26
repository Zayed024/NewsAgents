"""Text-to-Speech tool using edge-tts for Hindi narration."""

import os
import asyncio
import edge_tts
from src.config import HINDI_TTS_VOICE, OUTPUT_DIR


async def generate_hindi_audio(
    text: str,
    output_filename: str = "narration.mp3",
    voice: str = HINDI_TTS_VOICE,
) -> str:
    """Generate Hindi audio from text using edge-tts.

    Returns the path to the generated audio file.
    """
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    output_path = os.path.join(OUTPUT_DIR, output_filename)

    try:
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(output_path)
        return output_path
    except Exception as e:
        # Fallback: try alternative Hindi voice
        try:
            alt_voice = "hi-IN-MadhurNeural"
            communicate = edge_tts.Communicate(text, alt_voice)
            await communicate.save(output_path)
            return output_path
        except Exception as e2:
            raise RuntimeError(f"TTS generation failed: {e}, fallback also failed: {e2}")


async def list_hindi_voices() -> list[str]:
    """List available Hindi voices."""
    voices = await edge_tts.list_voices()
    return [v["Name"] for v in voices if v["Locale"].startswith("hi-")]
