"""AudioGenerator — converts script text to speech using edge-tts."""

import asyncio
import os
import subprocess
import edge_tts
from src.config import HINDI_TTS_VOICE, OUTPUT_DIR, get_video_language_profile
from src.audit import log_agent_step, AuditTimer
from src.models import VideoScenePlan


def _voice_candidates(language: str, voice: str | None = None) -> list[str]:
    profile = get_video_language_profile(language)
    candidates: list[str] = []
    if voice:
        candidates.append(voice)

    primary = profile.get("tts_voice") or ""
    if primary:
        candidates.append(primary)

    for v in profile.get("tts_fallback_voices", []):
        if v:
            candidates.append(v)

    # Last safety fallback for existing Hindi pipeline behavior.
    if language.lower() in {"hi", "bho"}:
        candidates.append(HINDI_TTS_VOICE)

    deduped: list[str] = []
    seen = set()
    for c in candidates:
        if c and c not in seen:
            deduped.append(c)
            seen.add(c)
    return deduped


def _probe_duration_seconds(path: str) -> float:
    if not path or not os.path.exists(path):
        return 0.0
    try:
        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        if result.returncode == 0:
            return float((result.stdout or "0").strip())
    except Exception:
        pass
    return 0.0


async def generate_audio(
    script_text: str,
    output_filename: str = "narration.mp3",
    language: str = "hi",
    voice: str | None = None,
    session_id: str = "default",
) -> str:
    """Generate narration audio from text using edge-tts.

    Args:
        script_text: Script text in requested language
        output_filename: Output filename
        language: Target language code
        voice: TTS voice to use
        session_id: Session ID for audit

    Returns:
        Path to generated audio file
    """
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    output_path = os.path.join(OUTPUT_DIR, output_filename)
    candidates = _voice_candidates(language, voice)
    selected_voice = candidates[0] if candidates else ""

    with AuditTimer() as timer:
        status = "error"
        error = "No compatible TTS voice configured"
        try:
            if not candidates:
                raise RuntimeError("No TTS candidates available")

            last_error = ""
            for idx, candidate in enumerate(candidates):
                try:
                    communicate = edge_tts.Communicate(script_text, candidate)
                    await communicate.save(output_path)
                    selected_voice = candidate
                    status = "success" if idx == 0 else "fallback"
                    error = "" if idx == 0 else f"Primary voice failed; used fallback {candidate}"
                    break
                except Exception as inner:
                    last_error = str(inner)

            if status == "error":
                output_path = ""
                error = f"All configured voices failed: {last_error}"
        except Exception as e:
            status = "error"
            error = str(e)
            output_path = ""

    log_agent_step(
        agent_name="AudioGenerator",
        action="generate_audio",
        model_used=f"edge-tts ({selected_voice})",
        input_summary=f"Lang: {language}, text: {len(script_text)} chars",
        output_summary=f"Audio: {output_path}" if output_path else "Audio generation failed",
        latency_ms=timer.elapsed_ms,
        status=status,
        error_detail=error,
        session_id=session_id,
    )

    return output_path


async def generate_scene_audio(
    scene_plan: VideoScenePlan,
    language: str = "hi",
    output_filename: str = "scene_narration.mp3",
    target_duration_seconds: int = 0,
    voice: str | None = None,
    session_id: str = "default",
) -> tuple[str, list[int]]:
    """Generate one audio clip per scene and merge into a single narration file.

    Returns:
        Tuple of merged audio path and per-scene durations in seconds.
    """
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    chunks_dir = os.path.join(OUTPUT_DIR, "audio_chunks", session_id)
    os.makedirs(chunks_dir, exist_ok=True)
    merged_output = os.path.join(OUTPUT_DIR, output_filename)

    candidates = _voice_candidates(language, voice)
    selected_voice = candidates[0] if candidates else ""

    with AuditTimer() as timer:
        chunk_paths: list[str] = []
        durations: list[int] = []
        status = "success"
        error = ""

        try:
            if not candidates:
                raise RuntimeError("No TTS candidates available for language")

            async def generate_one_scene(idx: int, scene) -> tuple[str, int]:
                text = (scene.narration_text or scene.text or "").strip()
                if not text:
                    text = scene.heading
                # Enrich terse fallback narration so non-Hindi tracks don't collapse to tiny clips.
                if len(text) < 140:
                    additions = [scene.text or "", scene.heading or "", scene.visual_hint or ""]
                    for part in additions:
                        part = (part or "").strip()
                        if part and part not in text:
                            text = f"{text} {part}".strip()
                # Guardrail: avoid excessively long scene clips from malformed text.
                if len(text) > 420:
                    text = text[:420]
                chunk_path = os.path.join(chunks_dir, f"scene_{idx+1:03d}.mp3")
                last_error = ""
                for candidate in candidates:
                    try:
                        communicate = edge_tts.Communicate(text, candidate, rate="+5%")
                        await communicate.save(chunk_path)
                        dur = max(1, int(round(_probe_duration_seconds(chunk_path))))
                        return chunk_path, dur
                    except Exception as inner:
                        last_error = str(inner)
                raise RuntimeError(f"All voice candidates failed for scene {idx+1}: {last_error}")

            tasks = [generate_one_scene(idx, scene) for idx, scene in enumerate(scene_plan.scenes)]
            results = await asyncio.gather(*tasks)
            for chunk_path, dur in results:
                chunk_paths.append(chunk_path)
                durations.append(dur)

            if not chunk_paths:
                raise RuntimeError("No scene audio chunks were generated")

            concat_path = os.path.join(chunks_dir, "audio_concat.txt")
            with open(concat_path, "w", encoding="utf-8") as f:
                for p in chunk_paths:
                    f.write(f"file '{p.replace(chr(92), '/')}'\n")

            merge_cmd = [
                "ffmpeg", "-y",
                "-f", "concat", "-safe", "0", "-i", concat_path,
                "-c", "copy",
                merged_output,
            ]
            merged = subprocess.run(merge_cmd, capture_output=True, text=True, timeout=60)
            if merged.returncode != 0:
                # Retry with re-encode if stream copy fails.
                merge_cmd = [
                    "ffmpeg", "-y",
                    "-f", "concat", "-safe", "0", "-i", concat_path,
                    "-c:a", "libmp3lame", "-q:a", "2",
                    merged_output,
                ]
                merged = subprocess.run(merge_cmd, capture_output=True, text=True, timeout=60)
                if merged.returncode != 0:
                    raise RuntimeError(f"Audio merge failed: {merged.stderr[:160]}")

            if len(durations) < len(scene_plan.scenes):
                durations.extend([6] * (len(scene_plan.scenes) - len(durations)))

            # Keep scene-synced output near intended duration across languages.
            min_total_seconds = max(int(target_duration_seconds or 0), int(scene_plan.target_duration_seconds or 0), 70)
            total_seconds = sum(durations)
            if merged_output and total_seconds < min_total_seconds:
                deficit = max(0, min_total_seconds - total_seconds)
                padded_output = os.path.join(chunks_dir, "scene_narration_padded.mp3")
                pad_cmd = [
                    "ffmpeg", "-y",
                    "-i", merged_output,
                    "-af", "apad",
                    "-t", str(min_total_seconds),
                    padded_output,
                ]
                padded = subprocess.run(pad_cmd, capture_output=True, text=True, timeout=60)
                if padded.returncode == 0:
                    merged_output = padded_output
                    if durations:
                        durations[-1] += deficit
                else:
                    # If pad fails, still stretch final scene to avoid abrupt ending.
                    if durations:
                        durations[-1] += deficit

        except Exception as e:
            status = "fallback"
            error = str(e)
            merged_output = ""
            durations = []

    log_agent_step(
        agent_name="AudioGenerator",
        action="generate_scene_audio",
        model_used=f"edge-tts ({selected_voice}) + ffmpeg",
        input_summary=f"Lang: {language}, scenes: {len(scene_plan.scenes)}",
        output_summary=f"Merged audio: {bool(merged_output)}, durations: {durations[:8]}",
        latency_ms=timer.elapsed_ms,
        status=status,
        error_detail=error,
        session_id=session_id,
    )

    return merged_output, durations
