"""Load articles and data from JSON files."""

import json
import os
from src.config import DATA_DIR
from src.models import Article, UserProfile
from src.tools.corpus.provider import get_corpus_provider


def load_budget_articles(
    topic: str = "Union Budget 2026",
    max_items: int = 200,
    min_items: int = 8,
) -> list[Article]:
    """Load topic articles from the active corpus provider.

    Provider mode is controlled via CORPUS_PROVIDER env var:
    - static (default): existing local JSON dataset
    - store: corpus store (for crawler-ingested data)
    """
    provider = get_corpus_provider()
    articles = provider.get_topic_articles(topic=topic, max_items=max_items)

    required_items = min(max_items, max(min_items, 0))
    path = os.path.join(DATA_DIR, "budget_articles", "articles.json")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    static_articles = [Article(**a) for a in data]

    # Ensure demo still has enough content even if live/store corpus is sparse.
    if len(articles) < required_items:
        seen_ids = {a.id for a in articles}
        for article in static_articles:
            if article.id in seen_ids:
                continue
            articles.append(article)
            seen_ids.add(article.id)
            if len(articles) >= max_items:
                break

    if articles:
        return articles[:max_items]
    return static_articles[:max_items]


def load_homepage_articles(max_items: int = 50) -> list[Article]:
    """Load homepage articles from active corpus provider."""
    provider = get_corpus_provider()
    articles = provider.get_homepage_articles(max_items=max_items)

    if articles:
        return articles

    path = os.path.join(DATA_DIR, "homepage_articles.json")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return [Article(**a) for a in data][:max_items]


def load_breaking_news_articles(max_items: int = 20) -> list[Article]:
    """Load all breaking news articles for video demo."""
    breaking_dir = os.path.join(DATA_DIR, "breaking_news")
    if not os.path.isdir(breaking_dir):
        return []

    articles: list[Article] = []
    for name in sorted(os.listdir(breaking_dir)):
        if not name.lower().endswith(".json"):
            continue
        path = os.path.join(breaking_dir, name)
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        articles.append(Article(**data))

    articles.sort(key=lambda a: a.published_at, reverse=True)
    return articles[:max_items]


def load_breaking_news(article_id: str | None = None) -> Article:
    """Load a specific breaking news article (or latest available one)."""
    articles = load_breaking_news_articles(max_items=100)
    if not articles:
        raise FileNotFoundError("No breaking news articles found in data/breaking_news")

    if article_id:
        for article in articles:
            if article.id == article_id:
                return article

    return articles[0]


def load_user_profile(profile_name: str) -> UserProfile:
    """Load a user profile by name or user_id.

    Handles both old names (cfo_profile) and new names (user-cfo-001).
    """
    # Migration map for renamed profiles
    _PROFILE_ALIASES = {
        "cfo_profile": "user-cfo-001",
        "young_investor_profile": "user-young-001",
    }
    resolved = _PROFILE_ALIASES.get(profile_name, profile_name)
    path = os.path.join(DATA_DIR, "user_profiles", f"{resolved}.json")
    if not os.path.exists(path):
        # Try original name as fallback
        path = os.path.join(DATA_DIR, "user_profiles", f"{profile_name}.json")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return UserProfile(**data)
