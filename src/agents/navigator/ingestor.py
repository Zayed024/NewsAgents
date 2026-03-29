"""ArticleIngestor agent — parses articles and extracts structured metadata."""

import re

from src.llm import call_llm, parse_json_response
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
            model="flash",
            system_instruction=SYSTEM_INSTRUCTION,
            response_mime_type="application/json",
            temperature=0.3,
        )

        try:
            result = parse_json_response(response)
        except Exception:
            # If parsing fails, use deterministic extraction so downstream agents still have useful context.
            result = [_deterministic_article_metadata(a) for a in articles]

    log_agent_step(
        agent_name="ArticleIngestor",
        action="ingest_articles",
        model_used="flash",
        input_summary=f"{len(articles)} articles",
        output_summary=f"{len(result)} metadata entries extracted",
        latency_ms=timer.elapsed_ms,
        status="success" if isinstance(result, list) else "fallback",
        session_id=session_id,
    )

    return result


def _deterministic_article_metadata(article: Article) -> dict:
    text = f"{article.title}. {article.content}"
    summary = _first_sentence(article.content)
    return {
        "id": article.id,
        "title": article.title,
        "category": article.category,
        "summary": summary,
        "sentiment": _estimate_sentiment(text),
        "key_entities": {
            "people": _extract_people(text),
            "companies": _extract_companies(text),
            "sectors": _extract_sectors(text, article.tags),
            "policies": _extract_policies(text),
        },
        "relevance_tags": list(dict.fromkeys(article.tags + _extract_tags_from_text(text)))[:10],
    }


def _first_sentence(content: str) -> str:
    parts = re.split(r"(?<=[.!?])\s+", content.strip())
    return parts[0][:220] if parts and parts[0] else content[:220]


def _estimate_sentiment(text: str) -> str:
    lowered = text.lower()
    pos = sum(1 for w in ["boost", "growth", "surge", "gain", "positive", "improve", "reform"] if w in lowered)
    neg = sum(1 for w in ["risk", "concern", "decline", "dip", "negative", "stress", "slowdown"] if w in lowered)
    if pos > neg + 1:
        return "positive"
    if neg > pos + 1:
        return "negative"
    if pos > 0 and neg > 0:
        return "mixed"
    return "neutral"


def _extract_people(text: str) -> list[str]:
    matches = re.findall(r"\b[A-Z][a-z]+\s+[A-Z][a-z]+\b", text)
    blacklist = {"Union Budget", "Economic Times", "Budget Day", "Market Reaction"}
    out = []
    for m in matches:
        if m in blacklist:
            continue
        if m not in out:
            out.append(m)
    return out[:8]


def _extract_companies(text: str) -> list[str]:
    patterns = [
        r"\b[A-Z][A-Za-z0-9&.-]{1,30}\s+(?:Bank|AMC|Ltd|Limited|Corp|Corporation|Systems|Technologies|Pharma)\b",
        r"\b(?:Infosys|TCS|Wipro|Cipla|Apollo Hospitals|HDFC Bank|ICICI Bank|SBI)\b",
    ]
    out = []
    for pat in patterns:
        for match in re.findall(pat, text):
            if match not in out:
                out.append(match)
    return out[:8]


def _extract_sectors(text: str, tags: list[str]) -> list[str]:
    lowered = text.lower()
    sector_terms = [
        "it", "technology", "pharma", "healthcare", "banking", "real estate",
        "infrastructure", "defence", "agriculture", "automobile", "fmcg",
    ]
    out = [term for term in sector_terms if term in lowered]
    for tag in tags:
        t = tag.replace("-", " ").lower()
        if any(k in t for k in ["sector", "bank", "pharma", "health", "real", "it", "infra"]):
            out.append(t)
    deduped = []
    for s in out:
        normalized = s.title()
        if normalized not in deduped:
            deduped.append(normalized)
    return deduped[:8]


def _extract_policies(text: str) -> list[str]:
    lowered = text.lower()
    policy_phrases = [
        "fiscal deficit", "capital expenditure", "capex", "tax", "income tax",
        "deposit insurance", "borrowing programme", "rbi rate cut", "pli", "customs duty",
    ]
    out = [p.title() for p in policy_phrases if p in lowered]
    return out[:8]


def _extract_tags_from_text(text: str) -> list[str]:
    lowered = text.lower()
    candidates = [
        "fiscal-deficit", "gdp-growth", "capital-expenditure", "market-reaction",
        "it-sector", "healthcare", "banking", "real-estate", "tax-changes", "rbi-policy",
    ]
    return [c for c in candidates if c.replace("-", " ") in lowered or c in lowered]
