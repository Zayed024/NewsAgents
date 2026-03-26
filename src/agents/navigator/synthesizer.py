"""SynthesisEngine agent — produces dense synthesis for each angle cluster."""

from src.llm import call_llm, parse_json_response
from src.config import GEMINI_PRO
from src.audit import log_agent_step, AuditTimer
from src.models import AngleCluster, Article, SynthesisEntry, BriefingSynthesis


SYSTEM_INSTRUCTION = """You are a senior editorial synthesizer for Economic Times.
Your job is to take multiple articles about the same angle of a news event and produce a single, dense, insightful synthesis.

Rules:
1. DO NOT simply summarize each article. SYNTHESIZE — combine insights, highlight agreements/disagreements, surface patterns.
2. Cite sources using [Article ID] notation inline.
3. Include specific numbers, quotes, and data points.
4. Each synthesis should be 200-400 words — dense and information-rich.
5. Include 3-5 key takeaways as bullet points.
6. The synthesis for each angle MUST be distinct — no overlapping content between angles."""


async def synthesize_angles(
    angles: list[AngleCluster],
    articles: list[Article],
    session_id: str = "default",
) -> list[SynthesisEntry]:
    """Produce dense synthesis for each angle cluster.

    Args:
        angles: Clustered angles from AngleClustering
        articles: Original articles
        session_id: Session ID for audit trail

    Returns:
        List of SynthesisEntry objects, one per angle
    """
    # Build article lookup
    article_map = {a.id: a for a in articles}
    results = []

    for angle in angles:
        with AuditTimer() as timer:
            # Get full content of articles in this cluster
            cluster_articles = ""
            for aid in angle.article_ids:
                if aid in article_map:
                    a = article_map[aid]
                    cluster_articles += f"\n---\n[{a.id}] {a.title}\nBy: {a.author}\n{a.content}\n"

            prompt = f"""Synthesize these articles under the angle: "{angle.angle_name}"
Description: {angle.description}
Key themes: {angle.key_themes}

ARTICLES IN THIS CLUSTER:
{cluster_articles}

Produce a JSON response:
{{
  "angle_name": "{angle.angle_name}",
  "synthesis": "A 200-400 word synthesis paragraph. Cite articles as [budget-XXX]. Include specific numbers and data points. Do NOT just summarize — synthesize patterns, agreements, contradictions.",
  "source_articles": ["budget-001", "budget-002"],
  "key_takeaways": [
    "Takeaway 1 with specific number",
    "Takeaway 2",
    "Takeaway 3"
  ]
}}"""

            response = await call_llm(
                prompt=prompt,
                model=GEMINI_PRO,
                system_instruction=SYSTEM_INSTRUCTION,
                response_mime_type="application/json",
                temperature=0.5,
            )

            try:
                data = parse_json_response(response)
                entry = SynthesisEntry(**data)
            except Exception:
                # Fallback: basic concatenation
                entry = SynthesisEntry(
                    angle_name=angle.angle_name,
                    synthesis=f"[Synthesis pending] This angle covers: {angle.description}. "
                              f"Key themes: {', '.join(angle.key_themes)}. "
                              f"Based on {len(angle.article_ids)} articles.",
                    source_articles=angle.article_ids,
                    key_takeaways=angle.key_themes,
                )

            results.append(entry)

        log_agent_step(
            agent_name="SynthesisEngine",
            action=f"synthesize_{angle.angle_name}",
            model_used=GEMINI_PRO,
            input_summary=f"Angle: {angle.angle_name}, {len(angle.article_ids)} articles",
            output_summary=f"Synthesis: {len(entry.synthesis)} chars, {len(entry.key_takeaways)} takeaways",
            latency_ms=timer.elapsed_ms,
            session_id=session_id,
        )

    return results
