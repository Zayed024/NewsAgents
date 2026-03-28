"""Discovery helpers for sitemap and in-page URL extraction."""

from __future__ import annotations

import re
from urllib.parse import urljoin, urlparse
from xml.etree import ElementTree as ET

from src.tools.corpus.dedup import canonicalize_url


DEFAULT_SEEDS = [
    "https://economictimes.indiatimes.com/news/economy",
    "https://economictimes.indiatimes.com/markets",
    "https://economictimes.indiatimes.com/industry",
]


def build_topic_seeds(topic: str) -> list[str]:
    topic_slug = re.sub(r"[^a-z0-9]+", "-", topic.lower()).strip("-")
    seeds = list(DEFAULT_SEEDS)
    if topic_slug:
        seeds.append(f"https://economictimes.indiatimes.com/topic/{topic_slug}")
    return seeds


def extract_urls_from_sitemap_xml(xml_text: str, allowed_domains: set[str]) -> list[str]:
    urls: list[str] = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return urls

    namespaces = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    candidates = root.findall(".//sm:loc", namespaces)
    if not candidates:
        candidates = root.findall(".//loc")

    for loc in candidates:
        if not loc.text:
            continue
        url = canonicalize_url(loc.text.strip())
        if _is_allowed_domain(url, allowed_domains):
            urls.append(url)

    return list(dict.fromkeys(urls))


def extract_urls_from_html(html: str, base_url: str, allowed_domains: set[str]) -> list[str]:
    hrefs = re.findall(r"href=[\"'](.*?)[\"']", html, flags=re.IGNORECASE)
    urls: list[str] = []
    for href in hrefs:
        if href.startswith("#") or href.startswith("javascript:") or href.startswith("mailto:"):
            continue
        absolute = canonicalize_url(urljoin(base_url, href))
        if not _is_allowed_domain(absolute, allowed_domains):
            continue
        urls.append(absolute)

    # Keep only article-like ET URLs to reduce crawl noise.
    article_like = [u for u in urls if "articleshow" in u or "/topic/" in u or "/news/" in u or "/markets/" in u]
    return list(dict.fromkeys(article_like))


def _is_allowed_domain(url: str, allowed_domains: set[str]) -> bool:
    host = urlparse(url).netloc.lower().replace("www.", "")
    allowed = {d.lower().replace("www.", "") for d in allowed_domains}
    return host in allowed
