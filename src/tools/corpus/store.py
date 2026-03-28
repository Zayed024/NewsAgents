"""Local corpus storage and retrieval for ET articles."""

from __future__ import annotations

import json
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Any

from src.config import DATA_DIR
from src.models import Article
from src.tools.corpus.dedup import canonicalize_url, content_hash, simhash64, hamming_distance_64


class ArticleCorpusStore:
    """Simple JSONL-based article store with deterministic topic retrieval."""

    def __init__(
        self,
        store_path: str | None = None,
    ):
        base = os.path.join(DATA_DIR, "corpus")
        self.store_path = store_path or os.path.join(base, "articles.jsonl")
        os.makedirs(os.path.dirname(self.store_path), exist_ok=True)

    def upsert_articles(self, docs: list[dict[str, Any]]) -> int:
        """Insert or update articles with canonical dedup and version tracking."""
        existing = self._read_docs()

        by_key: dict[str, dict[str, Any]] = {}
        for doc in existing:
            key = self._doc_key(doc)
            by_key[key] = doc

        inserted = 0
        for raw in docs:
            normalized = self._normalize_doc(raw)
            if not normalized:
                continue
            key = self._doc_key(normalized)

            existing_doc = by_key.get(key)
            if existing_doc is None:
                # Secondary near-duplicate guard against URL variants.
                near_key = self._find_near_duplicate_key(normalized, by_key)
                if near_key:
                    existing_doc = by_key.get(near_key)
                    key = near_key

            if existing_doc is None:
                inserted += 1
                by_key[key] = normalized
            else:
                by_key[key] = self._merge_version(existing_doc, normalized)

        self._write_docs(list(by_key.values()))
        return inserted

    def list_articles(self) -> list[Article]:
        """Return all stored documents as Article models."""
        docs = self._read_docs()
        out: list[Article] = []
        for d in docs:
            art = self._doc_to_article(d)
            if art:
                out.append(art)
        return out

    def get_homepage_slice(self, max_items: int = 25) -> list[Article]:
        """Return newest articles for feed experiences."""
        articles = self.list_articles()
        articles.sort(key=lambda a: a.published_at, reverse=True)
        return articles[:max_items]

    def get_topic_articles(self, topic: str, max_items: int = 100) -> list[Article]:
        """Return top lexical matches for a topic across stored corpus."""
        articles = self.list_articles()
        if not topic.strip():
            return articles[:max_items]

        tokens = _topic_tokens(topic)
        scored: list[tuple[int, Article]] = []

        for article in articles:
            text = " ".join([
                article.title.lower(),
                article.category.lower(),
                " ".join(t.lower() for t in article.tags),
                article.content.lower(),
            ])
            score = sum(1 for token in tokens if token in text)
            if score > 0:
                scored.append((score, article))

        scored.sort(key=lambda item: (item[0], item[1].published_at), reverse=True)
        return [article for _, article in scored[:max_items]]

    def _read_docs(self) -> list[dict[str, Any]]:
        if not os.path.exists(self.store_path):
            return []
        docs: list[dict[str, Any]] = []
        with open(self.store_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    docs.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return docs

    def _write_docs(self, docs: list[dict[str, Any]]):
        with open(self.store_path, "w", encoding="utf-8") as f:
            for doc in docs:
                f.write(json.dumps(doc, ensure_ascii=False) + "\n")

    def _doc_key(self, doc: dict[str, Any]) -> str:
        canonical = str(doc.get("canonical_url", "")).strip()
        if canonical:
            return f"canonical:{canonical}"
        doc_id = str(doc.get("id", "")).strip()
        url = str(doc.get("url", "")).strip()
        if doc_id:
            return f"id:{doc_id}"
        if url:
            return f"url:{url}"
        return f"fallback:{hash(json.dumps(doc, sort_keys=True))}"

    def _normalize_doc(self, raw: dict[str, Any]) -> dict[str, Any] | None:
        title = str(raw.get("title", "")).strip()
        content = str(raw.get("content", "")).strip()
        if not title or not content:
            return None

        now = datetime.now(timezone.utc).isoformat()

        doc_id = str(raw.get("id", "")).strip()
        if not doc_id:
            doc_id = _slugify(title)[:60]

        raw_url = str(raw.get("url", "")).strip()
        canonical_url = canonicalize_url(raw_url) if raw_url else ""
        content = str(raw.get("content", "")).strip()
        c_hash = content_hash(content)
        c_simhash = simhash64(content)

        return {
            "doc_uid": str(raw.get("doc_uid", uuid.uuid4().hex)),
            "id": doc_id,
            "title": title,
            "published_at": str(raw.get("published_at", now)),
            "category": str(raw.get("category", "general")),
            "content": content,
            "author": str(raw.get("author", "ET Staff")),
            "tags": list(raw.get("tags", [])) if isinstance(raw.get("tags", []), list) else [],
            "url": raw_url,
            "canonical_url": canonical_url,
            "source": str(raw.get("source", "economictimes")),
            "fetched_at": str(raw.get("fetched_at", now)),
            "content_hash": c_hash,
            "content_simhash": c_simhash,
            "version": int(raw.get("version", 1)),
            "previous_doc_uid": str(raw.get("previous_doc_uid", "")),
        }

    def _find_near_duplicate_key(self, doc: dict[str, Any], by_key: dict[str, dict[str, Any]]) -> str | None:
        simhash = int(doc.get("content_simhash", 0))
        for key, existing in by_key.items():
            existing_simhash = int(existing.get("content_simhash", 0))
            if hamming_distance_64(simhash, existing_simhash) <= 4:
                return key
        return None

    def _merge_version(self, existing: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
        if incoming.get("content_hash") == existing.get("content_hash"):
            # No semantic content change; just refresh fetch timestamp and metadata fields.
            merged = existing.copy()
            merged["fetched_at"] = incoming.get("fetched_at", existing.get("fetched_at", ""))
            merged["published_at"] = incoming.get("published_at", existing.get("published_at", ""))
            merged["tags"] = list(dict.fromkeys((existing.get("tags", []) or []) + (incoming.get("tags", []) or [])))
            merged["author"] = incoming.get("author", existing.get("author", "ET Staff"))
            merged["title"] = incoming.get("title", existing.get("title", ""))
            return merged

        merged = incoming.copy()
        merged["version"] = int(existing.get("version", 1)) + 1
        merged["previous_doc_uid"] = str(existing.get("doc_uid", ""))
        if not merged.get("canonical_url"):
            merged["canonical_url"] = existing.get("canonical_url", "")
        if not merged.get("url"):
            merged["url"] = existing.get("url", "")
        return merged

    def _doc_to_article(self, doc: dict[str, Any]) -> Article | None:
        try:
            return Article(
                id=str(doc.get("id", "")).strip() or _slugify(str(doc.get("title", "article"))),
                title=str(doc.get("title", "")).strip(),
                published_at=str(doc.get("published_at", datetime.now(timezone.utc).isoformat())),
                category=str(doc.get("category", "general")),
                content=str(doc.get("content", "")).strip(),
                author=str(doc.get("author", "ET Staff")),
                tags=list(doc.get("tags", [])) if isinstance(doc.get("tags", []), list) else [],
                url=str(doc.get("url", "")),
            )
        except Exception:
            return None


def _topic_tokens(topic: str) -> list[str]:
    raw = re.findall(r"[a-z0-9]+", topic.lower())
    return [t for t in raw if len(t) >= 3]


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "article"
