"""Phase 3-5: Single-User Personalized Feed Pipeline with Adaptive Ranking.

Pipeline flow:
    1. Phase 2: Get personalized corpus subset
    2. Phase 1: Analyze profile
    3. Phase 3: Rank articles (baseline)
    4. Phase 5: Apply adaptive boost from Phase 4 feedback
    5. Phase 3: Adapt articles and explain
"""

import asyncio
from src.models import Article, UserProfile, PersonaFeed, FeedItem
from src.agents.persona_feed.profiler import analyze_profile
from src.agents.persona_feed.ranker import rank_articles
from src.agents.persona_feed.adapter import adapt_articles
from src.agents.profile_subset_builder import get_articles_for_user
from src.agents.adaptive_ranker import merge_feedback_with_preference_scores, get_boost_explanation
from src.agents.engagement_tracker import get_feedback_signal_for_ranker
from src.audit import log_agent_step, AuditTimer, clear_audit_trail


async def generate_personalized_user_feed(
    user_id: str,
    profile: UserProfile,
    all_articles: list[Article],
    session_id: str = "user_feed",
    use_personalized_subset: bool = True,
    top_n: int = 5,
) -> dict:
    """Generate a fully personalized feed for a single user.
    
    Pipeline:
    1. Phase 2: Get personalized corpus subset (filtered by user interests)
    2. Phase 1: Analyze profile → preferences
    3. Phase 2: Rank articles by relevance
    4. Phase 3: Adapt top articles to user's depth/format
    5. Explain: Why each article, confidence, matched tags
    
    Args:
        user_id: User identifier
        profile: UserProfile object
        all_articles: All available articles
        session_id: Session ID for audit
        use_personalized_subset: Whether to use Phase 2 personalization (True) or generic ranking
        top_n: Number of articles to adapt and return
    
    Returns:
        Dict with feed, explanations, audit trail
    """
    clear_audit_trail(session_id)
    
    with AuditTimer() as total_timer:
        # Step 1: Get personalized subset (Phase 2)
        if use_personalized_subset:
            from src.agents.profile_subset_builder import get_articles_for_user as phase2_get_articles
            
            articles_list = phase2_get_articles(
                user_id=user_id,
                all_articles=[a.model_dump() for a in all_articles],
                profile=profile,
                use_cache=True,
                max_items=30,
            )
            
            # Convert back to Article objects
            articles_for_feed = [Article(**a) for a in articles_list]
            
            log_agent_step(
                agent_name="CorpusPersonalizer",
                action="get_personalized_subset",
                model_used="rule-based (no LLM)",
                input_summary=f"User: {profile.name}, Total articles: {len(all_articles)}",
                output_summary=f"Personalized subset: {len(articles_for_feed)} articles",
                latency_ms=0,
                session_id=session_id,
            )
        else:
            articles_for_feed = all_articles
        
        # Step 2: Analyze profile (Phase 1)
        preferences = await analyze_profile(profile, session_id)
        
        # Step 3: Rank articles (Phase 3 baseline)
        rankings = await rank_articles(
            articles_for_feed,
            preferences,
            profile.name,
            session_id,
        )
        
        # ========== PHASE 5: ADAPTIVE RANKING ==========
        # Step 3.5: Apply adaptive boost from Phase 4 feedback
        base_scores = {r["article_id"]: r.get("relevance_score", 0.5) for r in rankings}
        
        # Get feedback signals from Phase 4
        feedback_signals = get_feedback_signal_for_ranker(user_id)
        
        # Apply adaptive boost (Phase 5)
        boosted_scores = merge_feedback_with_preference_scores(
            articles=articles_for_feed,
            user_profile=profile,
            ranker_scores=base_scores,
            feedback_signals=feedback_signals,
            session_id=session_id,
        )
        
        # Update rankings with boosted scores
        for ranking in rankings:
            article_id = ranking["article_id"]
            original_score = ranking.get("relevance_score", 0.5)
            boosted_score = boosted_scores.get(article_id, original_score)
            
            # Add boost info to ranking for explanation
            ranking["original_score"] = original_score
            ranking["boosted_score"] = boosted_score
            ranking["relevance_score"] = boosted_score  # Use boosted score for final ranking
            ranking["boost_explanation"] = get_boost_explanation(
                article_id,
                original_score,
                boosted_score,
                feedback_signals or {},
            )
        
        # Re-sort rankings by boosted score
        rankings.sort(key=lambda x: x["boosted_score"], reverse=True)
        
        # Step 4: Adapt top articles (existing adapter)
        feed_items = await adapt_articles(
            articles_for_feed,
            rankings,
            preferences,
            user_name=profile.name,
            top_n=top_n,
            session_id=session_id,
        )
        
        # Step 5: Build explanations for each item
        ranked_map = {r["article_id"]: r for r in rankings}
        feed_with_explanations = []
        
        for item in feed_items:
            ranking = ranked_map.get(item.article_id, {})
            
            # Extract matched tags from the personalized subset
            matched_tags = []
            if use_personalized_subset:
                # Find original article to check its tags
                for a in articles_list:
                    if a.get("id") == item.article_id:
                        tags = a.get("tags", [])
                        # Extract relevance and intent tags
                        matched_tags = [t for t in tags if ":" in t]
                        break
            
            # Build explanation with Phase 5 boost info
            boost_explanation = ranking.get("boost_explanation", "Ranked by your interests")
            
            explanation = {
                "why_shown": boost_explanation,  # Phase 5: Updated with feedback source
                "relevance_score": ranking.get("relevance_score", 0.5),
                "confidence": "high" if ranking.get("relevance_score", 0) > 0.7 else "medium" if ranking.get("relevance_score", 0) > 0.4 else "low",
                "matched_tags": matched_tags,
                "reading_depth": preferences.get("content_depth", "intermediate"),
                "format_applied": item.format_type,
                "boosted": ranking.get("original_score", 0) != ranking.get("boosted_score", 0),  # Phase 5 flag
            }
            
            feed_with_explanations.append({
                "item": item,
                "explanation": explanation,
            })
    
    # Build PersonaFeed response
    persona_feed = PersonaFeed(
        user_profile=profile,
        feed_items=[x["item"] for x in feed_with_explanations],
        reading_level_applied=preferences.get("content_depth", "intermediate"),
        format_applied=preferences.get("format_preference", "standard"),
    )
    
    # Get audit trail
    from src.audit import get_audit_trail
    audit_trail = get_audit_trail(session_id)
    
    return {
        "feed": persona_feed,
        "explanations": [x["explanation"] for x in feed_with_explanations],
        "audit_trail": audit_trail,
        "total_pipeline_time_ms": total_timer.elapsed_ms,
        "personalization_method": "phase2_corpus_aware" if use_personalized_subset else "generic_ranking",
    }


async def compare_personalized_vs_baseline(
    user_id: str,
    profile: UserProfile,
    all_articles: list[Article],
    session_id: str = "feed_comparison",
) -> dict:
    """A/B test comparison: personalized feed vs. baseline (non-personalized).
    
    Returns both feeds so client can measure engagement difference.
    
    Args:
        user_id: User identifier
        profile: UserProfile
        all_articles: All available articles
        session_id: Session ID
    
    Returns:
        Dict with personalized_feed, baseline_feed, delta_metrics
    """
    # Get personalized feed (Phase 2 aware)
    personalized = await generate_personalized_user_feed(
        user_id=user_id,
        profile=profile,
        all_articles=all_articles,
        session_id=f"{session_id}_personalized",
        use_personalized_subset=True,
        top_n=5,
    )
    
    # Get baseline feed (no Phase 2 personalization)
    baseline = await generate_personalized_user_feed(
        user_id=user_id,
        profile=profile,
        all_articles=all_articles,
        session_id=f"{session_id}_baseline",
        use_personalized_subset=False,
        top_n=5,
    )
    
    # Calculate delta
    personalized_ids = {item.article_id for item in personalized["feed"].feed_items}
    baseline_ids = {item.article_id for item in baseline["feed"].feed_items}
    
    shared = personalized_ids & baseline_ids
    unique_to_personalized = personalized_ids - baseline_ids
    unique_to_baseline = baseline_ids - personalized_ids
    
    delta_metrics = {
        "total_articles_shown": len(personalized["feed"].feed_items),
        "articles_in_common": len(shared),
        "unique_to_personalized": len(unique_to_personalized),
        "unique_to_baseline": len(unique_to_baseline),
        "personalization_delta": f"{len(unique_to_personalized)} of {len(personalized_ids)} articles differ from baseline",
        "personalized_avg_relevance": sum(
            r["relevance_score"] for r in personalized["explanations"]
        ) / len(personalized["explanations"]) if personalized["explanations"] else 0,
        "baseline_avg_relevance": sum(
            r["relevance_score"] for r in baseline["explanations"]
        ) / len(baseline["explanations"]) if baseline["explanations"] else 0,
    }
    
    log_agent_step(
        agent_name="FeedComparison",
        action="personalized_vs_baseline",
        model_used="multi-model",
        input_summary=f"User: {profile.name}",
        output_summary=f"Delta: {delta_metrics['personalization_delta']}",
        latency_ms=int(personalized["total_pipeline_time_ms"] + baseline["total_pipeline_time_ms"]),
        session_id=session_id,
    )
    
    from src.audit import get_audit_trail
    combined_audit = get_audit_trail(f"{session_id}_personalized") + get_audit_trail(f"{session_id}_baseline")
    
    return {
        "personalized_feed": personalized["feed"],
        "baseline_feed": baseline["feed"],
        "personalized_explanations": personalized["explanations"],
        "baseline_explanations": baseline["explanations"],
        "delta_metrics": delta_metrics,
        "audit_trail": combined_audit,
    }
