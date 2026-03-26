"""UserProfiler agent — analyzes user profile to determine content preferences."""

from src.llm import call_llm, parse_json_response
from src.config import GEMINI_FLASH
from src.audit import log_agent_step, AuditTimer
from src.models import UserProfile


SYSTEM_INSTRUCTION = """You are a user profiling specialist for a financial news platform.
Given a user profile, determine their content preferences including reading level,
preferred content formats, topics of interest, and how content should be framed for them."""


async def analyze_profile(profile: UserProfile, session_id: str = "default") -> dict:
    """Analyze a user profile to determine content delivery preferences.

    Args:
        profile: User profile
        session_id: Session ID for audit

    Returns:
        Dict with content preferences
    """
    with AuditTimer() as timer:
        prompt = f"""Analyze this user profile and determine content delivery preferences:

Name: {profile.name}
Age: {profile.age}
Role: {profile.role}
Interests: {profile.interests}
Reading Level: {profile.reading_level}
Preferred Format: {profile.preferred_format}
Portfolio: {profile.portfolio_exposure}
News Consumption: {profile.news_consumption}
Investing Experience: {profile.investing_experience}

Return JSON:
{{
  "content_depth": "expert|intermediate|beginner",
  "format_preference": "executive_summary|standard|explainer|visual_card",
  "tone": "formal_analytical|conversational|educational",
  "jargon_level": "high|medium|low",
  "priority_topics": ["topic1", "topic2"],
  "depriority_topics": ["topic1"],
  "data_preference": "data_tables_charts|inline_numbers|minimal_numbers",
  "framing_style": "Description of how to frame content for this user",
  "reading_grade_level": 12,
  "max_article_length_words": 500
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
            # Fallback based on reading_level
            result = _fallback_profile_analysis(profile)

    log_agent_step(
        agent_name="UserProfiler",
        action="analyze_profile",
        model_used=GEMINI_FLASH,
        input_summary=f"User: {profile.name}, {profile.role}",
        output_summary=f"Depth: {result.get('content_depth')}, Format: {result.get('format_preference')}",
        latency_ms=timer.elapsed_ms,
        session_id=session_id,
    )

    return result


def _fallback_profile_analysis(profile: UserProfile) -> dict:
    """Fallback profile analysis without LLM."""
    if profile.reading_level == "expert":
        return {
            "content_depth": "expert",
            "format_preference": "executive_summary",
            "tone": "formal_analytical",
            "jargon_level": "high",
            "priority_topics": profile.interests,
            "depriority_topics": [],
            "data_preference": "data_tables_charts",
            "framing_style": "Data-dense executive briefing with policy implications",
            "reading_grade_level": 14,
            "max_article_length_words": 800,
        }
    elif profile.reading_level == "beginner":
        return {
            "content_depth": "beginner",
            "format_preference": "explainer",
            "tone": "educational",
            "jargon_level": "low",
            "priority_topics": profile.interests,
            "depriority_topics": [],
            "data_preference": "minimal_numbers",
            "framing_style": "Simple explanations with everyday analogies",
            "reading_grade_level": 8,
            "max_article_length_words": 300,
        }
    else:
        return {
            "content_depth": "intermediate",
            "format_preference": "standard",
            "tone": "conversational",
            "jargon_level": "medium",
            "priority_topics": profile.interests,
            "depriority_topics": [],
            "data_preference": "inline_numbers",
            "framing_style": "Balanced coverage with context",
            "reading_grade_level": 11,
            "max_article_length_words": 500,
        }
