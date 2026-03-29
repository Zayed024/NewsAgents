"""Build a single explorable deep briefing from angle syntheses."""

from src.llm import call_llm, parse_json_response
from src.audit import log_agent_step, AuditTimer
from src.models import AngleCluster, SynthesisEntry


SYSTEM_INSTRUCTION = """You are an Economic Times editorial intelligence editor.
Convert multi-angle syntheses into one interactive deep briefing document that is easy to explore.
Keep structure crisp and useful for readers who want both speed and depth.
"""


async def build_interactive_briefing(
    angles: list[AngleCluster],
    syntheses: list[SynthesisEntry],
    session_id: str = "default",
) -> tuple[str, list[str]]:
    """Create a single deep briefing markdown and suggested follow-up questions."""
    with AuditTimer() as timer:
        angle_descriptions = "\n".join(
            f"- {a.angle_name}: {a.description}" for a in angles
        )
        synthesis_blocks = "\n\n".join(
            (
                f"[{s.angle_name}]\n"
                f"Synthesis: {s.synthesis}\n"
                f"Key takeaways: {', '.join(s.key_takeaways)}\n"
                f"Sources: {', '.join(s.source_articles)}"
            )
            for s in syntheses
        )

        prompt = f"""Build ONE explorable briefing in markdown from this input.

ANGLES:
{angle_descriptions}

SYNTHESIS INPUT:
{synthesis_blocks}

Return JSON with this shape:
{{
  "deep_briefing_markdown": "A structured markdown briefing with sections in this order: # Title, ## At a glance, ## What changed, ## Angle explorer (sub-sections for every angle), ## Cross-angle tensions and trade-offs, ## What to watch next (next 30-90 days), ## Source map",
  "suggested_questions": [
    "Question 1",
    "Question 2",
    "Question 3",
    "Question 4",
    "Question 5"
  ]
}}

Rules:
1. Make the markdown explorable with headings and concise bullets.
2. Keep each angle section distinct and cite source IDs like [budget-001].
3. Suggested questions must be concrete and answerable from source-backed context.
4. Do not invent claims or data.
"""

        response = await call_llm(
            prompt=prompt,
            model="pro",
            system_instruction=SYSTEM_INSTRUCTION,
            response_mime_type="application/json",
            temperature=0.4,
        )

        try:
            data = parse_json_response(response)
            markdown = str(data.get("deep_briefing_markdown", "")).strip()
            questions = [str(q).strip() for q in data.get("suggested_questions", []) if str(q).strip()]
        except Exception:
            markdown, questions = _fallback_deep_briefing(angles, syntheses)

        if not markdown:
            markdown, questions = _fallback_deep_briefing(angles, syntheses)

    log_agent_step(
        agent_name="BriefingBuilder",
        action="build_interactive_briefing",
        model_used="pro",
        input_summary=f"{len(angles)} angles, {len(syntheses)} syntheses",
        output_summary=f"markdown {len(markdown)} chars, {len(questions)} suggested questions",
        latency_ms=timer.elapsed_ms,
        session_id=session_id,
    )

    return markdown, questions[:6]


def _fallback_deep_briefing(
    angles: list[AngleCluster],
    syntheses: list[SynthesisEntry],
) -> tuple[str, list[str]]:
    """Deterministic fallback if JSON parsing or generation fails."""
    synthesis_map = {s.angle_name: s for s in syntheses}

    lines = [
        "# Union Budget Intelligence Briefing",
        "",
        "## At a glance",
        f"- Total angles: {len(angles)}",
        "- Format: Synthesized from ET angle coverage",
        "",
        "## Angle explorer",
    ]

    for angle in angles:
        s = synthesis_map.get(angle.angle_name)
        lines.append("")
        lines.append(f"### {angle.angle_name}")
        lines.append(f"{angle.description}")
        if s:
            lines.append("")
            lines.append(s.synthesis)
            if s.key_takeaways:
                lines.append("")
                lines.append("Key takeaways:")
                for takeaway in s.key_takeaways[:5]:
                    lines.append(f"- {takeaway}")
            if s.source_articles:
                lines.append("")
                lines.append(f"Sources: {', '.join(s.source_articles)}")

    lines.extend([
        "",
        "## What to watch next (next 30-90 days)",
        "- Sector-level guidance updates and implementation circulars",
        "- Earnings commentary for budget-sensitive sectors",
        "- Policy clarifications that change tax or capex assumptions",
    ])

    questions = [
        "Which budget changes are likely to affect earnings guidance first?",
        "Where do the biggest trade-offs appear across sectors in this briefing?",
        "What are the highest-confidence winners and why?",
        "What could invalidate the current market narrative in 1-2 quarters?",
        "Can you map the policy timeline and expected impact checkpoints?",
    ]

    return "\n".join(lines), questions
