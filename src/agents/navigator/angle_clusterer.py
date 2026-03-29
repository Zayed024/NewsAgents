"""AngleClustering agent — clusters articles into navigable angles."""

from src.llm import call_llm, parse_json_response
from src.audit import log_agent_step, AuditTimer
from src.models import AngleCluster, AngleClusters, Article, EntityMap


SYSTEM_INSTRUCTION = """You are a senior news editor creating an interactive briefing structure.
Given articles about a major news event, cluster them into 5-7 distinct "angles" or perspectives.
Each angle should represent a unique lens through which to understand the event.
Angles should NOT overlap — a reader navigating between angles should get genuinely different insights.
Examples of angles: "Macro Impact", "Sector Winners & Losers", "Market Reaction", "Expert Commentary", "Historical Context", "Personal Impact / Tax Changes"."""


async def cluster_angles(
    articles: list[Article],
    article_metadata: list[dict],
    entity_map: EntityMap,
    session_id: str = "default",
) -> list[AngleCluster]:
    """Cluster articles into 5-7 navigable angles.

    Args:
        articles: Original articles
        article_metadata: Enriched metadata
        entity_map: Entity-to-article index
        session_id: Session ID for audit trail

    Returns:
        List of AngleCluster objects
    """
    with AuditTimer() as timer:
        # Build article summaries for the prompt
        summaries = ""
        for m in article_metadata:
            summaries += f"\n{m['id']}: [{m.get('category', 'general')}] {m['title']}"
            summaries += f"\n  Summary: {m.get('summary', 'N/A')}"
            summaries += f"\n  Sentiment: {m.get('sentiment', 'neutral')}\n"

        prompt = f"""Analyze these {len(articles)} articles about the Union Budget 2026 and cluster them into 5-7 distinct angles.

ARTICLES:
{summaries}

KEY ENTITIES:
- Sectors mentioned: {list(entity_map.sectors.keys())[:15]}
- People mentioned: {list(entity_map.people.keys())[:10]}
- Policies mentioned: {list(entity_map.policies.keys())[:10]}

Return a JSON object:
{{
  "angles": [
    {{
      "angle_name": "Macro Impact",
      "description": "How the budget affects GDP, fiscal deficit, and overall economic trajectory",
      "article_ids": ["budget-001", "budget-006"],
      "key_themes": ["fiscal deficit", "GDP growth", "government borrowing"]
    }}
  ]
}}

Rules:
1. Create exactly 5-7 angles
2. Every article must appear in at least one angle
3. Minimize overlap — each angle should feel distinct
4. Order angles from broadest (macro) to most specific (personal impact)"""

        response = await call_llm(
            prompt=prompt,
            model="pro",
            system_instruction=SYSTEM_INSTRUCTION,
            response_mime_type="application/json",
            temperature=0.4,
        )

        try:
            data = parse_json_response(response)
            clusters = AngleClusters(**data)
            result = clusters.angles
        except Exception:
            # Fallback: cluster by category
            result = _fallback_clustering(articles, article_metadata)

    log_agent_step(
        agent_name="AngleClustering",
        action="cluster_angles",
        model_used="pro",
        input_summary=f"{len(articles)} articles, {len(entity_map.sectors)} sectors",
        output_summary=f"{len(result)} angles created: {[a.angle_name for a in result]}",
        latency_ms=timer.elapsed_ms,
        session_id=session_id,
    )

    return result


def _fallback_clustering(articles: list[Article], metadata: list[dict]) -> list[AngleCluster]:
    """Fallback: cluster by article category."""
    category_map: dict[str, list[str]] = {}
    for m in metadata:
        cat = m.get("category", "general")
        category_map.setdefault(cat, []).append(m["id"])

    angle_names = {
        "macro": ("Macro Impact", "GDP, fiscal deficit, and economic outlook"),
        "sector": ("Sector Winners & Losers", "Industry-specific impacts"),
        "market": ("Market Reaction", "Stock market and investor sentiment"),
        "expert": ("Expert Commentary", "Analysis from economists and industry leaders"),
        "historical": ("Historical Context", "Comparison with previous budgets"),
        "tax": ("Personal Impact & Tax", "Tax changes and personal finance implications"),
    }

    result = []
    for cat, ids in category_map.items():
        name, desc = angle_names.get(cat, (cat.title(), f"Articles about {cat}"))
        result.append(AngleCluster(
            angle_name=name,
            description=desc,
            article_ids=ids,
            key_themes=[cat],
        ))

    return result
