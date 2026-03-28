"""Load articles and data from JSON files."""

import json
import os
from src.config import DATA_DIR
from src.models import Article, UserProfile
from src.tools.corpus.provider import get_corpus_provider


def load_budget_articles(topic: str = "Union Budget 2026", max_items: int = 200) -> list[Article]:
    """Load topic articles from the active corpus provider.

    Provider mode is controlled via CORPUS_PROVIDER env var:
    - static (default): existing local JSON dataset
    - store: corpus store (for crawler-ingested data)
    """
    provider = get_corpus_provider()
    articles = provider.get_topic_articles(topic=topic, max_items=max_items)

    # Backward-compatible fallback if provider returns empty.
    if articles:
        return articles

    path = os.path.join(DATA_DIR, "budget_articles", "articles.json")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return [Article(**a) for a in data][:max_items]


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


def load_breaking_news() -> Article:
    """Load the breaking news article for video demo."""
    path = os.path.join(DATA_DIR, "breaking_news", "bankruptcy_article.json")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return Article(**data)


def load_user_profile(profile_name: str) -> UserProfile:
    """Load a user profile by name (e.g. 'cfo_profile' or 'young_investor_profile')."""
    path = os.path.join(DATA_DIR, "user_profiles", f"{profile_name}.json")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return UserProfile(**data)
