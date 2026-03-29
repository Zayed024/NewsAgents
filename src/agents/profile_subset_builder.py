"""Phase 2: Profile-Aware Subset Builder — materializes per-user corpus subsets."""

import json
import os
from datetime import datetime
from src.config import DATA_DIR
from src.models import UserProfile, Article
from src.agents.corpus_personalizer import (
    profile_to_crawl_queries,
    profile_to_subset_tags,
    filter_articles_for_profile,
    tag_articles_with_profile_data,
    get_profile_segment_cache_key,
)


def _profile_subset_dir() -> str:
    """Directory for per-user corpus subsets."""
    path = os.path.join(DATA_DIR, "corpus", "subsets", "profile_specific")
    os.makedirs(path, exist_ok=True)
    return path


def _get_profile_subset_path(user_id: str) -> str:
    """Get the file path for a user's personalized subset."""
    return os.path.join(_profile_subset_dir(), f"{user_id}_subset.json")


def _get_segment_subset_path(segment: str) -> str:
    """Get the file path for a segment-level cached subset."""
    return os.path.join(_profile_subset_dir(), f"segment_{segment}_cached.json")


def build_profile_specific_subset(
    articles: list[dict],
    profile: UserProfile,
    max_items: int = 30,
) -> dict:
    """Build a corpus subset tailored to a specific user profile.
    
    Args:
        articles: Available articles (list of dicts)
        profile: UserProfile object
        max_items: Maximum articles to include
    
    Returns:
        Subset dict with selected_ids, tags, metadata
    """
    # Get crawl intents to guide filtering
    crawl_intents = profile_to_crawl_queries(profile)
    subset_tags = profile_to_subset_tags(profile)
    
    # Filter articles by profile interests
    filtered = filter_articles_for_profile(articles, profile)
    
    # Tag articles with profile-specific metadata
    tagged = [tag_articles_with_profile_data(a, profile) for a in filtered]
    
    # Sort by relevance (articles with "high" tag first)
    def relevance_score(article):
        tags = article.get("tags", [])
        if "relevance:high" in tags:
            return 3
        elif "relevance:medium" in tags:
            return 2
        else:
            return 1
    
    tagged.sort(key=relevance_score, reverse=True)
    
    # Select top N
    selected = tagged[:max_items]
    selected_ids = [a.get("id") for a in selected]
    
    subset = {
        "user_id": profile.user_id,
        "user_name": profile.name,
        "subset_generated_at": datetime.now().isoformat(),
        "crawl_intents": crawl_intents,
        "subset_tags": subset_tags,
        "selected_count": len(selected_ids),
        "selected_ids": selected_ids,
        "total_available": len(articles),
        "filter_criteria": {
            "keywords": crawl_intents.get("keywords", []),
            "sectors": crawl_intents.get("sectors", []),
            "intent_types": crawl_intents.get("intent_types", []),
        },
        "articles": selected,
    }
    
    return subset


def save_profile_subset(profile: UserProfile, subset: dict) -> bool:
    """Save a profile-specific subset to disk.
    
    Args:
        profile: UserProfile
        subset: Subset dict from build_profile_specific_subset
    
    Returns:
        True if successful
    """
    try:
        path = _get_profile_subset_path(profile.user_id)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(subset, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Error saving profile subset: {e}")
        return False


def load_profile_subset(user_id: str) -> dict | None:
    """Load a previously saved user subset.
    
    Args:
        user_id: User identifier
    
    Returns:
        Subset dict if found, None otherwise
    """
    try:
        path = _get_profile_subset_path(user_id)
        if not os.path.exists(path):
            return None
        
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def save_segment_subset(segment: str, subset: dict) -> bool:
    """Cache a segment-level subset for reuse by similar profiles.
    
    Args:
        segment: Segment identifier (e.g., "student_beginner")
        subset: Subset dict
    
    Returns:
        True if successful
    """
    try:
        path = _get_segment_subset_path(segment)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(subset, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Error saving segment subset: {e}")
        return False


def load_segment_subset(segment: str) -> dict | None:
    """Load a cached segment subset.
    
    Args:
        segment: Segment identifier
    
    Returns:
        Subset dict if found and fresh, None otherwise
    """
    try:
        path = _get_segment_subset_path(segment)
        if not os.path.exists(path):
            return None
        
        with open(path, "r", encoding="utf-8") as f:
            subset = json.load(f)
        
        # Check freshness (2 hours)
        generated_at = datetime.fromisoformat(subset.get("subset_generated_at", ""))
        age_minutes = (datetime.now() - generated_at).total_seconds() / 60
        
        if age_minutes < 120:
            return subset
        
    except Exception:
        pass
    
    return None


def get_articles_for_user(
    user_id: str,
    all_articles: list[dict],
    profile: UserProfile,
    use_cache: bool = True,
    max_items: int = 30,
) -> list[dict]:
    """Get personalized articles for a user.
    
    Strategy:
    1. Try to load cached user subset
    2. If not found, try segment cache
    3. If segment cache hit, use it
    4. Otherwise, build fresh subset
    
    Args:
        user_id: User identifier
        all_articles: Available articles
        profile: UserProfile
        use_cache: Whether to try cached segments
        max_items: Maximum articles to return
    
    Returns:
        List of article dicts
    """
    # Try user-specific subset first
    user_subset = load_profile_subset(user_id)
    if user_subset:
        return user_subset.get("articles", [])[:max_items]
    
    # Try segment cache
    from src.agents.corpus_personalizer import get_profile_segment_cache_key
    segment_key = get_profile_segment_cache_key(profile)
    
    if use_cache:
        from src.agents.corpus_personalizer import _get_profile_segment
        segment = _get_profile_segment(profile)
        segment_subset = load_segment_subset(segment)
        if segment_subset:
            return segment_subset.get("articles", [])[:max_items]
    
    # Build fresh subset
    subset = build_profile_specific_subset(all_articles, profile, max_items=max_items)
    save_profile_subset(profile, subset)
    
    # Also save segment cache for similar profiles
    from src.agents.corpus_personalizer import _get_profile_segment
    segment = _get_profile_segment(profile)
    save_segment_subset(segment, subset)
    
    return subset.get("articles", [])
