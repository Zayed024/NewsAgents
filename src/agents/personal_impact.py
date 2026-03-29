"""Personal impact explainer for "So what does this mean for me?" interactions."""

from src.audit import AuditTimer, log_agent_step
from src.llm import call_llm, is_llm_unavailable_response, parse_json_response
from src.models import PersonalImpactSummary, UserProfile


SYSTEM_INSTRUCTION = """You are a personal finance and business impact explainer.
Given an article or briefing and a user profile, explain what the update means for that user.
Rules:
1. Keep output practical and personal, not generic.
2. Return exactly 3 bullet points.
3. Mention uncertainty when evidence is incomplete.
4. Never invent numbers or facts.
"""


async def generate_personal_impact(
    profile: UserProfile | dict,
    item_title: str,
    item_text: str,
    session_id: str = "default",
) -> PersonalImpactSummary:
    """Generate a profile-aware 3-bullet impact summary.

    Args:
        profile: User profile model or dict
        item_title: Article/briefing title
        item_text: Article/briefing body
        session_id: Audit session id

    Returns:
        PersonalImpactSummary
    """
    profile_dict = profile.model_dump() if isinstance(profile, UserProfile) else dict(profile)

    with AuditTimer() as timer:
        prompt = _build_prompt(profile_dict, item_title, item_text)
        response = await call_llm(
            prompt=prompt,
            model="pro",
            system_instruction=SYSTEM_INSTRUCTION,
            response_mime_type="application/json",
            temperature=0.3,
        )

        try:
            parsed = parse_json_response(response)
            summary = PersonalImpactSummary(**parsed)
            if len(summary.bullet_points) != 3 or is_llm_unavailable_response(summary.headline_impact):
                raise ValueError("Invalid personal impact payload")
        except Exception:
            summary = _fallback_personal_impact(profile_dict, item_title, item_text)

    log_agent_step(
        agent_name="PersonalImpactExplainer",
        action="generate_personal_impact",
        model_used="pro",
        input_summary=f"{profile_dict.get('role', 'User')} | {item_title[:120]}",
        output_summary=f"{summary.headline_impact[:140]} | bullets={len(summary.bullet_points)}",
        latency_ms=timer.elapsed_ms,
        session_id=session_id,
    )

    return summary


def _build_prompt(profile: dict, item_title: str, item_text: str) -> str:
    interests = profile.get("interests", []) or []
    exposure = profile.get("portfolio_exposure", []) or []

    return f"""User profile:
- Name: {profile.get('name', 'User')}
- Role: {profile.get('role', 'General')}
- Reading level: {profile.get('reading_level', 'intermediate')}
- Interests: {', '.join(interests) if interests else 'Not specified'}
- Portfolio exposure: {', '.join(exposure) if exposure else 'Not specified'}

Story:
- Title: {item_title}
- Content: {item_text[:3000]}

Return strict JSON:
{{
  "headline_impact": "One-sentence personal interpretation",
  "bullet_points": [
    "Specific impact bullet 1",
    "Specific impact bullet 2",
    "Specific impact bullet 3"
  ],
  "confidence": "low|medium|high",
  "caveat": "A short caveat about uncertainty or assumptions"
}}
"""


def _fallback_personal_impact(profile: dict, item_title: str, item_text: str) -> PersonalImpactSummary:
    role = (profile.get("role") or "User").strip()
    interests = profile.get("interests", []) or []
    top_interest = interests[0] if interests else "your key interests"

    lowered = f"{item_title} {item_text}".lower()

    if any(token in lowered for token in ["rate", "inflation", "rbi", "repo", "interest"]):
        lead = f"This update can change borrowing costs, savings returns, and risk appetite for a {role.lower()}."
    elif any(token in lowered for token in ["tax", "budget", "policy", "compliance"]):
        lead = f"This likely affects planning decisions and compliance priorities for a {role.lower()}."
    elif any(token in lowered for token in ["earnings", "profit", "guidance", "revenue"]):
        lead = f"This may alter valuation expectations and position sizing decisions for a {role.lower()}."
    else:
        lead = f"This matters because it may shift near-term decisions relevant to {top_interest}."

    bullets = [
        f"Immediate watch: track whether this changes short-term choices tied to {top_interest}.",
        "Portfolio/operations implication: revisit exposure to sectors most directly affected by this headline.",
        "Action signal: wait for one confirming datapoint before making major allocation or policy moves.",
    ]

    return PersonalImpactSummary(
        headline_impact=lead,
        bullet_points=bullets,
        confidence="medium",
        caveat="Fallback summary: validate with fresh disclosures and official guidance.",
    )
