"""BreakingIngestor agent — extracts 5W1H facts and key numbers from breaking news."""

from src.llm import call_llm, parse_json_response
from src.config import GEMINI_FLASH
from src.audit import log_agent_step, AuditTimer
from src.models import Article


SYSTEM_INSTRUCTION = """You are a breaking news fact extractor.
Given a breaking news article, extract the essential 5W1H facts and key numbers.
Be precise and factual — every fact must be directly supported by the article.
Return structured JSON."""


async def extract_breaking_facts(article: Article, session_id: str = "default") -> dict:
    """Extract key facts from a breaking news article.

    Args:
        article: The breaking news article
        session_id: Session ID for audit

    Returns:
        Dict with structured facts
    """
    with AuditTimer() as timer:
        prompt = f"""Extract all key facts from this breaking news article:

TITLE: {article.title}
CONTENT: {article.content}

Return JSON:
{{
  "what": "What happened — one sentence",
  "who": "Key parties involved",
  "when": "When it happened",
  "where": "Where (location/entity)",
  "why": "Why / what led to this",
  "how": "How it happened / process",
  "key_numbers": [
    {{"label": "Total debt", "value": "Rs 47,000 crore", "context": "owed to 14 banks"}},
    {{"label": "Largest creditor", "value": "SBI", "context": "Rs 12,000 crore exposure"}}
  ],
  "impact_points": [
    "Impact on banking sector",
    "Impact on employees",
    "Impact on ongoing projects"
  ],
  "entities": {{
    "company": "company name",
    "people": ["person1"],
    "banks": ["bank1", "bank2"],
    "regulators": ["NCLT", "SEBI"]
  }}
}}"""

        response = await call_llm(
            prompt=prompt,
            model=GEMINI_FLASH,
            system_instruction=SYSTEM_INSTRUCTION,
            response_mime_type="application/json",
            temperature=0.2,
        )

        try:
            result = parse_json_response(response)
        except Exception:
            result = {
                "what": article.title,
                "who": "See article",
                "when": article.published_at,
                "where": "India",
                "why": "See article for details",
                "how": "See article for details",
                "key_numbers": [],
                "impact_points": [],
                "entities": {"company": "", "people": [], "banks": [], "regulators": []},
            }

    log_agent_step(
        agent_name="BreakingIngestor",
        action="extract_breaking_facts",
        model_used=GEMINI_FLASH,
        input_summary=f"Article: {article.title[:80]}",
        output_summary=f"Extracted {len(result.get('key_numbers', []))} key numbers, {len(result.get('impact_points', []))} impacts",
        latency_ms=timer.elapsed_ms,
        session_id=session_id,
    )

    return result
