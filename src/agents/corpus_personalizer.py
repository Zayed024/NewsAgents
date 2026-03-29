"""Phase 2: Corpus Personalizer — converts user profiles to crawl intents and subset tags."""

from src.models import UserProfile
from typing import Dict, List


# Mapping of user interests/roles to ET keywords and crawl intents
INTEREST_TO_KEYWORDS = {
    "Personal savings & tax optimization": [
        "section 80c",
        "elss",
        "tax saving",
        "deduction",
        "income tax",
        "tax planning",
    ],
    "Stock market & equity investing": [
        "stock market",
        "bse",
        "nse",
        "share price",
        "stock tips",
        "equity",
        "bullion",
    ],
    "Mutual funds & passive investing": [
        "mutual fund",
        "amc",
        "nav",
        "nft",
        "index fund",
        "etf",
        "sip",
    ],
    "Cryptocurrency & crypto assets": [
        "bitcoin",
        "ethereum",
        "crypto",
        "blockchain",
        "nft",
        "defi",
    ],
    "Real estate & property": [
        "real estate",
        "property",
        "home loan",
        "mortgage",
        "reit",
        "land",
    ],
    "Startup funding & venture": [
        "startup",
        "vc",
        "funding",
        "unicorn",
        "venture capital",
        "series a",
        "ipo",
    ],
    "Macro policy & economy": [
        "gdp",
        "inflation",
        "rbi",
        "monetary policy",
        "fiscal policy",
        "budget",
        "macro",
    ],
    "Commodity & forex markets": [
        "commodity",
        "gold",
        "crude oil",
        "forex",
        "rupee",
        "interest rate",
    ],
}

ROLE_TO_INTENT = {
    "Student / Just Starting": {
        "intent_types": ["explainer", "educational", "basics"],
        "audience_level": "beginner",
        "depth_preference": "explainer",
    },
    "Salaried Professional": {
        "intent_types": ["market_move", "portfolio_action", "news"],
        "audience_level": "intermediate",
        "depth_preference": "standard",
    },
    "Business Owner / Entrepreneur": {
        "intent_types": ["market_move", "competitor", "funding", "startup"],
        "audience_level": "expert",
        "depth_preference": "detailed",
    },
    "Financial Professional / Trader": {
        "intent_types": ["market_data", "analysis", "technical"],
        "audience_level": "expert",
        "depth_preference": "data_dense",
    },
    "Retiree / Wealth Manager": {
        "intent_types": ["portfolio_action", "income", "safety"],
        "audience_level": "expert",
        "depth_preference": "conservative",
    },
}

EXPERIENCE_TO_SECTOR_DEPTH = {
    "Just starting": {
        "sectors": ["technology", "banking", "fmcg"],  # broad, safe sectors
        "focus": "fundamentals",
    },
    "Less than 1 year": {
        "sectors": ["technology", "banking", "healthcare"],
        "focus": "basics_and_trends",
    },
    "1-3 years": {
        "sectors": ["technology", "banking", "healthcare", "infrastructure"],
        "focus": "trends_and_analysis",
    },
    "3-10 years": {
        "sectors": [
            "technology",
            "banking",
            "healthcare",
            "infrastructure",
            "manufacturing",
        ],
        "focus": "deep_analysis",
    },
    "10+ years": {
        "sectors": None,  # All sectors
        "focus": "comprehensive",
    },
}

RISK_TO_CONTENT_FILTER = {
    "Conservative": {
        "exclude_keywords": ["speculative", "risky", "volatile"],
        "prefer_keywords": ["safe", "stable", "predictable"],
        "content_type": "defensive",
    },
    "Moderate": {
        "exclude_keywords": ["extreme", "highly speculative"],
        "prefer_keywords": ["balanced", "growth"],
        "content_type": "balanced",
    },
    "Aggressive": {
        "exclude_keywords": [],  # No exclusions
        "prefer_keywords": ["growth", "opportunity", "upside"],
        "content_type": "aggressive",
    },
}


def profile_to_crawl_queries(profile: UserProfile) -> Dict[str, List[str]]:
    """Convert a user profile to crawl query intents.
    
    Args:
        profile: UserProfile object
    
    Returns:
        Dict with keys: keywords, entities, sectors, intent_types
    """
    keywords = set()
    entities = set()
    sectors = set()
    intent_types = set()
    
    # Extract keywords from interests
    for interest in profile.interests:
        if interest in INTEREST_TO_KEYWORDS:
            keywords.update(INTEREST_TO_KEYWORDS[interest])
    
    # Extract intent types from role
    role = profile.role
    if role in ROLE_TO_INTENT:
        role_config = ROLE_TO_INTENT[role]
        intent_types.update(role_config["intent_types"])
    
    # Extract sectors from experience level
    exp = profile.investing_experience
    if exp in EXPERIENCE_TO_SECTOR_DEPTH:
        exp_config = EXPERIENCE_TO_SECTOR_DEPTH[exp]
        if exp_config["sectors"]:
            sectors.update(exp_config["sectors"])
    
    # Extract from portfolio exposure
    portfolio_keywords = {
        "Cash / Savings account": ["savings", "fd", "fixed deposit"],
        "Index funds & ETFs": ["index", "etf", "benchmark"],
        "Active mutual funds": ["mutual fund", "amc", "schemes"],
        "Individual stocks": ["stock", "share", "equity"],
        "Bonds & fixed income": ["bond", "debenture", "g-sec"],
        "Real estate / Property": ["real estate", "property", "reit"],
        "Cryptocurrency": ["crypto", "bitcoin", "blockchain"],
        "Commodities": ["commodity", "gold", "oil"],
    }
    for portfolio_item in profile.portfolio_exposure:
        if portfolio_item in portfolio_keywords:
            keywords.update(portfolio_keywords[portfolio_item])
    
    return {
        "keywords": sorted(list(keywords))[:20],  # Top 20
        "sectors": sorted(list(sectors)),
        "intent_types": list(intent_types),
        "profile_segment": _get_profile_segment(profile),
    }


def profile_to_subset_tags(profile: UserProfile) -> Dict[str, str]:
    """Generate tags to use when building a subset for this user.
    
    Args:
        profile: UserProfile object
    
    Returns:
        Dict with relevance_topic, audience_level, intent_type, content_filter
    """
    # Audience level from reading level
    audience_map = {
        "beginner": "beginner",
        "intermediate": "intermediate",
        "expert": "expert",
    }
    
    # Intent from role
    intent = "news"  # default
    role = profile.role
    if role in ROLE_TO_INTENT:
        intents = ROLE_TO_INTENT[role]["intent_types"]
        if intents:
            intent = intents[0]  # Primary intent
    
    # Content filter from risk (if available in answers)
    content_filter = "balanced"  # default
    # This would be extended if risk_appetite was stored in UserProfile
    
    # Primary topics from interests
    topics = ",".join(profile.interests[:3]) if profile.interests else "general"
    
    return {
        "relevance_topic": topics,
        "audience_level": audience_map.get(profile.reading_level, "intermediate"),
        "intent_type": intent,
        "content_filter": content_filter,
        "language_preference": "English",  # Can be extended from onboarding
    }


def _get_profile_segment(profile: UserProfile) -> str:
    """Determine the profile segment for caching purposes.
    
    Returns a segment name like "student_beginner", "professional_intermediate", etc.
    Users in the same segment share crawl results.
    """
    role_segment = profile.role.lower().split()[0]
    exp_segment = profile.reading_level
    
    return f"{role_segment}_{exp_segment}"


def filter_articles_for_profile(
    articles: list,
    profile: UserProfile,
) -> list:
    """Filter a list of articles to match a user profile's interests and reading level.
    
    Simple heuristic filtering:
    - Filter by keywords from crawl_queries
    - Filter by content depth (beginner users get simpler articles)
    
    Args:
        articles: List of Article objects or dicts with id, title, content, tags
        profile: UserProfile
    
    Returns:
        Filtered list of articles
    """
    crawl_intents = profile_to_crawl_queries(profile)
    keywords = set(crawl_intents.get("keywords", []))
    
    filtered = []
    for article in articles:
        # Check if article matches any of user's keywords or interests
        article_text = f"{article.get('title', '')} {article.get('content', '')}".lower()
        article_tags = set(article.get("tags", []))
        
        # Match score: how many keywords appear in the article
        match_count = sum(1 for kw in keywords if kw.lower() in article_text)
        tag_match = len(article_tags & set(keywords))
        
        # Include if at least one keyword matches (or if no keywords specified)
        if not keywords or match_count >= 1 or tag_match >= 1:
            filtered.append(article)
    
    return filtered[:20]  # Return top 20


def tag_articles_with_profile_data(
    article: dict,
    profile: UserProfile,
) -> dict:
    """Enrich an article dict with tags based on profile relevance.
    
    Args:
        article: Article dict with id, title, content, tags
        profile: UserProfile
    
    Returns:
        Article dict with additional profile-specific tags in the tags list
    """
    tags = set(article.get("tags", []))
    subset_tags = profile_to_subset_tags(profile)
    crawl_intents = profile_to_crawl_queries(profile)
    
    # Add audience level tag
    tags.add(f"audience:{subset_tags['audience_level']}")
    
    # Add intent type tag
    tags.add(f"intent:{subset_tags['intent_type']}")
    
    # Add relevance score tag based on keyword matches
    keywords = set(crawl_intents.get("keywords", []))
    article_text = f"{article.get('title', '')} {article.get('content', '')}".lower()
    match_count = sum(1 for kw in keywords if kw.lower() in article_text)
    
    if match_count >= 3:
        tags.add("relevance:high")
    elif match_count >= 1:
        tags.add("relevance:medium")
    else:
        tags.add("relevance:low")
    
    article["tags"] = sorted(list(tags))
    return article


def get_profile_segment_cache_key(profile: UserProfile) -> str:
    """Get the cache key for storing crawl results by profile segment.
    
    Users with similar profiles share cached results to reduce crawl cost.
    
    Args:
        profile: UserProfile
    
    Returns:
        Cache key like "segment_student_beginner" or "segment_professional_expert"
    """
    segment = _get_profile_segment(profile)
    return f"segment_{segment}"
