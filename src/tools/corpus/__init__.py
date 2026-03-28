"""Corpus tools for ingestion, storage, and retrieval."""

from src.tools.corpus.provider import get_corpus_provider
from src.tools.corpus.store import ArticleCorpusStore
from src.tools.corpus.crawler import EconomicTimesCrawler
from src.tools.corpus.discovery import build_topic_seeds
from src.tools.corpus.queue import CrawlQueue
from src.tools.corpus.dedup import canonicalize_url, content_hash, simhash64
from src.tools.corpus.relevance import hybrid_rank_articles
from src.tools.corpus.subsets import load_topic_subset, load_persona_general_subset
from src.tools.corpus.compliance import (
    is_corpus_kill_switch_enabled,
    validate_crawl_preflight,
    validate_subset_preflight,
    validate_retrieval_preflight,
    write_compliance_snapshot,
)

__all__ = [
    "get_corpus_provider",
    "ArticleCorpusStore",
    "EconomicTimesCrawler",
    "build_topic_seeds",
    "CrawlQueue",
    "canonicalize_url",
    "content_hash",
    "simhash64",
    "hybrid_rank_articles",
    "load_topic_subset",
    "load_persona_general_subset",
    "is_corpus_kill_switch_enabled",
    "validate_crawl_preflight",
    "validate_subset_preflight",
    "validate_retrieval_preflight",
    "write_compliance_snapshot",
]
