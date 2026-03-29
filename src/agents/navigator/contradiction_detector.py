"""Contradiction Detector — flags where articles directly contradict each other."""

from src.llm import call_llm, parse_json_response
from src.audit import log_agent_step, AuditTimer
from src.models import Article, SynthesisEntry


SYSTEM_INSTRUCTION = """You are a financial news contradiction analyst.
Given multiple article syntheses about the same event, identify specific points where
articles or experts DIRECTLY CONTRADICT each other — not just different emphasis, but
genuinely opposing claims or predictions.

Rules:
1. Only flag real contradictions, not mere differences in emphasis.
2. Cite specific articles by ID.
3. Explain WHY the contradiction matters for the reader's decision-making.
4. If no genuine contradictions exist, say so honestly — do not fabricate them.
"""


async def detect_contradictions(
    syntheses: list[SynthesisEntry],
    articles: list[Article],
    session_id: str = "default",
) -> list[dict]:
    """Detect contradictions across article syntheses.

    Returns:
        List of contradiction dicts with claim_a, claim_b, source_a, source_b,
        why_it_matters, and severity (high/medium/low).
    """
    with AuditTimer() as timer:
        # Build context from syntheses
        synth_text = ""
        for s in syntheses:
            synth_text += f"\n[{s.angle_name}] (sources: {s.source_articles}):\n{s.synthesis}\n"

        # Include a sample of article content for deeper analysis
        article_text = ""
        for a in articles[:12]:
            article_text += f"\n[{a.id}] {a.title}:\n{a.content[:300]}...\n"

        prompt = f"""Analyze these syntheses and articles for DIRECT CONTRADICTIONS — points where
two sources make genuinely opposing claims about the same topic.

SYNTHESES:
{synth_text}

ARTICLES:
{article_text}

Return JSON:
{{
  "contradictions": [
    {{
      "claim_a": "What source A claims",
      "source_a": ["article-id-1"],
      "claim_b": "What source B claims (opposing)",
      "source_b": ["article-id-2"],
      "topic": "The topic they disagree on",
      "why_it_matters": "Why this contradiction matters for reader decision-making",
      "severity": "high|medium|low"
    }}
  ],
  "contradiction_count": 2,
  "overall_coherence": "high|medium|low"
}}

If no genuine contradictions exist, return empty contradictions array with overall_coherence: "high"."""

        response = await call_llm(
            prompt=prompt,
            model="pro",
            system_instruction=SYSTEM_INSTRUCTION,
            response_mime_type="application/json",
            temperature=0.3,
        )

        try:
            data = parse_json_response(response)
            contradictions = data.get("contradictions", [])
        except Exception:
            contradictions = []

    log_agent_step(
        agent_name="ContradictionDetector",
        action="detect_contradictions",
        model_used="pro",
        input_summary=f"{len(syntheses)} syntheses, {len(articles)} articles",
        output_summary=f"{len(contradictions)} contradictions found",
        latency_ms=timer.elapsed_ms,
        session_id=session_id,
    )

    return contradictions
