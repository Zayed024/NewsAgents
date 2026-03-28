"""Corpus provider abstraction for navigator and feed pipelines."""

from __future__ import annotations

import json
import os
from typing import Protocol

from src.config import DATA_DIR
from src.models import Article
from src.tools.corpus.store import ArticleCorpusStore
from src.tools.corpus.subsets import (
    load_persona_general_subset,
    materialize_persona_general_subset,
)


class ArticleCorpusProvider(Protocol):
    """Abstract corpus provider API."""

    def get_topic_articles(self, topic: str, max_items: int = 100) -> list[Article]:
        ...

    def get_homepage_articles(self, max_items: int = 25) -> list[Article]:
        ...


class StaticJsonCorpusProvider:
    """Current dataset-backed provider for deterministic local demos."""

    def get_topic_articles(self, topic: str, max_items: int = 100) -> list[Article]:
        path = os.path.join(DATA_DIR, "budget_articles", "articles.json")
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        articles = [Article(**a) for a in data]
        return articles[:max_items]

    def get_homepage_articles(self, max_items: int = 25) -> list[Article]:
        path = os.path.join(DATA_DIR, "homepage_articles.json")
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        articles = [Article(**a) for a in data]
        return articles[:max_items]


class StoreBackedCorpusProvider:
    """Store-backed provider for live/expanded corpus retrieval."""

    def __init__(self, store: ArticleCorpusStore | None = None):
        self.store = store or ArticleCorpusStore()

    def get_topic_articles(self, topic: str, max_items: int = 100) -> list[Article]:
        return self.store.get_topic_articles(topic=topic, max_items=max_items)

    def get_homepage_articles(self, max_items: int = 25) -> list[Article]:
        all_articles = self.store.list_articles()
        if not all_articles:
            return []

        subset = load_persona_general_subset()
        if not subset:
            materialize_persona_general_subset(all_articles, max_items=max(40, max_items))
            subset = load_persona_general_subset()

        if subset:
            selected_ids = set(subset.get("selected_ids", []))
            if selected_ids:
                ordered = [a for a in all_articles if a.id in selected_ids]
                ordered.sort(key=lambda a: a.published_at, reverse=True)
                if ordered:
                    return ordered[:max_items]

        return self.store.get_homepage_slice(max_items=max_items)


def get_corpus_provider() -> ArticleCorpusProvider:
    """Select provider by CORPUS_PROVIDER env var: static | store."""
    mode = os.getenv("CORPUS_PROVIDER", "static").strip().lower()
    if mode == "store":
        return StoreBackedCorpusProvider()
    return StaticJsonCorpusProvider()
