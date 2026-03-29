"""Blind Spot Detector — surfaces topics NOT covered by any article in the set."""

from src.llm import call_llm, parse_json_response
from src.audit import log_agent_step, AuditTimer
from src.models import Article, AngleCluster


SYSTEM_INSTRUCTION = """You are a financial news coverage gap analyst.
Given a set of articles about a major event (e.g. Union Budget), identify important topics
or angles that NONE of the articles adequately cover — the blind spots.

Rules:
1. Focus on topics a well-informed reader would expect to see covered.
2. Be specific — "agriculture impact" is better than "some sectors missing".
3. Explain why each blind spot matters.
4. Limit to 3-5 most important gaps. Do not over-flag.
5. Only flag genuine gaps — if a topic is covered even briefly, it's not a blind spot.
"""


async def detect_blind_spots(
    articles: list[Article],
    angles: list[AngleCluster],
    topic: str = "Union Budget 2026",
    session_id: str = "default",
) -> list[dict]:
    """Detect coverage blind spots — important topics no article covers.

    Returns:
        List of blind spot dicts with topic, why_it_matters, expected_coverage,
        and importance (high/medium).
    """
    with AuditTimer() as timer:
        # Build what IS covered
        covered_angles = [a.angle_name for a in angles]
        covered_themes = []
        for a in angles:
            covered_themes.extend(a.key_themes)

        article_titles = [f"[{a.id}] {a.title}" for a in articles]

        prompt = f"""This news event — "{topic}" — is covered by {len(articles)} articles across these angles:
{covered_angles}

Key themes covered: {list(set(covered_themes))}

Article titles:
{chr(10).join(article_titles)}

What IMPORTANT topics or perspectives are MISSING from this coverage? What would a
well-informed reader expect to see but won't find in any of these articles?

Return JSON:
{{
  "blind_spots": [
    {{
      "topic": "Specific uncovered topic",
      "why_it_matters": "Why a reader needs this perspective",
      "expected_coverage": "What kind of article should have covered this",
      "importance": "high|medium"
    }}
  ],
  "coverage_completeness": "high|medium|low",
  "total_gaps_found": 3
}}"""

        response = await call_llm(
            prompt=prompt,
            model="pro",
            system_instruction=SYSTEM_INSTRUCTION,
            response_mime_type="application/json",
            temperature=0.4,
        )

        try:
            data = parse_json_response(response)
            blind_spots = data.get("blind_spots", [])
        except Exception:
            blind_spots = []

    log_agent_step(
        agent_name="BlindSpotDetector",
        action="detect_blind_spots",
        model_used="pro",
        input_summary=f"{len(articles)} articles, {len(angles)} angles, topic: {topic}",
        output_summary=f"{len(blind_spots)} blind spots found",
        latency_ms=timer.elapsed_ms,
        session_id=session_id,
    )

    return blind_spots
