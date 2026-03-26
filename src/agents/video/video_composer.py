"""VideoComposer — generates visual frames with PIL and composes video with ffmpeg."""

import os
import subprocess
import textwrap
from PIL import Image, ImageDraw, ImageFont
from src.config import (
    VIDEO_WIDTH, VIDEO_HEIGHT, OUTPUT_DIR, HINDI_FONT_PATH, ASSETS_DIR,
)
from src.audit import log_agent_step, AuditTimer


# Colors
BG_DARK = (15, 23, 42)       # Dark navy
BG_ACCENT = (30, 58, 138)    # Blue accent
TEXT_WHITE = (255, 255, 255)
TEXT_YELLOW = (250, 204, 21)
TEXT_RED = (239, 68, 68)
BRAND_ORANGE = (234, 88, 12)


def _get_font(size: int) -> ImageFont.FreeTypeFont:
    """Get the Hindi font at the specified size."""
    try:
        return ImageFont.truetype(HINDI_FONT_PATH, size)
    except Exception:
        # Fallback to default font
        return ImageFont.load_default()


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


def generate_title_frame(title_hindi: str, subtitle: str = "") -> Image.Image:
    """Generate the title card frame."""
    img = _create_gradient_bg()
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
            # Generate frames
            title_text = facts.get("what", "ब्रेकिंग न्यूज़")
            key_numbers = facts.get("key_numbers", [])
            impacts = facts.get("impact_points", [])

            frames = []

            # Frame 1: Title (5 seconds)
            f1 = generate_title_frame(title_text)
            f1_path = os.path.join(frames_dir, "frame_001.png")
            f1.save(f1_path)
            frames.append((f1_path, 5))

            # Frame 2: Key facts (15 seconds)
            if key_numbers:
                f2 = generate_facts_frame(key_numbers)
                f2_path = os.path.join(frames_dir, "frame_002.png")
                f2.save(f2_path)
                frames.append((f2_path, 15))

            # Frame 3: Key numbers (15 seconds)
            if key_numbers:
                f3 = generate_numbers_frame(key_numbers[:4])
                f3_path = os.path.join(frames_dir, "frame_003.png")
                f3.save(f3_path)
                frames.append((f3_path, 15))

            # Frame 4: Impact (15 seconds)
            if impacts:
                f4 = generate_impact_frame(impacts)
                f4_path = os.path.join(frames_dir, "frame_004.png")
                f4.save(f4_path)
                frames.append((f4_path, 15))

            # Frame 5: Closing (10 seconds)
            f5 = generate_closing_frame(source_url)
            f5_path = os.path.join(frames_dir, "frame_005.png")
            f5.save(f5_path)
            frames.append((f5_path, 10))

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
                cmd.extend(["-i", audio_path, "-c:a", "aac", "-shortest"])

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
        input_summary=f"{len(frames) if 'frames' in dir() else 0} frames, audio: {bool(audio_path)}",
        output_summary=output_path if output_path else f"Failed: {error[:100]}",
        latency_ms=timer.elapsed_ms,
        status=status,
        error_detail=error,
        session_id=session_id,
    )

    return output_path
