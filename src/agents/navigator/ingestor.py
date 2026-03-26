"""ArticleIngestor agent — parses articles and extracts structured metadata."""

from src.llm import call_llm, parse_json_response
from src.config import GEMINI_FLASH
from src.audit import log_agent_step, AuditTimer
from src.models import Article


SYSTEM_INSTRUCTION = """You are an article metadata extractor for a financial news platform.
Given a batch of news articles, extract structured metadata for each article.
For each article, identify:
1. The primary category (macro, sector, market, expert, historical, tax)
2. Key entities mentioned (people, companies, sectors, policies)
3. A 1-sentence summary
4. Sentiment (positive, negative, neutral, mixed)
5. Relevance tags

Return valid JSON array."""


async def ingest_articles(articles: list[Article], session_id: str = "default") -> list[dict]:
    """Parse articles and extract structured metadata.

    Args:
        articles: List of raw articles
        session_id: Session ID for audit trail

    Returns:
        List of enriched article metadata dicts
    """
    with AuditTimer() as timer:
        # Build prompt with all articles
        articles_text = ""
        for a in articles:
            articles_text += f"\n---\nID: {a.id}\nTitle: {a.title}\nCategory: {a.category}\nContent: {a.content[:500]}...\n"

        prompt = f"""Extract structured metadata for each of these {len(articles)} articles.

{articles_text}

Return a JSON array where each element has:
{{
  "id": "article id",
  "title": "article title",
  "category": "macro|sector|market|expert|historical|tax",
  "summary": "1-sentence summary",
  "sentiment": "positive|negative|neutral|mixed",
  "key_entities": {{
    "people": ["name1", "name2"],
    "companies": ["company1"],
    "sectors": ["sector1"],
    "policies": ["policy1"]
  }},
  "relevance_tags": ["tag1", "tag2"]
}}"""

        response = await call_llm(
            prompt=prompt,
            model=GEMINI_FLASH,
            system_instruction=SYSTEM_INSTRUCTION,
            response_mime_type="application/json",
            temperature=0.3,
        )

        try:
            result = parse_json_response(response)
        except Exception:
            # If parsing fails, return basic metadata from articles themselves
            result = [
                {
                    "id": a.id,
                    "title": a.title,
                    "category": a.category,
                    "summary": a.content[:100],
                    "sentiment": "neutral",
                    "key_entities": {"people": [], "companies": [], "sectors": [], "policies": []},
                    "relevance_tags": a.tags,
                }
                for a in articles
            ]

    log_agent_step(
        agent_name="ArticleIngestor",
        action="ingest_articles",
        model_used=GEMINI_FLASH,
        input_summary=f"{len(articles)} articles",
        output_summary=f"{len(result)} metadata entries extracted",
        latency_ms=timer.elapsed_ms,
        status="success" if isinstance(result, list) else "fallback",
        session_id=session_id,
    )

    return result
