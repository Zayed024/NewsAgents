"""Bootstrap corpus store from existing local datasets."""

from __future__ import annotations

import json
import os

from src.config import DATA_DIR
from src.tools.corpus.compliance import validate_crawl_preflight, write_compliance_snapshot
from src.tools.corpus.crawler import EconomicTimesCrawler
from src.tools.corpus.store import ArticleCorpusStore


def _load_json(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def bootstrap_from_local_files() -> int:
    """Load current static files into the corpus store."""
    store = ArticleCorpusStore()
    docs = []

    budget_path = os.path.join(DATA_DIR, "budget_articles", "articles.json")
    homepage_path = os.path.join(DATA_DIR, "homepage_articles.json")

    if os.path.exists(budget_path):
        budget = _load_json(budget_path)
        if isinstance(budget, list):
            docs.extend(budget)

    if os.path.exists(homepage_path):
        homepage = _load_json(homepage_path)
        if isinstance(homepage, list):
            docs.extend(homepage)

    return store.upsert_articles(docs)


def ingest_topic_from_web(topic: str, max_pages: int = 60, max_depth: int = 2) -> int:
    """Discover and ingest ET topic coverage into corpus store."""
    preflight = validate_crawl_preflight(topic=topic, max_pages=max_pages, max_depth=max_depth)
    if not preflight.get("allowed", False):
        write_compliance_snapshot(
            operation="ingest_topic_from_web",
            preflight=preflight,
            decision="denied_policy",
            metadata={"topic": topic, "max_pages": max_pages, "max_depth": max_depth},
        )
        return 0

    write_compliance_snapshot(
        operation="ingest_topic_from_web",
        preflight=preflight,
        decision="allowed",
        metadata={"topic": topic, "max_pages": max_pages, "max_depth": max_depth},
    )

    crawler = EconomicTimesCrawler()
    docs = crawler.crawl_topic(topic=topic, max_pages=max_pages, max_depth=max_depth)
    store = ArticleCorpusStore()
    return store.upsert_articles(docs)


if __name__ == "__main__":
    inserted = bootstrap_from_local_files()
    print(f"Corpus bootstrap complete. Inserted/updated docs: {inserted}")
