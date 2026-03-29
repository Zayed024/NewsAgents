"""Language validator for story pipeline outputs.

Validates and corrects script + scene text into the requested target language.
"""

import re

from src.llm import call_llm, parse_json_response
from src.config import get_video_language_profile
from src.audit import log_agent_step, AuditTimer
from src.models import VideoScript, VideoScenePlan, VideoScene


SYSTEM_INSTRUCTION = """You are a strict language quality checker for multilingual news videos.
Your task is to ensure all generated text is in the requested target language.
Rules:
1. Preserve factual meaning and numeric values.
2. Preserve proper nouns (company names, legal institutions, people names).
3. Remove unwanted English words unless they are proper nouns or unavoidable acronyms.
4. Keep style natural, simple, and retail-investor friendly.
5. Return valid JSON only.
"""


def should_run_language_validator(
    script: VideoScript,
    scene_plan: VideoScenePlan,
    target_language: str,
) -> bool:
    """Fast gate: run validator only when non-English text appears noisy."""
    lang = (target_language or "").lower()
    if lang == "en":
        return False

    text_blob = " ".join(
        [
            script.script_hindi,
            scene_plan.story_arc_summary,
            " ".join(scene_plan.sentiment_shifts),
            scene_plan.contrarian_perspective,
            " ".join(scene_plan.watch_next),
            " ".join((s.chapter + " " + s.heading + " " + s.text + " " + (s.narration_text or "")) for s in scene_plan.scenes),
        ]
    )
    english_tokens = len(re.findall(r"[A-Za-z]{3,}", text_blob))

    # Keep a small allowance for proper nouns/acronyms.
    return english_tokens > 18


def _is_model_error_text(text: str) -> bool:
    t = (text or "").strip().lower()
    return (
        t.startswith("[llm unavailable")
        or "resource_exhausted" in t
        or "quota" in t
        or "ollama error" in t
        or "internal server error" in t
    )


def _deterministic_cleanup(text: str, target_language: str) -> str:
    """Cheap local cleanup used when model-based validator is unavailable."""
    cleaned = (text or "").strip()
    if not cleaned:
        return cleaned

    lang = (target_language or "").lower()
    if lang in {"hi", "mr", "bho"}:
        # Remove obvious model error payloads and keep a readable fallback.
        if _is_model_error_text(cleaned):
            return "सिस्टम इस समय अनुवाद जाँच नहीं कर सका। मूल सामग्री सुरक्षित रखी गई है।"
    return cleaned


async def validate_and_correct_language(
    script: VideoScript,
    scene_plan: VideoScenePlan,
    target_language: str,
    session_id: str = "default",
) -> tuple[VideoScript, VideoScenePlan]:
    """Validate and correct script + scene plan to requested language."""
    profile = get_video_language_profile(target_language)
    validator_hint = profile.get("validator_hint", f"Use {target_language} only.")

    with AuditTimer() as timer:
        status = "success"
        error = ""
        corrected_script = script
        corrected_scene_plan = scene_plan

        try:
            prompt = f"""Target language rule: {validator_hint}

SCRIPT TEXT:
{script.script_hindi}

SCENES JSON:
{scene_plan.model_dump()}

Return strict JSON:
{{
  "script_hindi": "corrected full script in target language",
  "script_transliteration": "optional transliteration or same text",
  "estimated_duration_seconds": {script.estimated_duration_seconds},
  "key_facts_used": {script.key_facts_used},
  "analogies_used": {script.analogies_used},
  "scene_plan": {{
    "target_duration_seconds": {scene_plan.target_duration_seconds},
    "story_arc_summary": "...",
    "key_players": ["..."],
    "sentiment_shifts": ["..."],
    "contrarian_perspective": "...",
    "watch_next": ["..."],
    "scenes": [
      {{
        "chapter": "...",
        "heading": "...",
        "text": "short on-screen text in target language",
        "narration_text": "voiceover text in target language",
        "visual_hint": "...",
        "sentiment": "negative|neutral|cautious|positive",
        "duration_seconds": 12,
        "scene_type": "narrative"
      }}
    ]
  }}
}}"""

            response = await call_llm(
                prompt=prompt,
                model="flash",
                system_instruction=SYSTEM_INSTRUCTION,
                response_mime_type="application/json",
                temperature=0.2,
            )
            if _is_model_error_text(response):
                raise RuntimeError("Language validator model unavailable")
            data = parse_json_response(response)

            corrected_script = VideoScript(
                script_hindi=data.get("script_hindi", script.script_hindi),
                script_transliteration=data.get("script_transliteration", script.script_transliteration),
                estimated_duration_seconds=int(data.get("estimated_duration_seconds", script.estimated_duration_seconds)),
                key_facts_used=data.get("key_facts_used", script.key_facts_used),
                analogies_used=data.get("analogies_used", script.analogies_used),
            )

            sp_data = data.get("scene_plan", {})
            corrected_scene_plan = VideoScenePlan(
                target_duration_seconds=int(sp_data.get("target_duration_seconds", scene_plan.target_duration_seconds)),
                story_arc_summary=sp_data.get("story_arc_summary", scene_plan.story_arc_summary),
                key_players=sp_data.get("key_players", scene_plan.key_players),
                sentiment_shifts=sp_data.get("sentiment_shifts", scene_plan.sentiment_shifts),
                contrarian_perspective=sp_data.get("contrarian_perspective", scene_plan.contrarian_perspective),
                watch_next=sp_data.get("watch_next", scene_plan.watch_next),
                scenes=[VideoScene(**scene) for scene in sp_data.get("scenes", [s.model_dump() for s in scene_plan.scenes])],
            )
        except Exception as e:
            status = "fallback"
            error = str(e)

            # Fast fallback path: deterministic cleanup only (no extra model calls).
            corrected_script = VideoScript(
                script_hindi=_deterministic_cleanup(script.script_hindi, target_language),
                script_transliteration=script.script_transliteration,
                estimated_duration_seconds=script.estimated_duration_seconds,
                key_facts_used=script.key_facts_used,
                analogies_used=script.analogies_used,
            )

            corrected_scenes: list[VideoScene] = []
            for scene in scene_plan.scenes:
                corrected_scenes.append(
                    VideoScene(
                        chapter=_deterministic_cleanup(scene.chapter, target_language),
                        heading=_deterministic_cleanup(scene.heading, target_language),
                        text=_deterministic_cleanup(scene.text, target_language),
                        narration_text=_deterministic_cleanup(scene.narration_text or scene.text, target_language),
                        visual_hint=scene.visual_hint,
                        sentiment=scene.sentiment,
                        duration_seconds=scene.duration_seconds,
                        scene_type=scene.scene_type,
                    )
                )

            corrected_scene_plan = VideoScenePlan(
                target_duration_seconds=scene_plan.target_duration_seconds,
                story_arc_summary=_deterministic_cleanup(scene_plan.story_arc_summary, target_language),
                key_players=scene_plan.key_players,
                sentiment_shifts=[_deterministic_cleanup(s, target_language) for s in scene_plan.sentiment_shifts],
                contrarian_perspective=_deterministic_cleanup(scene_plan.contrarian_perspective, target_language),
                watch_next=[_deterministic_cleanup(s, target_language) for s in scene_plan.watch_next],
                scenes=corrected_scenes,
            )

    log_agent_step(
        agent_name="LanguageValidator",
        action="validate_and_correct",
        model_used="flash",
        input_summary=f"Lang: {target_language}, scenes: {len(scene_plan.scenes)}",
        output_summary=(
            f"Script chars: {len(corrected_script.script_hindi)}, "
            f"scenes: {len(corrected_scene_plan.scenes)}"
        ),
        latency_ms=timer.elapsed_ms,
        status=status,
        error_detail=error,
        session_id=session_id,
    )

    return corrected_script, corrected_scene_plan
