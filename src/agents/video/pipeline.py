"""Vernacular Video pipeline — orchestrates breaking news to language-aware explainer video."""

import time
from src.models import Article, VideoResult, AuditEntry
from src.audit import get_audit_trail, clear_audit_trail, log_agent_step, AuditTimer
from src.agents.video.breaking_ingestor import extract_breaking_facts
from src.agents.video.script_writer import write_script
from src.agents.video.fact_checker import check_facts
from src.agents.video.scene_planner import plan_scenes
from src.agents.video.language_validator import validate_and_correct_language, should_run_language_validator
from src.agents.video.audio_gen import generate_audio, generate_scene_audio
from src.agents.video.video_composer import compose_video
from src.config import DEFAULT_VIDEO_LANGUAGE


async def run_video_pipeline(
    article: Article,
    target_language: str = DEFAULT_VIDEO_LANGUAGE,
    session_id: str = "video-default",
) -> VideoResult:
    """Run the full breaking news -> explainer video pipeline.

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

        # Step 2: Write language-aware script
        script = await write_script(
            facts=facts,
            language=target_language,
            target_duration_seconds=90,
            session_id=session_id,
        )

        # Step 3: Fact check
        fact_check = await check_facts(script, article, session_id)

        # Step 4: Plan chaptered scenes (Phase 2)
        scene_plan = await plan_scenes(
            facts=facts,
            script_text=script.script_hindi,
            language=target_language,
            target_duration_seconds=script.estimated_duration_seconds,
            session_id=session_id,
        )

        # Step 5: Validate/correct language consistency only when needed.
        if should_run_language_validator(script, scene_plan, target_language):
            script, scene_plan = await validate_and_correct_language(
                script=script,
                scene_plan=scene_plan,
                target_language=target_language,
                session_id=session_id,
            )

        # Step 6: Generate scene-synced audio for better A/V alignment.
        audio_path, scene_audio_durations = await generate_scene_audio(
            scene_plan=scene_plan,
            language=target_language,
            output_filename=f"{session_id}_narration.mp3",
            target_duration_seconds=script.estimated_duration_seconds,
            session_id=session_id,
        )

        # Fallback to full-script narration if scene audio generation fails.
        if not audio_path:
            audio_path = await generate_audio(
                script_text=script.script_hindi,
                output_filename=f"{session_id}_narration.mp3",
                language=target_language,
                session_id=session_id,
            )
            scene_audio_durations = []

        # Step 7: Compose video
        video_path = await compose_video(
            facts=facts,
            script_hindi=script.script_hindi,
            audio_path=audio_path,
            scene_plan=scene_plan,
            scene_audio_durations=scene_audio_durations,
            target_duration_seconds=script.estimated_duration_seconds,
            language=target_language,
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
        scene_plan = None
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
        input_summary=f"Article: {article.title[:80]}, lang: {target_language}",
        output_summary=f"Video: {bool(video_path)}, Time: {total_time:.1f}s, Status: {status}",
        latency_ms=int(total_time * 1000),
        status=status,
        session_id=session_id,
    )

    return VideoResult(
        video_path=video_path or "",
        script=script,
        fact_check=fact_check,
        scene_plan=scene_plan,
        generation_time_seconds=round(total_time, 1),
        audio_path=audio_path if audio_path else "",
        status=status,
    )
