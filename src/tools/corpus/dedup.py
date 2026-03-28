"""Deduplication helpers: canonical URL normalization and near-duplicate detection."""

from __future__ import annotations

import hashlib
import re
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode


TRACKING_QUERY_PREFIXES = (
    "utm_",
    "fbclid",
    "gclid",
    "igshid",
    "mc_",
    "mkt_",
)


def canonicalize_url(url: str) -> str:
    """Normalize URL for stable identity and dedup."""
    parsed = urlparse(url.strip())
    scheme = "https"
    netloc = parsed.netloc.lower().replace("www.", "")
    path = re.sub(r"/+", "/", parsed.path).rstrip("/") or "/"

    query_items = []
    for key, value in parse_qsl(parsed.query, keep_blank_values=True):
        key_l = key.lower()
        if any(key_l.startswith(prefix) for prefix in TRACKING_QUERY_PREFIXES):
            continue
        query_items.append((key_l, value))
    query_items.sort(key=lambda x: (x[0], x[1]))
    query = urlencode(query_items)

    return urlunparse((scheme, netloc, path, "", query, ""))


def normalize_text(text: str) -> str:
    text = text.lower()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[^a-z0-9 ]", "", text)
    return text.strip()


def content_hash(text: str) -> str:
    return hashlib.sha256(normalize_text(text).encode("utf-8")).hexdigest()


def simhash64(text: str) -> int:
    """Compute 64-bit simhash using token hashes."""
    tokens = [t for t in normalize_text(text).split(" ") if t]
    if not tokens:
        return 0

    vector = [0] * 64
    for token in tokens:
        h = int(hashlib.md5(token.encode("utf-8")).hexdigest(), 16)
        for i in range(64):
            bit = (h >> i) & 1
            vector[i] += 1 if bit else -1

    fingerprint = 0
    for i, val in enumerate(vector):
        if val >= 0:
            fingerprint |= (1 << i)
    return fingerprint


def hamming_distance_64(a: int, b: int) -> int:
    return (a ^ b).bit_count()


def is_near_duplicate(text_a: str, text_b: str, threshold: int = 6) -> bool:
    """Return True when lexical overlap or simhash proximity indicate near-duplicate content."""
    if _jaccard_token_similarity(text_a, text_b) >= 0.72:
        return True

    sa = simhash64(text_a)
    sb = simhash64(text_b)
    return hamming_distance_64(sa, sb) <= threshold


def _jaccard_token_similarity(text_a: str, text_b: str) -> float:
    tokens_a = {t for t in normalize_text(text_a).split(" ") if t}
    tokens_b = {t for t in normalize_text(text_b).split(" ") if t}
    if not tokens_a or not tokens_b:
        return 0.0
    inter = len(tokens_a.intersection(tokens_b))
    union = len(tokens_a.union(tokens_b))
    if union == 0:
        return 0.0
    return inter / union
