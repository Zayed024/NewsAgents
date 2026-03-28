"""Simple bounded crawl queue with depth and domain constraints."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from urllib.parse import urlparse

from src.tools.corpus.dedup import canonicalize_url


@dataclass
class CrawlTask:
    url: str
    depth: int


class CrawlQueue:
    def __init__(self, allowed_domains: set[str], max_depth: int = 2, max_items: int = 1000):
        self.allowed_domains = {d.lower().replace("www.", "") for d in allowed_domains}
        self.max_depth = max_depth
        self.max_items = max_items
        self._queue: deque[CrawlTask] = deque()
        self._seen: set[str] = set()

    def enqueue(self, url: str, depth: int) -> bool:
        if depth > self.max_depth:
            return False
        canon = canonicalize_url(url)
        if canon in self._seen:
            return False
        if len(self._seen) >= self.max_items:
            return False
        if not self._is_allowed(canon):
            return False

        self._seen.add(canon)
        self._queue.append(CrawlTask(url=canon, depth=depth))
        return True

    def dequeue(self) -> CrawlTask | None:
        if not self._queue:
            return None
        return self._queue.popleft()

    def __len__(self) -> int:
        return len(self._queue)

    def _is_allowed(self, url: str) -> bool:
        host = urlparse(url).netloc.lower().replace("www.", "")
        return host in self.allowed_domains
