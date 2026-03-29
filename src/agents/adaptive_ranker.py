"""Adaptive ranking with feedback signals (Phase 5).

Phase 5: Adaptive Learning + Cold Start

This module wraps the existing ranker to boost/penalize articles based on user's
feedback from current session (Phase 4) and helps new users with cold-start strategy.

Key functions:
- apply_feedback_boost(): Modify article scores based on liked/disliked signals
- get_cold_start_boost_for_role(): Seed new users with role-based defaults
- merge_feedback_with_preference_scores(): Blend Phase 3 scores with Phase 4 feedback
"""

import json
import time
import math
from typing import Optional

from src.models import UserProfile, Article


def apply_feedback_boost(
    articles: list[Article],
    feedback_signals: dict,
    base_scores: dict[str, float],
) -> dict[str, float]:
    """
    Apply feedback-based score modifications to articles.
    
    Args:
        articles: List of Article objects to score
        feedback_signals: Dict from get_feedback_signal_for_ranker() with:
            - liked_count (int)
            - disliked_count (int)
            - disliked_reasons (dict[str, int])
            - session_feedback_weight (float, 0.0-0.2)
        base_scores: Dict[article_id] -> float, from Phase 3 ranker
    
    Returns:
        Dict[article_id] -> float with feedback-boosted scores
    
    Strategy:
        - Boost factor: +0.2 per liked article (up to +0.5 max boost)
        - Penalize factor: -0.2 per disliked article (down to -0.5 min)
        - Blending: new_score = base_score * (1 - session_weight) + feedback_bonus
    """
    liked_count = feedback_signals.get("liked_count", 0)
    disliked_count = feedback_signals.get("disliked_count", 0)
    session_weight = feedback_signals.get("session_feedback_weight", 0.0)
    disliked_reasons = feedback_signals.get("disliked_reasons", {})
    
    boosted_scores = base_scores.copy()
    
    # If no feedback yet, return base scores as-is
    if liked_count == 0 and disliked_count == 0:
        return boosted_scores
    
    # Build penalization rules from disliked_reasons
    # e.g., {"Already know this": 1, "Not credible source": 2}
    penalize_rules = {
        "Already know this": -0.25,  # High penalty — user knows content
        "Not credible source": -0.30,  # Credibility issues
        "Sensationalized": -0.25,  # Yellow journalism
        "Duplicate/repetitive": -0.20,  # Redundant (soft penalty)
        "Too technical/complex": -0.15,  # Personalization clue (softer)
        "Too basic/simple": -0.15,  # Inverse personalization clue
        "Not relevant to interests": -0.20,  # Interest mismatch
    }
    
    # Boost rules from liked articles
    boost_rules = {
        "Relevant to my portfolio": 0.25,  # Portfolio fit (strong)
        "Great explanation": 0.20,  # Writing quality
        "Market-moving news": 0.30,  # Importance (strongest)
        "Actionable insights": 0.25,  # Utility
        "Timely topic": 0.15,  # Freshness
    }
    
    # For each article, check if similar reasons exist
    for article in articles:
        article_id = article.id  # Use .id instead of .article_id
        
        if article_id not in boosted_scores:
            continue
        
        base_score = boosted_scores[article_id]
        feedback_delta = 0.0
        
        # Apply penalization based on disliked_reasons
        if disliked_reasons:
            for reason, count in disliked_reasons.items():
                penalty = penalize_rules.get(reason, -0.15)
                # Scale penalty by count (more dislikes = more penalty)
                feedback_delta += penalty * min(count / max(1, disliked_count), 1.0)
        
        # Cap feedback delta
        feedback_delta = max(-0.5, min(0.5, feedback_delta))
        
        # Blend: weighted combination of base score and feedback
        # session_weight typically 0.05-0.2 from Phase 4
        boosted_scores[article_id] = base_score * (1 - session_weight) + (base_score + feedback_delta) * session_weight
        
        # Ensure score stays in valid range [0, 1]
        boosted_scores[article_id] = max(0.0, min(1.0, boosted_scores[article_id]))
    
    return boosted_scores


def get_cold_start_boost_for_role(role: str) -> dict[str, float]:
    """
    Seed new users (no feedback history) with role-based default scores.
    
    Used when Phase 4 feedback signals are empty.
    
    Args:
        role: User role (CFO, Young Investor, etc.)
    
    Returns:
        Dict of topic -> base_boost_score for cold-start ranking
    """
    cold_start_rules = {
        "CFO": {
            "policy": 0.50,
            "macro": 0.45,
            "tech": 0.35,
            "international": 0.40,
            "markets": 0.50,
        },
        "Young Investor": {
            "tech": 0.55,
            "startups": 0.60,
            "micro": 0.45,
            "policy": 0.30,
            "markets": 0.50,
        },
        "Analyst": {
            "macro": 0.55,
            "policy": 0.50,
            "markets": 0.55,
            "tech": 0.40,
            "international": 0.45,
        },
        "Default": {  # Fallback for unknowns
            "markets": 0.50,
            "policy": 0.40,
            "tech": 0.40,
            "macro": 0.40,
        },
    }
    
    return cold_start_rules.get(role, cold_start_rules["Default"])


def merge_feedback_with_preference_scores(
    articles: list[Article],
    user_profile: UserProfile,
    ranker_scores: dict[str, float],
    feedback_signals: Optional[dict] = None,
    session_id: str = "default",
) -> dict[str, float]:
    """
    Merge Phase 3 ranker scores with Phase 4 feedback signals.
    
    This is the main function called from personalized_feed_pipeline.py
    
    Args:
        articles: List of Article objects
        user_profile: UserProfile with interests/role
        ranker_scores: Dict[article_id] -> float from Phase 3 ranker
        feedback_signals: Optional dict from get_feedback_signal_for_ranker()
                         If None, use cold-start boost
        session_id: For logging
    
    Returns:
        Dict[article_id] -> float with merged scores ready for ranking
    """
    # If no feedback history, use cold-start strategy
    if not feedback_signals or (feedback_signals.get("liked_count", 0) == 0 and 
                                feedback_signals.get("disliked_count", 0) == 0):
        # Log cold-start path
        from src.audit import log_agent_step
        
        log_agent_step(
            agent_name="AdaptiveRanker",
            action="apply_cold_start_boost",
            model_used="rule-based (no LLM)",
            input_summary=f"Role: {user_profile.role}, Articles: {len(articles)}",
            output_summary=f"Returned baseline scores unchanged (cold-start)",
            latency_ms=0,
            status="success",
            session_id=session_id,
        )
        
        # Return ranker scores as-is (Phase 3 already handled cold-start)
        return ranker_scores
    
    # Apply feedback boost
    boosted_scores = apply_feedback_boost(
        articles=articles,
        feedback_signals=feedback_signals,
        base_scores=ranker_scores,
    )
    
    # Log boost application
    from src.audit import log_agent_step
    
    log_agent_step(
        agent_name="AdaptiveRanker",
        action="apply_feedback_boost",
        model_used="rule-based (feedback signals)",
        input_summary=f"Liked: {feedback_signals.get('liked_count', 0)}, Disliked: {feedback_signals.get('disliked_count', 0)}, Articles: {len(articles)}",
        output_summary=f"Boosted {len(articles)} article scores with feedback weight {feedback_signals.get('session_feedback_weight', 0):.2f}",
        latency_ms=0,
        status="success",
        session_id=session_id,
    )
    
    return boosted_scores


def get_boost_explanation(
    article_id: str,
    original_score: float,
    boosted_score: float,
    feedback_signals: dict,
) -> str:
    """
    Generate explanation for why an article was boosted/penalized.
    
    Args:
        article_id: Article being rated
        original_score: Phase 3 ranker score
        boosted_score: After-feedback score
        feedback_signals: From Phase 4
    
    Returns:
        String explanation for article card UI
    """
    delta = boosted_score - original_score
    
    if delta > 0.05:
        return f"Boosted because you liked related articles (↑ {delta:.2f})"
    elif delta < -0.05:
        disliked_reasons = feedback_signals.get("disliked_reasons", {})
        if disliked_reasons:
            top_reason = max(disliked_reasons.items(), key=lambda x: x[1])[0]
            return f"Penalized: {top_reason} (↓ {abs(delta):.2f})"
        return f"Penalized by your feedback (↓ {abs(delta):.2f})"
    else:
        return "Ranked by your interests"


# ============================================================
# For Phase 5 Testing
# ============================================================

def save_adaptive_signals(
    user_id: str,
    signals: dict,
    session_id: str = "default",
) -> None:
    """Save adaptive signals for session analysis."""
    import os
    
    store_path = "output/adaptive_signals.json"
    os.makedirs(os.path.dirname(store_path), exist_ok=True)
    
    signals_store = {}
    if os.path.exists(store_path):
        with open(store_path, "r") as f:
            signals_store = json.load(f)
    
    key = f"{user_id}_{session_id}_{int(time.time())}"
    signals_store[key] = signals
    
    with open(store_path, "w") as f:
        json.dump(signals_store, f, indent=2)


def load_adaptive_signals(user_id: str) -> list[dict]:
    """Load all adaptive signals for a user."""
    import os
    
    store_path = "output/adaptive_signals.json"
    if not os.path.exists(store_path):
        return []
    
    with open(store_path, "r") as f:
        signals_store = json.load(f)
    
    return [v for k, v in signals_store.items() if k.startswith(user_id)]
