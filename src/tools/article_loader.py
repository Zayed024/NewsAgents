"""Load articles and data from JSON files."""

import json
import os
from src.config import DATA_DIR
from src.models import Article, UserProfile


def load_budget_articles() -> list[Article]:
    """Load the 22 Union Budget articles."""
    path = os.path.join(DATA_DIR, "budget_articles", "articles.json")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return [Article(**a) for a in data]


def load_homepage_articles() -> list[Article]:
    """Load homepage articles for persona feed demo."""
    path = os.path.join(DATA_DIR, "homepage_articles.json")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return [Article(**a) for a in data]


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
