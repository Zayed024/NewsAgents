"""Contrarian perspective generator for "Hear the other side" interactions."""

from src.audit import AuditTimer, log_agent_step
from src.llm import call_llm, is_llm_unavailable_response, parse_json_response
from src.models import ContrarianSummary


SYSTEM_INSTRUCTION = """You are a balanced market commentator.
Given a primary narrative, produce a thoughtful opposing interpretation.
Rules:
1. Keep both sides plausible and evidence-aware.
2. Avoid sensational claims.
3. Explicitly state what evidence would invalidate each side.
4. Do not invent data points.
"""


async def generate_contrarian_view(
    item_title: str,
    item_text: str,
    current_sentiment: str = "neutral",
    session_id: str = "default",
) -> ContrarianSummary:
    """Generate a compact opposing view for an article or synthesis."""
    with AuditTimer() as timer:
        prompt = _build_prompt(item_title, item_text, current_sentiment)
        response = await call_llm(
            prompt=prompt,
            model="pro",
            system_instruction=SYSTEM_INSTRUCTION,
            response_mime_type="application/json",
            temperature=0.35,
        )

        try:
            parsed = parse_json_response(response)
            summary = ContrarianSummary(**parsed)
            if is_llm_unavailable_response(summary.primary_take):
                raise ValueError("LLM unavailable")
        except Exception:
            summary = _fallback_contrarian(item_title, item_text, current_sentiment)

    log_agent_step(
        agent_name="ContrarianView",
        action="generate_contrarian_view",
        model_used="pro",
        input_summary=f"{current_sentiment} | {item_title[:120]}",
        output_summary=f"{summary.other_side_take[:160]}",
        latency_ms=timer.elapsed_ms,
        session_id=session_id,
    )

    return summary


def _build_prompt(item_title: str, item_text: str, current_sentiment: str) -> str:
    sentiment = (current_sentiment or "neutral").lower()

    return f"""Story:
- Title: {item_title}
- Context: {item_text[:3000]}
- Current sentiment: {sentiment}

Construct the opposite side thoughtfully:
- If current sentiment is bullish, write a cautious/bear case.
- If current sentiment is bearish, write a recovery/bull case.
- If neutral, write consensus vs skeptic framing.

Return strict JSON:
{{
  "primary_take": "What the main narrative currently implies",
  "other_side_take": "Strongest credible opposing interpretation",
  "strongest_evidence_for_other_side": "Single strongest evidence that supports the opposite view",
  "what_would_change_my_mind": "Concrete new data that would flip this view"
}}
"""


def _fallback_contrarian(item_title: str, item_text: str, current_sentiment: str) -> ContrarianSummary:
    sentiment = (current_sentiment or "neutral").lower()
    lower = f"{item_title} {item_text}".lower()

    if sentiment == "bullish":
        other = "The move may be over-discounting near-term upside and ignoring execution, valuation, or policy lag risks."
        evidence = "Recent rallies on narrative alone often retrace when guidance fails to improve in subsequent disclosures."
    elif sentiment == "bearish":
        other = "The downside case may be too crowded, and even small positive surprises can trigger a sharp rebound."
        evidence = "Bearish positioning tends to unwind quickly when indicators stabilize rather than worsen."
    else:
        other = "The consensus may be missing second-order effects that could materially alter outcomes."
        evidence = "Mixed signals often resolve non-linearly once one leading indicator decisively turns."

    if any(token in lower for token in ["rate", "rbi", "inflation"]):
        change = "A clear trend in inflation and forward rate guidance over 2-3 policy cycles would settle the debate."
    elif any(token in lower for token in ["earnings", "revenue", "margin"]):
        change = "Two consecutive quarters of margin and cash-flow confirmation would validate one side decisively."
    else:
        change = "A verified shift in leading indicators and management/policy follow-through would change this view."

    return ContrarianSummary(
        primary_take="The prevailing read is directionally valid but not yet fully confirmed.",
        other_side_take=other,
        strongest_evidence_for_other_side=evidence,
        what_would_change_my_mind=change,
    )
