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
