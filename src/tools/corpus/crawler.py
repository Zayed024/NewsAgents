"""Economic Times crawler scaffold for Phase 1 corpus ingestion."""

from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from typing import Any

import httpx

from src.tools.corpus.discovery import (
    build_topic_seeds,
    extract_urls_from_html,
    extract_urls_from_sitemap_xml,
)
from src.tools.corpus.queue import CrawlQueue


class EconomicTimesCrawler:
    """Polite crawler scaffold for ET pages.

    This crawler is intentionally conservative for phase 1:
    - fetches explicit URL lists
    - extracts structured data from JSON-LD when available
    - avoids aggressive crawling logic until robots/terms strategy is finalized
    """

    def __init__(
        self,
        user_agent: str = "NewsAgentsBot/0.1 (+local-dev)",
        timeout_seconds: float = 20.0,
        allowed_domains: set[str] | None = None,
        request_delay_seconds: float = 0.6,
    ):
        self.user_agent = user_agent
        self.timeout_seconds = timeout_seconds
        self.allowed_domains = allowed_domains or {"economictimes.indiatimes.com", "economictimes.com"}
        self.request_delay_seconds = request_delay_seconds

    def crawl_urls(self, urls: list[str]) -> list[dict[str, Any]]:
        """Fetch and extract article docs from explicit URLs."""
        docs: list[dict[str, Any]] = []
        headers = {
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }

        with httpx.Client(timeout=self.timeout_seconds, follow_redirects=True, headers=headers) as client:
            for url in urls:
                if not _is_et_url(url):
                    continue
                try:
                    resp = client.get(url)
                    if resp.status_code != 200:
                        continue
                    doc = self._extract_article(url, resp.text)
                    if doc:
                        docs.append(doc)
                    time.sleep(self.request_delay_seconds)
                except Exception:
                    continue

        return docs

    def crawl_topic(
        self,
        topic: str,
        max_pages: int = 80,
        max_depth: int = 2,
    ) -> list[dict[str, Any]]:
        """Discover and crawl ET pages for a topic with bounded breadth/depth."""
        queue = CrawlQueue(
            allowed_domains=self.allowed_domains,
            max_depth=max_depth,
            max_items=max_pages * 4,
        )

        for seed in build_topic_seeds(topic):
            queue.enqueue(seed, depth=0)

        # Attempt to seed from common sitemap locations.
        docs: list[dict[str, Any]] = []
        headers = {
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }

        with httpx.Client(timeout=self.timeout_seconds, follow_redirects=True, headers=headers) as client:
            for sitemap_url in [
                "https://economictimes.indiatimes.com/sitemap_index.xml",
                "https://economictimes.indiatimes.com/sitemap.xml",
            ]:
                try:
                    resp = client.get(sitemap_url)
                    if resp.status_code == 200:
                        for sitemap_candidate in extract_urls_from_sitemap_xml(resp.text, self.allowed_domains)[:120]:
                            queue.enqueue(sitemap_candidate, depth=0)
                except Exception:
                    continue

            processed = 0
            while processed < max_pages:
                task = queue.dequeue()
                if task is None:
                    break

                try:
                    resp = client.get(task.url)
                    if resp.status_code != 200:
                        continue

                    html = resp.text
                    doc = self._extract_article(task.url, html)
                    if doc:
                        docs.append(doc)

                    for discovered in extract_urls_from_html(html, task.url, self.allowed_domains):
                        queue.enqueue(discovered, depth=task.depth + 1)

                    processed += 1
                    time.sleep(self.request_delay_seconds)
                except Exception:
                    continue

        # Dedupe by URL while preserving latest fetched copy.
        by_url: dict[str, dict[str, Any]] = {}
        for doc in docs:
            by_url[str(doc.get("url", ""))] = doc
        return list(by_url.values())

    def _extract_article(self, url: str, html: str) -> dict[str, Any] | None:
        """Best-effort extraction using JSON-LD, then HTML title fallback."""
        fetched_at = datetime.now(timezone.utc).isoformat()

        ld_json = _extract_json_ld_blocks(html)
        article_payload = _pick_news_article_payload(ld_json)

        if article_payload:
            headline = str(article_payload.get("headline", "")).strip()
            body = str(article_payload.get("articleBody", "")).strip()
            if headline and body:
                return {
                    "id": _id_from_url(url),
                    "title": headline,
                    "published_at": str(article_payload.get("datePublished", fetched_at)),
                    "category": "general",
                    "content": body,
                    "author": _extract_author(article_payload),
                    "tags": _extract_keywords(article_payload),
                    "url": url,
                    "source": "economictimes",
                    "fetched_at": fetched_at,
                }

        title_match = re.search(r"<title>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
        para_match = re.search(r"<p[^>]*>(.*?)</p>", html, re.IGNORECASE | re.DOTALL)
        if not title_match or not para_match:
            return None

        title = _clean_html_text(title_match.group(1))
        first_para = _clean_html_text(para_match.group(1))
        if not title or not first_para:
            return None

        return {
            "id": _id_from_url(url),
            "title": title,
            "published_at": fetched_at,
            "category": "general",
            "content": first_para,
            "author": "ET Staff",
            "tags": [],
            "url": url,
            "source": "economictimes",
            "fetched_at": fetched_at,
        }


def _extract_json_ld_blocks(html: str) -> list[dict[str, Any]]:
    blocks = re.findall(
        r"<script[^>]*type=['\"]application/ld\+json['\"][^>]*>(.*?)</script>",
        html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    out: list[dict[str, Any]] = []
    for block in blocks:
        text = block.strip()
        if not text:
            continue
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                out.append(parsed)
            elif isinstance(parsed, list):
                for item in parsed:
                    if isinstance(item, dict):
                        out.append(item)
        except Exception:
            continue
    return out


def _pick_news_article_payload(payloads: list[dict[str, Any]]) -> dict[str, Any] | None:
    for payload in payloads:
        t = payload.get("@type")
        if isinstance(t, list):
            type_values = {str(x).lower() for x in t}
            if "newsarticle" in type_values or "article" in type_values:
                return payload
        if isinstance(t, str) and t.lower() in {"newsarticle", "article"}:
            return payload
    return None


def _extract_author(payload: dict[str, Any]) -> str:
    author = payload.get("author", "ET Staff")
    if isinstance(author, str):
        return author
    if isinstance(author, dict):
        return str(author.get("name", "ET Staff"))
    if isinstance(author, list) and author:
        first = author[0]
        if isinstance(first, str):
            return first
        if isinstance(first, dict):
            return str(first.get("name", "ET Staff"))
    return "ET Staff"


def _extract_keywords(payload: dict[str, Any]) -> list[str]:
    keywords = payload.get("keywords", [])
    if isinstance(keywords, str):
        return [k.strip() for k in keywords.split(",") if k.strip()]
    if isinstance(keywords, list):
        return [str(k).strip() for k in keywords if str(k).strip()]
    return []


def _id_from_url(url: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", url.lower()).strip("-")
    return f"et-{slug[-80:]}"


def _clean_html_text(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _is_et_url(url: str) -> bool:
    lowered = url.lower()
    return "economictimes.com" in lowered
