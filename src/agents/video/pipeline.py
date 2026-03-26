"""Vernacular Video pipeline — orchestrates breaking news to Hindi video in <60 seconds."""

import time
from src.models import Article, VideoResult, AuditEntry
from src.audit import get_audit_trail, clear_audit_trail, log_agent_step, AuditTimer
from src.agents.video.breaking_ingestor import extract_breaking_facts
from src.agents.video.script_writer import write_hindi_script
from src.agents.video.fact_checker import check_facts
from src.agents.video.audio_gen import generate_audio
from src.agents.video.video_composer import compose_video


async def run_video_pipeline(
    article: Article,
    session_id: str = "video-default",
) -> VideoResult:
    """Run the full breaking news → Hindi video pipeline.

    Steps:
    1. BreakingIngestor — extract 5W1H facts (Flash, ~2s)
    2. ScriptWriter — write Hindi explainer script (Pro, ~8s)
    3. FactChecker — verify claims against source (Flash, ~3s)
    4. AudioGenerator — Hindi TTS (edge-tts, ~15s)
    5. VideoComposer — frames + ffmpeg (PIL+ffmpeg, ~15s)

    Target: <60 seconds total wall-clock time.

    Args:
        article: Breaking news article
        session_id: Session ID for audit

    Returns:
        VideoResult with video path, script, fact check, and timing
    """
    clear_audit_trail(session_id)
    start_time = time.time()

    try:
        # Step 1: Extract facts
        facts = await extract_breaking_facts(article, session_id)

        # Step 2: Write Hindi script
        script = await write_hindi_script(facts, session_id)

        # Step 3: Fact check
        fact_check = await check_facts(script, article, session_id)

        # Step 4: Generate audio
        audio_path = await generate_audio(
            hindi_text=script.script_hindi,
            output_filename=f"{session_id}_narration.mp3",
            session_id=session_id,
        )

        # Step 5: Compose video
        video_path = await compose_video(
            facts=facts,
            script_hindi=script.script_hindi,
            audio_path=audio_path,
            source_url=article.url,
            output_filename=f"{session_id}_explainer.mp4",
            session_id=session_id,
        )

        total_time = time.time() - start_time

        # Determine status
        if video_path:
            status = "success"
        elif audio_path:
            status = "degraded"  # Video failed but audio available
        else:
            status = "degraded"  # Text-only output

    except Exception as e:
        total_time = time.time() - start_time
        video_path = ""
        audio_path = ""
        script = None
        fact_check = None
        status = "failed"

        log_agent_step(
            agent_name="VideoPipeline",
            action="pipeline_error",
            model_used="multi-model",
            input_summary=article.title[:80],
            output_summary=f"Pipeline failed: {str(e)[:100]}",
            latency_ms=int(total_time * 1000),
            status="error",
            error_detail=str(e),
            session_id=session_id,
        )

    # Log overall pipeline completion
    log_agent_step(
        agent_name="VideoPipeline",
        action="full_pipeline",
        model_used="multi-model (Flash + Pro + edge-tts + ffmpeg)",
        input_summary=f"Article: {article.title[:80]}",
        output_summary=f"Video: {bool(video_path)}, Time: {total_time:.1f}s, Status: {status}",
        latency_ms=int(total_time * 1000),
        status=status,
        session_id=session_id,
    )

    return VideoResult(
        video_path=video_path or "",
        script=script,
        fact_check=fact_check,
        generation_time_seconds=round(total_time, 1),
        audio_path=audio_path if audio_path else "",
        status=status,
    )
