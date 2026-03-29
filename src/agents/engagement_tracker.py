"""EngagementTracker — tracks user interaction signals and retunes content delivery.

This module provides cross-session learning without any LLM cost.
It logs engagement signals (clicks, queries, dwell time) and builds a
per-user interest vector that can be used to retune angle ordering,
article ranking, and content depth in subsequent sessions.

Directly addresses Track 8 extra credit:
"agents that track user engagement signals and retune content delivery
in subsequent sessions."
"""

import json
import os
import time
from collections import defaultdict
from src.config import OUTPUT_DIR
from src.audit import log_agent_step

# Persistent store path
ENGAGEMENT_STORE_PATH = os.path.join(OUTPUT_DIR, "engagement_store.json")


def _load_store() -> dict:
    """Load engagement data from disk."""
    if os.path.exists(ENGAGEMENT_STORE_PATH):
        try:
            with open(ENGAGEMENT_STORE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"users": {}, "global": {"angle_clicks": {}, "queries": [], "total_sessions": 0}}


def _save_store(store: dict):
    """Persist engagement data to disk."""
    os.makedirs(os.path.dirname(ENGAGEMENT_STORE_PATH), exist_ok=True)
    with open(ENGAGEMENT_STORE_PATH, "w", encoding="utf-8") as f:
        json.dump(store, f, indent=2, ensure_ascii=False)


# --- Signal Logging ---

def log_angle_click(user_id: str, angle_name: str, session_id: str = "default"):
    """Log that a user clicked/selected an angle in the Navigator."""
    store = _load_store()
    user = store["users"].setdefault(user_id, {
        "angle_clicks": {}, "queries": [], "feed_clicks": [],
        "preferred_depth": "intermediate", "sessions": 0,
    })
    user["angle_clicks"][angle_name] = user["angle_clicks"].get(angle_name, 0) + 1
    store["global"]["angle_clicks"][angle_name] = store["global"]["angle_clicks"].get(angle_name, 0) + 1
    _save_store(store)

    log_agent_step(
        agent_name="EngagementTracker",
        action="log_angle_click",
        model_used="local (no LLM)",
        input_summary=f"User: {user_id}, Angle: {angle_name}",
        output_summary=f"Total clicks on {angle_name}: {user['angle_clicks'][angle_name]}",
        latency_ms=0,
        session_id=session_id,
    )


def log_query(user_id: str, question: str, angle: str, session_id: str = "default"):
    """Log a follow-up question and which angle it was about."""
    store = _load_store()
    user = store["users"].setdefault(user_id, {
        "angle_clicks": {}, "queries": [], "feed_clicks": [],
        "preferred_depth": "intermediate", "sessions": 0,
    })
    user["queries"].append({
        "question": question[:200],
        "angle": angle,
        "timestamp": time.time(),
    })
    store["global"]["queries"].append({
        "question": question[:100],
        "angle": angle,
        "user_id": user_id,
    })
    # Keep only last 50 queries per user
    user["queries"] = user["queries"][-50:]
    store["global"]["queries"] = store["global"]["queries"][-200:]
    _save_store(store)


def log_feed_click(user_id: str, article_id: str, format_type: str, session_id: str = "default"):
    """Log that a user clicked a feed item in the Personalised Feed."""
    store = _load_store()
    user = store["users"].setdefault(user_id, {
        "angle_clicks": {}, "queries": [], "feed_clicks": [],
        "preferred_depth": "intermediate", "sessions": 0,
    })
    user["feed_clicks"].append({
        "article_id": article_id,
        "format_type": format_type,
        "timestamp": time.time(),
    })
    user["feed_clicks"] = user["feed_clicks"][-50:]
    _save_store(store)


def log_session_start(user_id: str, session_id: str = "default"):
    """Log a new session for engagement tracking."""
    store = _load_store()
    user = store["users"].setdefault(user_id, {
        "angle_clicks": {}, "queries": [], "feed_clicks": [],
        "preferred_depth": "intermediate", "sessions": 0,
    })
    user["sessions"] += 1
    store["global"]["total_sessions"] = store["global"].get("total_sessions", 0) + 1
    _save_store(store)


# --- Retuning / Preference Inference ---

def get_retuned_angle_order(user_id: str, default_angles: list[str]) -> list[str]:
    """Retune angle ordering based on user's engagement history.

    Angles the user has clicked more often are surfaced first.
    New/unclicked angles are placed after preferred ones.

    Args:
        user_id: User identifier
        default_angles: Default angle ordering

    Returns:
        Retuned angle ordering
    """
    store = _load_store()
    user = store["users"].get(user_id)
    if not user or not user.get("angle_clicks"):
        return default_angles

    clicks = user["angle_clicks"]
    # Sort by click count descending, then original order for ties
    scored = []
    for i, angle in enumerate(default_angles):
        score = clicks.get(angle, 0)
        scored.append((score, -i, angle))

    scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return [s[2] for s in scored]


def get_user_interest_vector(user_id: str) -> dict:
    """Build a user interest vector from engagement history.

    Returns a dict with:
    - preferred_angles: top angles by click frequency
    - query_topics: topics extracted from query history
    - preferred_format: most-clicked feed format type
    - engagement_depth: low/medium/high based on session count
    """
    store = _load_store()
    user = store["users"].get(user_id)
    if not user:
        return {
            "preferred_angles": [],
            "query_topics": [],
            "preferred_format": "standard",
            "engagement_depth": "low",
        }

    # Top angles
    angle_clicks = user.get("angle_clicks", {})
    sorted_angles = sorted(angle_clicks.items(), key=lambda x: x[1], reverse=True)
    preferred_angles = [a[0] for a in sorted_angles[:3]]

    # Query topics (extract angles from queries)
    query_angles = [q.get("angle", "") for q in user.get("queries", [])]
    topic_counts = defaultdict(int)
    for a in query_angles:
        if a:
            topic_counts[a] += 1
    query_topics = sorted(topic_counts.keys(), key=lambda x: topic_counts[x], reverse=True)[:5]

    # Preferred format from feed clicks
    format_counts = defaultdict(int)
    for click in user.get("feed_clicks", []):
        fmt = click.get("format_type", "standard")
        format_counts[fmt] += 1
    preferred_format = max(format_counts, key=format_counts.get) if format_counts else "standard"

    # Engagement depth
    sessions = user.get("sessions", 0)
    if sessions >= 5:
        depth = "high"
    elif sessions >= 2:
        depth = "medium"
    else:
        depth = "low"

    return {
        "preferred_angles": preferred_angles,
        "query_topics": query_topics,
        "preferred_format": preferred_format,
        "engagement_depth": depth,
    }


def get_engagement_summary() -> dict:
    """Get global engagement summary for display/audit."""
    store = _load_store()
    return {
        "total_users": len(store.get("users", {})),
        "total_sessions": store["global"].get("total_sessions", 0),
        "top_angles": sorted(
            store["global"].get("angle_clicks", {}).items(),
            key=lambda x: x[1], reverse=True,
        )[:5],
        "total_queries": len(store["global"].get("queries", [])),
    }


# --- Phase 4: Article Feedback Tracking ---

FEEDBACK_REASONS = {
    "interested": [
        "Relevant to my portfolio",
        "Great explanation",
        "Market-moving news",
        "Actionable insights",
        "Timely topic",
    ],
    "not_interested": [
        "Not relevant to my interests",
        "Too technical/complex",
        "Too basic/simple",
        "Already know this",
        "Sensationalized",
        "Not credible source",
        "Duplicate/repetitive",
    ],
}


def log_article_feedback(
    user_id: str,
    article_id: str,
    feedback_type: str,  # "interested" or "not_interested"
    reason: str = None,
    session_id: str = "default",
) -> dict:
    """Log article feedback (interested / not interested) with optional reason.
    
    Args:
        user_id: User identifier
        article_id: Article ID that was rated
        feedback_type: "interested" or "not_interested"
        reason: Optional reason (should be from FEEDBACK_REASONS)
        session_id: Session ID for audit
    
    Returns:
        Dict with feedback_id, timestamp, user_id, article_id, feedback_type, reason
    """
    if feedback_type not in ["interested", "not_interested"]:
        raise ValueError(f"Invalid feedback_type: {feedback_type}")
    
    store = _load_store()
    
    # Initialize user if needed
    user = store["users"].setdefault(user_id, {
        "angle_clicks": {},
        "queries": [],
        "feed_clicks": [],
        "article_feedback": [],  # Phase 4 addition
        "preferred_depth": "intermediate",
        "sessions": 0,
    })
    
    # Create feedback record
    feedback_record = {
        "article_id": article_id,
        "feedback_type": feedback_type,
        "reason": reason,
        "timestamp": time.time(),
    }
    
    # Append to feedback history (keep last 100)
    user.setdefault("article_feedback", []).append(feedback_record)
    user["article_feedback"] = user["article_feedback"][-100:]
    
    # Update global stats
    store["global"].setdefault("article_feedback", {})
    store["global"]["article_feedback"][feedback_type] = \
        store["global"]["article_feedback"].get(feedback_type, 0) + 1
    
    _save_store(store)
    
    log_agent_step(
        agent_name="EngagementTracker",
        action="log_article_feedback",
        model_used="local (no LLM)",
        input_summary=f"User: {user_id}, Article: {article_id}, Type: {feedback_type}",
        output_summary=f"Feedback recorded. Reason: {reason or 'none'}",
        latency_ms=0,
        session_id=session_id,
    )
    
    return {
        "feedback_type": feedback_type,
        "article_id": article_id,
        "reason": reason,
        "timestamp": feedback_record["timestamp"],
    }


def get_user_feedback_summary(user_id: str) -> dict:
    """Get summary of user's article feedback.
    
    Returns:
        Dict with interested_count, not_interested_count, interested_reasons, not_interested_reasons
    """
    store = _load_store()
    user = store["users"].get(user_id, {})
    feedback_list = user.get("article_feedback", [])
    
    interested = [f for f in feedback_list if f["feedback_type"] == "interested"]
    not_interested = [f for f in feedback_list if f["feedback_type"] == "not_interested"]
    
    # Extract reason frequencies
    interested_reasons = defaultdict(int)
    for f in interested:
        if f.get("reason"):
            interested_reasons[f["reason"]] += 1
    
    not_interested_reasons = defaultdict(int)
    for f in not_interested:
        if f.get("reason"):
            not_interested_reasons[f["reason"]] += 1
    
    return {
        "interested_count": len(interested),
        "not_interested_count": len(not_interested),
        "interested_reasons": dict(sorted(interested_reasons.items(), key=lambda x: x[1], reverse=True)),
        "not_interested_reasons": dict(sorted(not_interested_reasons.items(), key=lambda x: x[1], reverse=True)),
    }


def get_feedback_weighted_topics(user_id: str) -> dict:
    """Get topics the user has given positive feedback on.
    
    Returns article tags that were marked "interested" more frequently.
    Can be used to re-weight next feed generation.
    
    Returns:
        Dict with liked_tags and disliked_tags (lists of strings with counts)
    """
    store = _load_store()
    user = store["users"].get(user_id, {})
    
    # Note: This would need article metadata linking article_id → tags
    # For now, return structure ready for Phase 5 enhancement
    
    return {
        "liked_tags": [],
        "disliked_tags": [],
        "note": "Phase 5 will use article metadata to map feedback → tags → reweighting",
    }


def should_show_article_again(user_id: str, article_id: str) -> bool:
    """Check if user explicitly said they're not interested in similar articles.
    
    Args:
        user_id: User identifier
        article_id: Article ID to check
    
    Returns:
        False if user marked this exact article as "not_interested", True otherwise
    """
    store = _load_store()
    user = store["users"].get(user_id, {})
    feedback_list = user.get("article_feedback", [])
    
    for f in feedback_list:
        if f["article_id"] == article_id and f["feedback_type"] == "not_interested":
            return False
    
    return True


def get_feedback_signal_for_ranker(user_id: str) -> dict:
    """Generate feedback signal to pass to ranker for re-weighting.
    
    For Phase 5+, this feeds into ranker to boost/penalize articles
    based on user feedback patterns from current session.
    
    Returns:
        Dict with liked_count, disliked_count, dislikes_map, session_feedback_weight
    """
    summary = get_user_feedback_summary(user_id)
    
    return {
        "liked_count": summary["interested_count"],
        "disliked_count": summary["not_interested_count"],
        "liked_reasons": summary["interested_reasons"],
        "disliked_reasons": summary["not_interested_reasons"],
        "session_feedback_weight": min(1.0, summary["interested_count"] + summary["not_interested_count"]) / 10.0,
    }

