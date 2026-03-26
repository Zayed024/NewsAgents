"""FactChecker agent — verifies script claims against source article."""

from src.llm import call_llm, parse_json_response
from src.config import GEMINI_FLASH
from src.audit import log_agent_step, AuditTimer
from src.models import Article, VideoScript, FactCheckReport, FactCheckClaim


SYSTEM_INSTRUCTION = """You are a fact-checking specialist for news video scripts.
Compare every factual claim in the generated script against the source article.
Flag any claim that is not directly supported by the source.
Be strict — accuracy is paramount for news content."""


async def check_facts(
    script: VideoScript,
    source_article: Article,
    session_id: str = "default",
) -> FactCheckReport:
    """Verify script claims against source article.

    Args:
        script: The generated Hindi script
        source_article: Original article to check against
        session_id: Session ID for audit

    Returns:
        FactCheckReport with claim-by-claim verification
    """
    with AuditTimer() as timer:
        prompt = f"""Compare every factual claim in this Hindi script against the source article.

SCRIPT (Hindi):
{script.script_hindi}

SCRIPT (Transliteration for reference):
{script.script_transliteration}

KEY FACTS CLAIMED IN SCRIPT:
{script.key_facts_used}

SOURCE ARTICLE:
Title: {source_article.title}
Content: {source_article.content}

For each factual claim in the script, check if it is supported by the source article.

Return JSON:
{{
  "claims": [
    {{
      "claim": "The claim made in the script (in English)",
      "source_match": true,
      "source_text": "The exact text from the source article that supports this claim"
    }},
    {{
      "claim": "An unsupported claim",
      "source_match": false,
      "source_text": ""
    }}
  ],
  "accuracy_score": 0.95,
  "flagged_claims": ["Any claims that are inaccurate or unsupported"]
}}"""

        response = await call_llm(
            prompt=prompt,
            model=GEMINI_FLASH,
            system_instruction=SYSTEM_INSTRUCTION,
            response_mime_type="application/json",
            temperature=0.2,
        )

        try:
            data = parse_json_response(response)
            result = FactCheckReport(
                claims=[FactCheckClaim(**c) for c in data.get("claims", [])],
                accuracy_score=data.get("accuracy_score", 0.0),
                flagged_claims=data.get("flagged_claims", []),
            )
        except Exception:
            result = FactCheckReport(
                claims=[],
                accuracy_score=0.0,
                flagged_claims=["[Fact check could not be completed — manual review required]"],
            )

    log_agent_step(
        agent_name="FactChecker",
        action="check_facts",
        model_used=GEMINI_FLASH,
        input_summary=f"Script: {len(script.script_hindi)} chars vs article: {source_article.title[:60]}",
        output_summary=f"Accuracy: {result.accuracy_score}, Flagged: {len(result.flagged_claims)}",
        latency_ms=timer.elapsed_ms,
        session_id=session_id,
    )

    return result
