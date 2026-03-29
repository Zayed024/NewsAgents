"""BreakingIngestor agent — extracts 5W1H facts and key numbers from breaking news."""

import re
from src.llm import call_llm, parse_json_response
from src.audit import log_agent_step, AuditTimer
from src.models import Article


SYSTEM_INSTRUCTION = """You are a breaking news fact extractor.
Given a breaking news article, extract the essential 5W1H facts and key numbers.
Be precise and factual — every fact must be directly supported by the article.
Return structured JSON."""


def _heuristic_key_numbers(text: str) -> list[dict]:
  """Extract key numeric facts from article text when LLM output is sparse."""
  numbers: list[dict] = []
  lines = [ln.strip(" -\t") for ln in text.splitlines() if ln.strip()]

  # Capture bullet-like exposures: "State Bank of India: Rs 12,000 crore"
  exposure_pattern = re.compile(r"^(?P<label>[A-Za-z .&()]+):\s*(?P<value>Rs\s*[\d,]+\s*crore)", re.IGNORECASE)
  for ln in lines:
    m = exposure_pattern.search(ln)
    if m:
      numbers.append({
        "label": m.group("label").strip(),
        "value": m.group("value").strip(),
        "context": "creditor exposure",
      })

  # Generic monetary numbers in prose.
  money_pattern = re.compile(r"(Rs\s*[\d,]+\s*crore)", re.IGNORECASE)
  money_vals = money_pattern.findall(text)
  for val in money_vals[:6]:
    if any(n.get("value") == val for n in numbers):
      continue
    numbers.append({
      "label": "Financial figure",
      "value": val,
      "context": "from source article",
    })

  return numbers[:8]


def _heuristic_impacts(text: str) -> list[str]:
  """Derive likely impact points from source text keywords."""
  lower = text.lower()
  impacts: list[str] = []

  if "bank" in lower or "creditor" in lower:
    impacts.append("Banking sector and lender balance sheets may face near-term stress.")
  if "employ" in lower or "worker" in lower:
    impacts.append("Employees and contractors face execution and payment uncertainty.")
  if "project" in lower or "construction" in lower or "highway" in lower:
    impacts.append("Ongoing infrastructure projects may see delays or handover risk.")
  if "stock" in lower or "trading" in lower or "sebi" in lower:
    impacts.append("Market sentiment can stay volatile for linked stocks and sectors.")

  return impacts[:5]


def _enrich_facts(article: Article, facts: dict) -> dict:
  """Ensure required structure is populated with deterministic fallbacks."""
  facts = facts or {}
  facts.setdefault("what", article.title)
  facts.setdefault("who", "See article")
  facts.setdefault("when", article.published_at)
  facts.setdefault("where", "India")
  facts.setdefault("why", "See article for details")
  facts.setdefault("how", "See article for details")
  facts.setdefault("entities", {"company": "", "people": [], "banks": [], "regulators": []})

  if not facts.get("key_numbers"):
    facts["key_numbers"] = _heuristic_key_numbers(article.content)

  if not facts.get("impact_points"):
    facts["impact_points"] = _heuristic_impacts(article.content)

  return facts


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
            model="flash",
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

            result = _enrich_facts(article, result)

    log_agent_step(
        agent_name="BreakingIngestor",
        action="extract_breaking_facts",
        model_used="flash",
        input_summary=f"Article: {article.title[:80]}",
        output_summary=f"Extracted {len(result.get('key_numbers', []))} key numbers, {len(result.get('impact_points', []))} impacts",
        latency_ms=timer.elapsed_ms,
        session_id=session_id,
    )

    return result
