"""Reading Path Optimizer — generates an optimal 2-minute reading sequence."""

from src.llm import call_llm, parse_json_response
from src.audit import log_agent_step, AuditTimer
from src.models import Article, SynthesisEntry, UserProfile


SYSTEM_INSTRUCTION = """You are a news reading strategist for busy professionals.
Given a set of articles and a user profile, design the OPTIMAL reading path — the
3-4 articles to read in sequence that builds understanding most efficiently.

Rules:
1. The sequence matters — article 1 should provide foundation, article 2 should deepen,
   article 3 should provide actionable insight or contrarian view.
2. Tailor the path to the user's role and interests.
3. Explain WHY this order, not just WHICH articles.
4. Total reading time should be under 2 minutes (assume 200 words/minute).
5. Each article in the path should add something the previous ones didn't cover.
"""


async def generate_reading_path(
    articles: list[Article],
    syntheses: list[SynthesisEntry],
    user_profile: UserProfile | None = None,
    session_id: str = "default",
) -> dict:
    """Generate an optimal reading path for a user.

    Returns:
        Dict with path (ordered list of article recommendations),
        total_estimated_minutes, and path_rationale.
    """
    with AuditTimer() as timer:
        profile_context = ""
        if user_profile:
            profile_context = f"""
USER PROFILE:
- Role: {user_profile.role}
- Interests: {user_profile.interests}
- Reading level: {user_profile.reading_level}
- Experience: {user_profile.investing_experience}
"""
        else:
            profile_context = "USER: General reader, intermediate financial literacy."

        article_summaries = ""
        for a in articles[:15]:
            word_count = len(a.content.split())
            read_time = round(word_count / 200, 1)
            article_summaries += f"\n[{a.id}] {a.title} ({read_time} min read, {a.category})\n"

        synth_context = ""
        for s in syntheses[:5]:
            synth_context += f"\n[{s.angle_name}]: {s.synthesis[:150]}...\n"

        prompt = f"""{profile_context}

AVAILABLE ARTICLES:
{article_summaries}

ANGLE SYNTHESES:
{synth_context}

Design an optimal 3-4 article reading path for this user. Total reading time must be under 2 minutes.
The sequence should build understanding progressively.

Return JSON:
{{
  "path": [
    {{
      "position": 1,
      "article_id": "budget-005",
      "title": "Article title",
      "read_time_minutes": 0.8,
      "why_read_this": "Provides the essential context on...",
      "what_you_learn": "After reading this, you understand..."
    }}
  ],
  "total_estimated_minutes": 1.8,
  "path_rationale": "One sentence explaining the overall reading strategy",
  "skip_if_short_on_time": "article-id to skip if you only have 1 minute"
}}"""

        response = await call_llm(
            prompt=prompt,
            model="pro",
            system_instruction=SYSTEM_INSTRUCTION,
            response_mime_type="application/json",
            temperature=0.4,
        )

        try:
            result = parse_json_response(response)
        except Exception:
            result = {
                "path": [],
                "total_estimated_minutes": 0,
                "path_rationale": "Reading path could not be generated.",
                "skip_if_short_on_time": "",
            }

    log_agent_step(
        agent_name="ReadingPathOptimizer",
        action="generate_reading_path",
        model_used="pro",
        input_summary=f"{len(articles)} articles, profile: {user_profile.role if user_profile else 'general'}",
        output_summary=f"Path: {len(result.get('path', []))} articles, {result.get('total_estimated_minutes', 0)} min",
        latency_ms=timer.elapsed_ms,
        session_id=session_id,
    )

    return result
