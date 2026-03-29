"""Phase 6: Metadata Enricher — Add sentiment, credibility, source info to articles.

Enriches articles with:
- Sentiment (bullish, neutral, bearish for finance)
- Credibility score (0-1, based on source reputation)
- Source type (news, blog, official, research)
- Author credibility
- Content freshness
- Urgency badge (breaking, important, routine)
"""

from typing import Optional


class ArticleMetadata:
    """Rich metadata for an article."""
    
    def __init__(
        self,
        article_id: str,
        sentiment: str = "neutral",  # bullish, neutral, bearish
        sentiment_score: float = 0.5,  # 0-1, 0=bearish, 0.5=neutral, 1=bullish
        credibility_score: float = 0.7,  # 0-1, source reputation
        source_type: str = "news",  # news, blog, official, research, social
        urgency: str = "routine",  # breaking, important, routine
        freshness_hours: int = 0,  # How old is article (0-24 hours)
        author_credibility: Optional[int] = None,  # Number of publications (None if unknown)
        content_quality: str = "standard",  # excellent, good, standard, low
    ):
        self.article_id = article_id
        self.sentiment = sentiment
        self.sentiment_score = max(0.0, min(1.0, sentiment_score))
        self.credibility_score = max(0.0, min(1.0, credibility_score))
        self.source_type = source_type
        self.urgency = urgency
        self.freshness_hours = freshness_hours
        self.author_credibility = author_credibility
        self.content_quality = content_quality
    
    def to_dict(self) -> dict:
        return {
            "article_id": self.article_id,
            "sentiment": self.sentiment,
            "sentiment_score": self.sentiment_score,
            "credibility_score": self.credibility_score,
            "source_type": self.source_type,
            "urgency": self.urgency,
            "freshness_hours": self.freshness_hours,
            "author_credibility": self.author_credibility,
            "content_quality": self.content_quality,
        }


# ============================================================
# Rule-Based Metadata Inference
# ============================================================

def infer_article_metadata(
    article_dict: dict,
    user_profile: Optional[dict] = None,
) -> ArticleMetadata:
    """
    Infer metadata for an article using rule-based analysis.
    
    Rules are deterministic (no LLM cost) and based on:
    - Article content (keywords, language)
    - Source (known publishers)
    - Publication timestamp
    - Author information
    
    Args:
        article_dict: Article with title, content, author, published_at
        user_profile: Optional user profile for context
    
    Returns:
        ArticleMetadata with inferred values
    """
    article_id = article_dict.get("id", "unknown")
    title = article_dict.get("title", "").lower()
    content = article_dict.get("content", "").lower()
    author = article_dict.get("author", "").lower()
    
    # ========== Sentiment Analysis (Rule-based) ==========
    bullish_keywords = [
        "rally", "surge", "jump", "boom", "soar", "recover", "growth", "profit",
        "gain", "upside", "bullish", "strong", "outperform", "beat", "success",
        "opportunity", "breakthrough", "innovative", "winning", "momentum",
    ]
    bearish_keywords = [
        "crash", "plunge", "fall", "decline", "loss", "down", "slide", "bearish",
        "weak", "underperform", "miss", "fail", "risk", "concern", "threat",
        "challenge", "downside", "trouble", "crisis", "collapse",
    ]
    
    bullish_count = sum(
        title.count(kw) + content.count(kw) // 5  # Content weighted less
        for kw in bullish_keywords
    )
    bearish_count = sum(
        title.count(kw) + content.count(kw) // 5
        for kw in bearish_keywords
    )
    
    if bullish_count > bearish_count:
        sentiment = "bullish"
        sentiment_score = min(1.0, 0.5 + bullish_count * 0.1)
    elif bearish_count > bullish_count:
        sentiment = "bearish"
        sentiment_score = max(0.0, 0.5 - bearish_count * 0.1)
    else:
        sentiment = "neutral"
        sentiment_score = 0.5
    
    # ========== Source Credibility ==========
    source_type_map = {
        "et.economictimes": ("news", 0.95),
        "bloomberg": ("news", 0.92),
        "reuters": ("news", 0.93),
        "wsj": ("news", 0.91),
        "cnbc": ("news", 0.90),
        "moneycontrol": ("news", 0.85),
        "business today": ("news", 0.83),
        "fintech": ("research", 0.80),
        "blog": ("blog", 0.60),
        "twitter": ("social", 0.50),
        "reddit": ("social", 0.45),
    }
    
    source_type = "news"
    credibility_score = 0.70  # Default
    
    for source_key, (stype, cred) in source_type_map.items():
        if source_key in author or source_key in content[:100]:
            source_type = stype
            credibility_score = cred
            break
    
    # ========== Content Quality ==========
    content_length = len(content.split())
    
    if content_length > 500:
        content_quality = "excellent" if credibility_score > 0.85 else "good"
    elif content_length > 300:
        content_quality = "good" if credibility_score > 0.75 else "standard"
    else:
        content_quality = "standard" if credibility_score > 0.60 else "low"
    
    # ========== Urgency Badges ==========
    urgent_keywords = ["breaking", "just in", "urgent", "emergency", "developing"]
    important_keywords = ["announced", "significant", "major", "major announcement", "critical"]
    
    has_urgent = any(kw in title for kw in urgent_keywords)
    has_important = any(kw in title for kw in important_keywords)
    
    if has_urgent:
        urgency = "breaking"
    elif has_important:
        urgency = "important"
    else:
        urgency = "routine"
    
    # ========== Freshness ==========
    import time
    from datetime import datetime
    
    try:
        pub_date = article_dict.get("published_at", "")
        if pub_date:
            # Parse ISO format date
            pub_datetime = datetime.fromisoformat(pub_date)
            now = datetime.now()
            hours_ago = int((now - pub_datetime).total_seconds() / 3600)
            freshness_hours = min(24, hours_ago)  # Cap at 24 hours
        else:
            freshness_hours = 0
    except Exception:
        freshness_hours = 0
    
    # ========== Author Credibility ==========
    # Rule: Known financial analysts/journalists get boost
    known_experts = [
        "raghuram rajan", "swaminathan aiyar", "ajit ranade",
        "upal bhattacharya", "sumit bose", "deepthi bhatnagar",
    ]
    
    author_credibility = None
    for expert in known_experts:
        if expert in author:
            author_credibility = 50  # High authority
            break
    
    return ArticleMetadata(
        article_id=article_id,
        sentiment=sentiment,
        sentiment_score=sentiment_score,
        credibility_score=credibility_score,
        source_type=source_type,
        urgency=urgency,
        freshness_hours=freshness_hours,
        author_credibility=author_credibility,
        content_quality=content_quality,
    )


def get_urgency_badge(metadata: ArticleMetadata) -> str:
    """Get UI badge for article urgency."""
    badges = {
        "breaking": "🔴 BREAKING",
        "important": "🟡 IMPORTANT",
        "routine": "",
    }
    return badges.get(metadata.urgency, "")


def get_sentiment_emoji(metadata: ArticleMetadata) -> str:
    """Get emoji representing article sentiment."""
    if metadata.sentiment == "bullish":
        return "📈"
    elif metadata.sentiment == "bearish":
        return "📉"
    else:
        return "➡️"


def get_credibility_stars(metadata: ArticleMetadata) -> str:
    """Get star rating for credibility (1-5 stars)."""
    score = metadata.credibility_score
    stars = int(score * 5)
    return "⭐" * stars + "☆" * (5 - stars)


def format_freshness(metadata: ArticleMetadata) -> str:
    """Format freshness as human-readable time."""
    hours = metadata.freshness_hours
    
    if hours < 1:
        return "Just now"
    elif hours < 24:
        return f"{hours}h ago"
    elif hours < 48:
        return "1 day ago"
    else:
        return f"{hours // 24}d ago"


def enrich_feed_with_metadata(
    feed_items: list[dict],
    user_profile: Optional[dict] = None,
) -> dict[str, ArticleMetadata]:
    """
    Enrich feed items with metadata.
    
    Args:
        feed_items: List of article dicts
        user_profile: Optional user context
    
    Returns:
        Dict mapping article_id -> ArticleMetadata
    """
    metadata_map = {}
    
    for item in feed_items:
        article_id = item.get("id", str(hash(item.get("title", ""))))
        metadata = infer_article_metadata(item, user_profile)
        metadata_map[article_id] = metadata
    
    return metadata_map


def get_metadata_summary_stats(
    metadata_map: dict[str, ArticleMetadata],
) -> dict:
    """Get summary statistics across all enriched metadata."""
    
    if not metadata_map:
        return {
            "total_articles": 0,
            "sentiment_distribution": {},
            "urgency_distribution": {},
            "avg_credibility": 0.0,
            "content_quality_distribution": {},
        }
    
    articles = list(metadata_map.values())
    
    sentiments = [a.sentiment for a in articles]
    urgencies = [a.urgency for a in articles]
    qualities = [a.content_quality for a in articles]
    credibilities = [a.credibility_score for a in articles]
    
    return {
        "total_articles": len(articles),
        "sentiment_distribution": {
            "bullish": sentiments.count("bullish"),
            "neutral": sentiments.count("neutral"),
            "bearish": sentiments.count("bearish"),
        },
        "urgency_distribution": {
            "breaking": urgencies.count("breaking"),
            "important": urgencies.count("important"),
            "routine": urgencies.count("routine"),
        },
        "content_quality_distribution": {
            "excellent": qualities.count("excellent"),
            "good": qualities.count("good"),
            "standard": qualities.count("standard"),
            "low": qualities.count("low"),
        },
        "avg_credibility": sum(credibilities) / len(credibilities) if credibilities else 0,
    }
