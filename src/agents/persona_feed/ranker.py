"""ContentRanker agent — ranks and filters articles based on user preferences."""

from src.llm import call_llm, parse_json_response
from src.audit import log_agent_step, AuditTimer
from src.models import Article


SYSTEM_INSTRUCTION = """You are a content relevance ranking specialist.
Given a set of articles and a user's content preferences, rank the articles by relevance to this specific user.
Consider their interests, reading level, professional role, and portfolio exposure.
Assign a relevance score (0-1) to each article."""


async def rank_articles(
    articles: list[Article],
    preferences: dict,
    user_name: str = "User",
    session_id: str = "default",
) -> list[dict]:
    """Rank articles by relevance to a user's preferences.

    Args:
        articles: Available articles
        preferences: User content preferences from profiler
        user_name: User name for audit
        session_id: Session ID for audit

    Returns:
        List of dicts with article_id and relevance_score, sorted by score desc
    """
    with AuditTimer() as timer:
        articles_summary = ""
        for a in articles:
            articles_summary += f"\n{a.id}: [{a.category}] {a.title} - {a.content[:100]}..."

        prompt = f"""Rank these articles for a user with these preferences:
- Depth: {preferences.get('content_depth', 'intermediate')}
- Priority topics: {preferences.get('priority_topics', [])}
- Depriority topics: {preferences.get('depriority_topics', [])}
- Role context: {preferences.get('framing_style', '')}

ARTICLES:
{articles_summary}

Return a JSON array sorted by relevance (highest first):
[
  {{"article_id": "home-001", "relevance_score": 0.95, "reason": "Directly relevant to user's macro policy interest"}},
  {{"article_id": "home-003", "relevance_score": 0.85, "reason": "Matches personal finance interest"}}
]

Include ALL articles. Assign scores between 0.0 and 1.0."""

        response = await call_llm(
            prompt=prompt,
            model="flash",
            system_instruction=SYSTEM_INSTRUCTION,
            response_mime_type="application/json",
            temperature=0.3,
        )

        try:
            result = parse_json_response(response)
            if isinstance(result, list):
                result.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)
        except Exception:
            # Fallback: basic keyword matching
            result = _fallback_ranking(articles, preferences)

    log_agent_step(
        agent_name="ContentRanker",
        action="rank_articles",
        model_used="flash",
        input_summary=f"User: {user_name}, {len(articles)} articles",
        output_summary=f"Top article: {result[0]['article_id'] if result else 'none'}",
        latency_ms=timer.elapsed_ms,
        session_id=session_id,
    )

    return result


def _fallback_ranking(articles: list[Article], preferences: dict) -> list[dict]:
    """Fallback ranking based on keyword matching."""
    priority = set(t.lower() for t in preferences.get("priority_topics", []))
    result = []

    for a in articles:
        tags = set(t.lower() for t in a.tags)
        overlap = len(tags & priority)
        score = min(0.5 + (overlap * 0.15), 1.0)
        result.append({
            "article_id": a.id,
            "relevance_score": score,
            "reason": f"Matched {overlap} priority topics",
        })

    result.sort(key=lambda x: x["relevance_score"], reverse=True)
    return result
