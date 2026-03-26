"""AudioGenerator — converts Hindi script to speech using edge-tts."""

import os
import asyncio
import edge_tts
from src.config import HINDI_TTS_VOICE, OUTPUT_DIR
from src.audit import log_agent_step, AuditTimer


async def generate_audio(
    hindi_text: str,
    output_filename: str = "narration.mp3",
    voice: str = HINDI_TTS_VOICE,
    session_id: str = "default",
) -> str:
    """Generate Hindi audio from text using edge-tts.

    Args:
        hindi_text: Hindi script in Devanagari
        output_filename: Output filename
        voice: TTS voice to use
        session_id: Session ID for audit

    Returns:
        Path to generated audio file
    """
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    output_path = os.path.join(OUTPUT_DIR, output_filename)

    with AuditTimer() as timer:
        try:
            communicate = edge_tts.Communicate(hindi_text, voice)
            await communicate.save(output_path)
            status = "success"
            error = ""
        except Exception as e:
            # Fallback to alternative voice
            try:
                alt_voice = "hi-IN-MadhurNeural"
                communicate = edge_tts.Communicate(hindi_text, alt_voice)
                await communicate.save(output_path)
                status = "fallback"
                error = f"Primary voice failed: {e}. Used fallback voice."
            except Exception as e2:
                status = "error"
                error = f"All TTS voices failed: {e}, {e2}"
                output_path = ""

    log_agent_step(
        agent_name="AudioGenerator",
        action="generate_hindi_audio",
        model_used=f"edge-tts ({voice})",
        input_summary=f"Hindi text: {len(hindi_text)} chars",
        output_summary=f"Audio: {output_path}" if output_path else "Audio generation failed",
        latency_ms=timer.elapsed_ms,
        status=status,
        error_detail=error,
        session_id=session_id,
    )

    return output_path
