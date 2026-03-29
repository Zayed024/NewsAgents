"""ContentAdapter agent — rewrites article content to match user's format and depth preferences."""

from src.llm import call_llm, parse_json_response
from src.audit import log_agent_step, AuditTimer
from src.models import Article, FeedItem


SYSTEM_INSTRUCTION = """You are a content adaptation specialist for Economic Times.
Your job is to rewrite news articles to match a specific user's reading level, format preference, and interests.

Adaptation strategies by user type:
- EXPERT/CFO: Data-dense executive summary. Lead with key numbers. Policy implications. No analogies needed. Include data tables if relevant.
- BEGINNER/YOUNG INVESTOR: ELI5 style. Use everyday analogies. Replace jargon with simple Hindi/English explanations. "Think of it as..." framing. Short paragraphs. End with "What this means for you."
- INTERMEDIATE: Standard journalistic format with added context.

The goal is that two users reading the same article should get genuinely DIFFERENT content — not just reordered sentences."""


async def adapt_articles(
    articles: list[Article],
    rankings: list[dict],
    preferences: dict,
    user_name: str = "User",
    top_n: int = 5,
    session_id: str = "default",
) -> list[FeedItem]:
    """Adapt top-ranked articles to match user preferences.

    Args:
        articles: All available articles
        rankings: Ranked article list from ranker
        preferences: User content preferences
        user_name: User name for context
        top_n: Number of articles to adapt
        session_id: Session ID for audit

    Returns:
        List of adapted FeedItem objects
    """
    article_map = {a.id: a for a in articles}
    top_ids = [r["article_id"] for r in rankings[:top_n]]
    results = []

    for aid in top_ids:
        article = article_map.get(aid)
        if not article:
            continue

        with AuditTimer() as timer:
            prompt = f"""Adapt this article for a user with these preferences:
- Content depth: {preferences.get('content_depth', 'intermediate')}
- Format: {preferences.get('format_preference', 'standard')}
- Tone: {preferences.get('tone', 'conversational')}
- Jargon level: {preferences.get('jargon_level', 'medium')}
- Framing style: {preferences.get('framing_style', '')}
- Max length: {preferences.get('max_article_length_words', 400)} words

ORIGINAL ARTICLE:
Title: {article.title}
Content: {article.content}

Return JSON:
{{
  "article_id": "{article.id}",
  "original_title": "{article.title}",
  "adapted_title": "Rewritten title matching user's level",
  "adapted_content": "Fully rewritten content matching the user's preferences. This should be genuinely different from the original — not just shortened.",
  "format_type": "executive_summary|explainer|data_table|card",
  "relevance_score": 0.9,
  "adaptation_notes": "What was changed and why"
}}"""

            response = await call_llm(
                prompt=prompt,
                model="pro",
                system_instruction=SYSTEM_INSTRUCTION,
                response_mime_type="application/json",
                temperature=0.6,
            )

            try:
                data = parse_json_response(response)
                item = FeedItem(**data)
            except Exception:
                item = FeedItem(
                    article_id=article.id,
                    original_title=article.title,
                    adapted_title=article.title,
                    adapted_content=article.content[:preferences.get("max_article_length_words", 400)],
                    format_type="standard",
                    relevance_score=0.5,
                    adaptation_notes="Adaptation failed — showing original content",
                )

            results.append(item)

        log_agent_step(
            agent_name="ContentAdapter",
            action=f"adapt_{article.id}",
            model_used="pro",
            input_summary=f"Article: {article.title[:60]} for {user_name}",
            output_summary=f"Format: {item.format_type}, {len(item.adapted_content)} chars",
            latency_ms=timer.elapsed_ms,
            session_id=session_id,
        )

    return results
