"""VideoComposer — generates visual frames with PIL and composes video with ffmpeg."""

import os
import subprocess
import textwrap
from PIL import Image, ImageDraw, ImageFont
from src.config import (
    VIDEO_WIDTH, VIDEO_HEIGHT, OUTPUT_DIR, HINDI_FONT_PATH, ASSETS_DIR,
    get_video_language_profile, get_font_path_for_language,
)
from src.audit import log_agent_step, AuditTimer
from src.models import VideoScenePlan
from src.agents.video.article_visuals import fetch_article_visuals
from src.agents.video.localized_event import is_english_heavy, localize_event_text


# Colors
BG_DARK = (15, 23, 42)       # Dark navy
BG_ACCENT = (30, 58, 138)    # Blue accent
TEXT_WHITE = (255, 255, 255)
TEXT_YELLOW = (250, 204, 21)
TEXT_RED = (239, 68, 68)
BRAND_ORANGE = (234, 88, 12)
ACTIVE_FONT_PATH = HINDI_FONT_PATH


def _get_font(size: int) -> ImageFont.FreeTypeFont:
    """Get active language font at the specified size."""
    try:
        return ImageFont.truetype(ACTIVE_FONT_PATH, size)
    except Exception:
        try:
            return ImageFont.truetype(HINDI_FONT_PATH, size)
        except Exception:
            return ImageFont.load_default()


def _split_script_sections(script_text: str, max_sections: int = 5) -> list[str]:
    """Split script into readable scene-sized sections."""
    text = (script_text or "").strip()
    if not text:
        return []
    sentences = [s.strip() for s in text.replace("\n", " ").split(".") if s.strip()]
    if not sentences:
        return [text[:220]]

    sections: list[str] = []
    current = ""
    for sentence in sentences:
        candidate = f"{current}. {sentence}" if current else sentence
        if len(candidate) <= 210:
            current = candidate
        else:
            if current:
                sections.append(current + ".")
            current = sentence
    if current:
        sections.append(current + ".")

    return sections[:max_sections]


def _get_media_duration_seconds(path: str) -> float:
    """Probe media duration with ffprobe; return 0 on failure."""
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


def _create_gradient_bg() -> Image.Image:
    """Create a gradient background image."""
    img = Image.new("RGB", (VIDEO_WIDTH, VIDEO_HEIGHT), BG_DARK)
    draw = ImageDraw.Draw(img)
    # Simple gradient from dark to slightly lighter at bottom
    for y in range(VIDEO_HEIGHT):
        r = int(15 + (20 * y / VIDEO_HEIGHT))
        g = int(23 + (30 * y / VIDEO_HEIGHT))
        b = int(42 + (50 * y / VIDEO_HEIGHT))
        draw.line([(0, y), (VIDEO_WIDTH, y)], fill=(r, g, b))
    return img


def _fit_image_to_canvas(image: Image.Image) -> Image.Image:
    """Center-crop image to target canvas size."""
    src_w, src_h = image.size
    target_ratio = VIDEO_WIDTH / VIDEO_HEIGHT
    src_ratio = src_w / src_h if src_h else target_ratio

    if src_ratio > target_ratio:
        new_h = src_h
        new_w = int(new_h * target_ratio)
        left = (src_w - new_w) // 2
        top = 0
    else:
        new_w = src_w
        new_h = int(new_w / target_ratio)
        left = 0
        top = (src_h - new_h) // 2

    cropped = image.crop((left, top, left + new_w, top + new_h))
    return cropped.resize((VIDEO_WIDTH, VIDEO_HEIGHT), Image.Resampling.LANCZOS)


def _create_visual_bg(image_path: str) -> Image.Image:
    """Create scene background from article image with dark overlay for readability."""
    try:
        img = Image.open(image_path).convert("RGB")
        img = _fit_image_to_canvas(img)
        overlay = Image.new("RGBA", (VIDEO_WIDTH, VIDEO_HEIGHT), (10, 18, 35, 145))
        img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
        return img
    except Exception:
        return _create_gradient_bg()


def _add_branding(draw: ImageDraw.Draw):
    """Add ET branding bar at top."""
    draw.rectangle([(0, 0), (VIDEO_WIDTH, 60)], fill=BRAND_ORANGE)
    font = _get_font(28)
    draw.text((20, 12), "ECONOMIC TIMES", font=font, fill=TEXT_WHITE)
    draw.text((VIDEO_WIDTH - 200, 12), "ब्रेकिंग न्यूज़", font=font, fill=TEXT_YELLOW)


def _wrap_hindi_text(text: str, max_chars: int = 40) -> list[str]:
    """Wrap Hindi text into lines."""
    words = text.split()
    lines = []
    current_line = ""
    for word in words:
        if len(current_line) + len(word) + 1 <= max_chars:
            current_line += (" " + word if current_line else word)
        else:
            if current_line:
                lines.append(current_line)
            current_line = word
    if current_line:
        lines.append(current_line)
    return lines


def generate_title_frame(title_hindi: str, subtitle: str = "", background_path: str = "") -> Image.Image:
    """Generate the title card frame."""
    img = _create_visual_bg(background_path) if background_path else _create_gradient_bg()
    draw = ImageDraw.Draw(img)
    _add_branding(draw)

    # Title
    title_font = _get_font(48)
    lines = _wrap_hindi_text(title_hindi, 30)
    y = 150
    for line in lines[:4]:
        draw.text((60, y), line, font=title_font, fill=TEXT_WHITE)
        y += 70

    # Subtitle
    if subtitle:
        sub_font = _get_font(28)
        draw.text((60, y + 30), subtitle, font=sub_font, fill=TEXT_YELLOW)

    # Source attribution
    src_font = _get_font(20)
    draw.text((60, VIDEO_HEIGHT - 50), "स्रोत: Economic Times", font=src_font, fill=(150, 150, 150))

    return img


def generate_facts_frame(facts: list[dict], heading: str = "मुख्य तथ्य") -> Image.Image:
    """Generate a key facts frame."""
    img = _create_gradient_bg()
    draw = ImageDraw.Draw(img)
    _add_branding(draw)

    # Heading
    heading_font = _get_font(40)
    draw.text((60, 90), heading, font=heading_font, fill=TEXT_YELLOW)

    # Facts
    fact_font = _get_font(32)
    y = 170
    for i, fact in enumerate(facts[:5]):
        label = fact.get("label", "")
        value = fact.get("value", "")
        context = fact.get("context", "")

        # Bullet
        draw.text((60, y), "●", font=fact_font, fill=BRAND_ORANGE)
        draw.text((100, y), f"{label}: {value}", font=fact_font, fill=TEXT_WHITE)
        y += 50

        if context:
            ctx_font = _get_font(24)
            draw.text((100, y), context, font=ctx_font, fill=(180, 180, 180))
            y += 40

        y += 10

    return img


def generate_numbers_frame(numbers: list[dict], heading: str = "प्रमुख आंकड़े") -> Image.Image:
    """Generate a key numbers highlight frame."""
    img = _create_gradient_bg()
    draw = ImageDraw.Draw(img)
    _add_branding(draw)

    heading_font = _get_font(40)
    draw.text((60, 90), heading, font=heading_font, fill=TEXT_YELLOW)

    # Display numbers in a grid-like layout
    num_font = _get_font(56)
    label_font = _get_font(24)
    y = 180
    for i, num in enumerate(numbers[:4]):
        x = 60 + (i % 2) * (VIDEO_WIDTH // 2)
        if i > 0 and i % 2 == 0:
            y += 180

        draw.text((x, y), str(num.get("value", "")), font=num_font, fill=TEXT_YELLOW)
        draw.text((x, y + 70), str(num.get("label", "")), font=label_font, fill=TEXT_WHITE)
        if num.get("context"):
            draw.text((x, y + 100), str(num.get("context", "")), font=label_font, fill=(150, 150, 150))

    return img


def generate_impact_frame(impacts: list[str], heading: str = "आपके लिए इसका क्या मतलब है") -> Image.Image:
    """Generate the 'what it means for you' frame."""
    img = _create_gradient_bg()
    draw = ImageDraw.Draw(img)
    _add_branding(draw)

    heading_font = _get_font(36)
    draw.text((60, 90), heading, font=heading_font, fill=TEXT_YELLOW)

    impact_font = _get_font(30)
    y = 170
    for impact in impacts[:5]:
        lines = _wrap_hindi_text(impact, 35)
        draw.text((60, y), "▸", font=impact_font, fill=BRAND_ORANGE)
        for line in lines[:2]:
            draw.text((100, y), line, font=impact_font, fill=TEXT_WHITE)
            y += 45
        y += 20

    return img


def generate_text_frame(
    heading: str,
    text: str,
    subheading: str = "",
    background_path: str = "",
) -> Image.Image:
    """Generate a generic narrative text frame."""
    img = _create_visual_bg(background_path) if background_path else _create_gradient_bg()
    draw = ImageDraw.Draw(img)
    _add_branding(draw)

    heading_font = _get_font(40)
    body_font = _get_font(30)
    sub_font = _get_font(24)

    draw.text((60, 90), heading, font=heading_font, fill=TEXT_YELLOW)
    if subheading:
        draw.text((60, 145), subheading, font=sub_font, fill=(180, 180, 180))

    y = 220
    for line in _wrap_hindi_text(text, 55):
        draw.text((60, y), line, font=body_font, fill=TEXT_WHITE)
        y += 45
        if y > VIDEO_HEIGHT - 120:
            break

    return img


def generate_chapter_frame(
    chapter: str,
    heading: str,
    text: str,
    chapter_index: int,
    chapter_total: int,
    background_path: str = "",
) -> Image.Image:
    """Generate chapter frame with progress timeline indicator."""
    img = _create_visual_bg(background_path) if background_path else _create_gradient_bg()
    draw = ImageDraw.Draw(img)
    _add_branding(draw)

    chapter_font = _get_font(24)
    heading_font = _get_font(40)
    body_font = _get_font(30)
    meta_font = _get_font(20)

    draw.text((60, 90), chapter, font=chapter_font, fill=BRAND_ORANGE)
    draw.text((60, 130), heading, font=heading_font, fill=TEXT_YELLOW)

    # Top progress rail across chapters.
    rail_x = 60
    rail_y = 190
    rail_w = VIDEO_WIDTH - 120
    draw.rectangle([(rail_x, rail_y), (rail_x + rail_w, rail_y + 8)], fill=(70, 70, 90))
    if chapter_total > 0:
        progress_w = int(rail_w * ((chapter_index + 1) / chapter_total))
        draw.rectangle([(rail_x, rail_y), (rail_x + progress_w, rail_y + 8)], fill=BRAND_ORANGE)
    draw.text((rail_x, rail_y + 16), f"Chapter {chapter_index + 1}/{chapter_total}", font=meta_font, fill=(180, 180, 180))

    y = 250
    for line in _wrap_hindi_text(text, 55):
        draw.text((60, y), line, font=body_font, fill=TEXT_WHITE)
        y += 46
        if y > VIDEO_HEIGHT - 90:
            break

    return img


def generate_timeline_scene_frame(text: str, language: str = "hi", background_path: str = "") -> Image.Image:
    """Generate a visual timeline scene using simple milestone dots and arrows."""
    img = _create_visual_bg(background_path) if background_path else _create_gradient_bg()
    draw = ImageDraw.Draw(img)
    _add_branding(draw)

    heading = "Story Timeline" if language.lower() == "en" else "कहानी की टाइमलाइन"
    heading_font = _get_font(40)
    body_font = _get_font(26)
    draw.text((60, 90), heading, font=heading_font, fill=TEXT_YELLOW)

    parts = [p.strip() for p in text.replace("->", "|" ).split("|") if p.strip()]
    if len(parts) < 3:
        parts = [p.strip() for p in text.split("-") if p.strip()][:4]
    if len(parts) < 3:
        parts = ["Trigger", "Escalation", "Resolution"] if language.lower() == "en" else ["शुरुआत", "बढ़त", "निष्कर्ष"]

    base_y = 280
    left = 100
    step = int((VIDEO_WIDTH - 200) / max(1, len(parts) - 1))
    for i, part in enumerate(parts):
        x = left + i * step
        draw.ellipse([(x - 14, base_y - 14), (x + 14, base_y + 14)], fill=BRAND_ORANGE)
        if i < len(parts) - 1:
            nx = left + (i + 1) * step
            draw.line([(x + 16, base_y), (nx - 16, base_y)], fill=(180, 180, 180), width=4)
        lines = _wrap_hindi_text(part, 18)
        ty = base_y + 28
        for line in lines[:2]:
            draw.text((x - 60, ty), line, font=body_font, fill=TEXT_WHITE)
            ty += 34

    return img


def generate_closing_frame(source_url: str = "") -> Image.Image:
    """Generate the closing/source attribution frame."""
    img = _create_gradient_bg()
    draw = ImageDraw.Draw(img)
    _add_branding(draw)

    font = _get_font(36)
    draw.text((60, 250), "पूरी खबर पढ़ने के लिए", font=font, fill=TEXT_WHITE)
    draw.text((60, 310), "Economic Times पर जाएं", font=font, fill=TEXT_YELLOW)

    if source_url:
        url_font = _get_font(20)
        draw.text((60, 400), source_url, font=url_font, fill=(150, 150, 150))

    # Disclaimer
    disc_font = _get_font(18)
    draw.text(
        (60, VIDEO_HEIGHT - 80),
        "यह AI द्वारा स्वचालित रूप से तैयार किया गया वीडियो है।",
        font=disc_font, fill=(120, 120, 120),
    )
    draw.text(
        (60, VIDEO_HEIGHT - 50),
        "निवेश से पहले अपने वित्तीय सलाहकार से परामर्श करें।",
        font=disc_font, fill=(120, 120, 120),
    )

    return img


async def compose_video(
    facts: dict,
    script_hindi: str,
    audio_path: str,
    scene_plan: VideoScenePlan | None = None,
    scene_audio_durations: list[int] | None = None,
    target_duration_seconds: int = 90,
    language: str = "hi",
    source_url: str = "",
    output_filename: str = "explainer.mp4",
    session_id: str = "default",
) -> str:
    """Compose the final video from frames and audio.

    Args:
        facts: Extracted facts dict
        script_hindi: Hindi script for title reference
        audio_path: Path to audio file
        source_url: Source article URL
        output_filename: Output video filename
        session_id: Session ID for audit

    Returns:
        Path to the generated video file
    """
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    frames_dir = os.path.join(OUTPUT_DIR, "frames")
    os.makedirs(frames_dir, exist_ok=True)

    with AuditTimer() as timer:
        try:
            global ACTIVE_FONT_PATH
            profile = get_video_language_profile(language)
            ACTIVE_FONT_PATH = get_font_path_for_language(language)
            scene_audio_durations = scene_audio_durations or []
            strict_scene_sync = bool(scene_audio_durations and scene_plan and scene_plan.scenes)
            # Generate frames
            title_text = facts.get("what", "ब्रेकिंग न्यूज़")
            if language.lower() != "en" and is_english_heavy(title_text):
                title_text = localize_event_text(title_text, language)
            key_numbers = facts.get("key_numbers", [])
            impacts = facts.get("impact_points", [])
            script_sections = _split_script_sections(script_hindi, max_sections=5)
            article_visuals = await fetch_article_visuals(source_url, session_id=session_id)

            min_target_seconds = max(int(target_duration_seconds or 0), 75)
            audio_duration_seconds = _get_media_duration_seconds(audio_path)
            final_target_seconds = int(max(min_target_seconds, audio_duration_seconds + 2))

            frames = []
            frame_idx = 1

            def next_frame_path() -> str:
                nonlocal frame_idx
                path = os.path.join(frames_dir, f"frame_{frame_idx:03d}.png")
                frame_idx += 1
                return path

            def pick_visual(i: int) -> str:
                if not article_visuals:
                    return ""
                return article_visuals[i % len(article_visuals)]

            # Frame 1: Title
            f1 = generate_title_frame(title_text, background_path=pick_visual(0))
            f1_path = next_frame_path()
            f1.save(f1_path)
            frames.append((f1_path, 2 if strict_scene_sync else 8))

            # Use explicit scene plan chapters when available.
            if scene_plan and scene_plan.scenes:
                total_chapters = len(scene_plan.scenes)
                for idx, scene in enumerate(scene_plan.scenes):
                    scene_duration = max(5, int(scene.duration_seconds))
                    if idx < len(scene_audio_durations) and scene_audio_durations[idx] > 0:
                        # Keep text frame slightly longer than clip to avoid abrupt cuts.
                        scene_duration = max(5, scene_audio_durations[idx] + 1)

                    if scene.scene_type == "timeline":
                        sf = generate_timeline_scene_frame(scene.text, language=language, background_path=pick_visual(idx + 1))
                    else:
                        sf = generate_chapter_frame(
                            chapter=scene.chapter,
                            heading=scene.heading,
                            text=scene.text,
                            chapter_index=idx,
                            chapter_total=total_chapters,
                            background_path=pick_visual(idx + 1),
                        )
                    sf_path = next_frame_path()
                    sf.save(sf_path)
                    frames.append((sf_path, scene_duration))

            # Fallback to script chunk scenes if no planner output is available.
            if not scene_plan or not scene_plan.scenes:
                for section in script_sections:
                    heading = "Story Update" if language.lower() == "en" else "कहानी का अगला भाग"
                    f_text = generate_text_frame(heading=heading, text=section, background_path=pick_visual(len(frames)))
                    f_text_path = next_frame_path()
                    f_text.save(f_text_path)
                    frames.append((f_text_path, 12))

            # Key facts
            if key_numbers and not strict_scene_sync:
                heading = "Key Facts" if language.lower() == "en" else "मुख्य तथ्य"
                f2 = generate_facts_frame(key_numbers, heading=heading)
                f2_path = next_frame_path()
                f2.save(f2_path)
                frames.append((f2_path, 12))

            # Key numbers
            if key_numbers and not strict_scene_sync:
                heading = "Key Numbers" if language.lower() == "en" else "प्रमुख आंकड़े"
                f3 = generate_numbers_frame(key_numbers[:4], heading=heading)
                f3_path = next_frame_path()
                f3.save(f3_path)
                frames.append((f3_path, 12))

            # Impact section
            if impacts and not strict_scene_sync:
                heading = "What It Means For You" if language.lower() == "en" else "आपके लिए इसका क्या मतलब है"
                f4 = generate_impact_frame(impacts, heading=heading)
                f4_path = next_frame_path()
                f4.save(f4_path)
                frames.append((f4_path, 12))

            # Always include at least one compact summary frame when extraction is sparse.
            if not key_numbers and script_sections and not strict_scene_sync:
                heading = "Quick Recap" if language.lower() == "en" else "तेज़ रिकैप"
                recap_text = " ".join(script_sections[:2])[:360]
                f_recap = generate_text_frame(heading=heading, text=recap_text, background_path=pick_visual(len(frames)))
                f_recap_path = next_frame_path()
                f_recap.save(f_recap_path)
                frames.append((f_recap_path, 10))

            # Closing
            if not strict_scene_sync:
                f5 = generate_closing_frame(source_url)
                f5_path = next_frame_path()
                f5.save(f5_path)
                frames.append((f5_path, 8))

            # Normalize only when scene-level audio is unavailable.
            if not scene_audio_durations:
                base_total = sum(d for _, d in frames) or 1
                scale = final_target_seconds / base_total
                normalized_frames = []
                for path, duration in frames:
                    normalized_frames.append((path, max(3, int(round(duration * scale)))))
                frames = normalized_frames

            # Create ffmpeg concat file
            concat_path = os.path.join(frames_dir, "concat.txt")
            with open(concat_path, "w") as f:
                for fpath, duration in frames:
                    fpath_unix = fpath.replace("\\", "/")
                    f.write(f"file '{fpath_unix}'\n")
                    f.write(f"duration {duration}\n")
                # Repeat last frame (ffmpeg concat demuxer requirement)
                f.write(f"file '{frames[-1][0].replace(chr(92), '/')}'\n")

            # Compose video with ffmpeg
            output_path = os.path.join(OUTPUT_DIR, output_filename)

            cmd = [
                "ffmpeg", "-y",
                "-f", "concat", "-safe", "0", "-i", concat_path,
            ]

            # Add audio if available
            if audio_path and os.path.exists(audio_path):
                cmd.extend(["-i", audio_path, "-c:a", "aac"])
                if strict_scene_sync:
                    cmd.append("-shortest")

            cmd.extend([
                "-vf", f"scale={VIDEO_WIDTH}:{VIDEO_HEIGHT}",
                "-c:v", "libx264",
                "-pix_fmt", "yuv420p",
                "-movflags", "+faststart",
                output_path,
            ])

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
            )

            if result.returncode != 0:
                raise RuntimeError(f"ffmpeg failed: {result.stderr[:200]}")

            status = "success"
            error = ""

        except Exception as e:
            output_path = ""
            status = "error"
            error = str(e)

    log_agent_step(
        agent_name="VideoComposer",
        action="compose_video",
        model_used="PIL + ffmpeg",
        input_summary=(
            f"{len(frames) if 'frames' in dir() else 0} frames, "
            f"lang: {language}, target_s: {target_duration_seconds}, audio: {bool(audio_path)}, "
            f"scene_audio: {len(scene_audio_durations) if scene_audio_durations else 0}"
        ),
        output_summary=output_path if output_path else f"Failed: {error[:100]}",
        latency_ms=timer.elapsed_ms,
        status=status,
        error_detail=error,
        session_id=session_id,
    )

    return output_path
