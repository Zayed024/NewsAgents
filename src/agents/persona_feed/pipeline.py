"""Personalised Feed pipeline — generates persona-differentiated news feeds."""

from src.models import (
    Article, UserProfile, PersonaFeed, FeedItem, FeedComparison,
    FeedCompareResponse, AuditEntry,
)
from src.audit import get_audit_trail, clear_audit_trail, log_agent_step, AuditTimer
from src.agents.persona_feed.profiler import analyze_profile
from src.agents.persona_feed.ranker import rank_articles
from src.agents.persona_feed.adapter import adapt_articles


async def generate_persona_feed(
    articles: list[Article],
    profile: UserProfile,
    session_id: str = "default",
) -> PersonaFeed:
    """Generate a personalised feed for a single user profile.

    Steps:
    1. UserProfiler — analyze content preferences (Flash)
    2. ContentRanker — rank articles by relevance (Flash)
    3. ContentAdapter — rewrite top articles (Pro)

    Args:
        articles: Available articles
        profile: User profile
        session_id: Session ID for audit

    Returns:
        PersonaFeed with adapted articles
    """
    # Step 1: Analyze profile
    preferences = await analyze_profile(profile, session_id)

    # Step 2: Rank articles
    rankings = await rank_articles(
        articles, preferences, profile.name, session_id
    )

    # Step 3: Adapt top articles
    feed_items = await adapt_articles(
        articles, rankings, preferences, profile.name, top_n=5, session_id=session_id
    )

    return PersonaFeed(
        user_profile=profile,
        feed_items=feed_items,
        reading_level_applied=preferences.get("content_depth", "intermediate"),
        format_applied=preferences.get("format_preference", "standard"),
    )


async def run_feed_comparison(
    articles: list[Article],
    profile_a: UserProfile,
    profile_b: UserProfile,
    session_id: str = "feed-compare",
) -> FeedCompareResponse:
    """Generate side-by-side comparison of two persona feeds.

    Args:
        articles: Available articles
        profile_a: First user profile (e.g. CFO)
        profile_b: Second user profile (e.g. young investor)
        session_id: Session ID for audit

    Returns:
        FeedCompareResponse with both feeds and delta summary
    """
    clear_audit_trail(session_id)

    with AuditTimer() as total_timer:
        # Generate both feeds (could be parallelized but keeping simple for hackathon)
        feed_a = await generate_persona_feed(
            articles, profile_a, session_id=f"{session_id}-a"
        )
        feed_b = await generate_persona_feed(
            articles, profile_b, session_id=f"{session_id}-b"
        )

        # Calculate delta
        delta = _calculate_delta(feed_a, feed_b)

    log_agent_step(
        agent_name="FeedComparisonPipeline",
        action="compare_feeds",
        model_used="multi-model",
        input_summary=f"{profile_a.name} vs {profile_b.name}, {len(articles)} articles",
        output_summary=delta[:150],
        latency_ms=total_timer.elapsed_ms,
        session_id=session_id,
    )

    # Merge audit trails from both sub-sessions
    from src.audit import get_audit_trail as _get
    combined_trail = _get(f"{session_id}-a") + _get(f"{session_id}-b") + _get(session_id)

    return FeedCompareResponse(
        feed_a=feed_a,
        feed_b=feed_b,
        delta_summary=delta,
        audit_trail=combined_trail,
    )


def _calculate_delta(feed_a: PersonaFeed, feed_b: PersonaFeed) -> str:
    """Calculate the difference between two feeds."""
    ids_a = {item.article_id for item in feed_a.feed_items}
    ids_b = {item.article_id for item in feed_b.feed_items}

    shared = ids_a & ids_b
    unique_a = ids_a - ids_b
    unique_b = ids_b - ids_a
    total = len(ids_a | ids_b)
    different = len(unique_a) + len(unique_b)

    # Format differences
    format_a = set(item.format_type for item in feed_a.feed_items)
    format_b = set(item.format_type for item in feed_b.feed_items)

    delta_parts = [
        f"{different} of {total} stories differ between the two feeds.",
        f"User A ({feed_a.user_profile.name}): {feed_a.reading_level_applied} depth, {feed_a.format_applied} format.",
        f"User B ({feed_b.user_profile.name}): {feed_b.reading_level_applied} depth, {feed_b.format_applied} format.",
    ]

    if shared:
        delta_parts.append(
            f"{len(shared)} shared articles are rewritten with different depth, tone, and framing."
        )

    if format_a != format_b:
        delta_parts.append(
            f"Content formats differ: {', '.join(format_a)} vs {', '.join(format_b)}."
        )

    return " ".join(delta_parts)
