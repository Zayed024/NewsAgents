"""SynthesisEngine agent — produces dense synthesis for each angle cluster."""

import re

from src.llm import call_llm, parse_json_response, is_llm_unavailable_response
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
                model="pro",
                system_instruction=SYSTEM_INSTRUCTION,
                response_mime_type="application/json",
                temperature=0.5,
            )

            try:
                data = parse_json_response(response)
                entry = SynthesisEntry(**data)
            except Exception:
                entry = _deterministic_synthesis_entry(angle, article_map)

            if is_llm_unavailable_response(entry.synthesis):
                entry = _deterministic_synthesis_entry(angle, article_map)

            results.append(entry)

        log_agent_step(
            agent_name="SynthesisEngine",
            action=f"synthesize_{angle.angle_name}",
            model_used="pro",
            input_summary=f"Angle: {angle.angle_name}, {len(angle.article_ids)} articles",
            output_summary=f"Synthesis: {len(entry.synthesis)} chars, {len(entry.key_takeaways)} takeaways",
            latency_ms=timer.elapsed_ms,
            session_id=session_id,
        )

    return results


def _deterministic_synthesis_entry(
    angle: AngleCluster,
    article_map: dict[str, Article],
) -> SynthesisEntry:
    cluster_articles = [article_map[aid] for aid in angle.article_ids if aid in article_map]
    cited_ids = [a.id for a in cluster_articles]

    scored_sentences: list[tuple[int, str, str]] = []
    for article in cluster_articles:
        for sentence in _split_sentences(article.content):
            s = sentence.strip()
            if len(s) < 40:
                continue
            score = _sentence_score(s, angle.key_themes)
            scored_sentences.append((score, s, article.id))

    scored_sentences.sort(key=lambda x: x[0], reverse=True)
    top = scored_sentences[:6]

    if not top:
        synthesis = (
            f"This angle, {angle.angle_name}, spans {len(cluster_articles)} ET articles and highlights "
            f"{angle.description.lower()}. Available evidence suggests notable movement across themes "
            f"{', '.join(angle.key_themes[:4])}."
        )
        takeaways = [
            f"{angle.angle_name} is supported by {len(cluster_articles)} source articles.",
            f"Primary themes include {', '.join(angle.key_themes[:3])}.",
            "Data points should be interpreted with implementation timelines in mind.",
        ]
        return SynthesisEntry(
            angle_name=angle.angle_name,
            synthesis=synthesis,
            source_articles=cited_ids,
            key_takeaways=takeaways,
        )

    synthesis_lines = [
        f"In the {angle.angle_name} lens, ET coverage indicates {angle.description.lower()}.",
    ]
    for _, sent, aid in top[:4]:
        synthesis_lines.append(f"{sent} [{aid}]")

    synthesis_lines.append(
        "Taken together, these reports suggest the impact will depend on execution speed, financing conditions, and follow-up policy circulars."
    )

    takeaways = []
    for _, sent, aid in top[:5]:
        short = sent[:170].strip()
        if len(sent) > 170:
            short += "..."
        takeaways.append(f"{short} [{aid}]")

    return SynthesisEntry(
        angle_name=angle.angle_name,
        synthesis=" ".join(synthesis_lines),
        source_articles=cited_ids,
        key_takeaways=takeaways[:5],
    )


def _split_sentences(text: str) -> list[str]:
    return [s for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]


def _sentence_score(sentence: str, themes: list[str]) -> int:
    lowered = sentence.lower()
    score = 1
    if re.search(r"\b\d+(?:\.\d+)?\b", sentence):
        score += 2
    for theme in themes:
        if theme.lower() in lowered:
            score += 2
    for term in ["rs", "%", "crore", "lakh", "growth", "deficit", "tax", "allocation"]:
        if term in lowered:
            score += 1
    return score
