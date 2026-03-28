"""Materialized retrieval subsets for navigator and persona feed."""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from typing import Any

from src.config import DATA_DIR
from src.models import Article, UserProfile


def _subset_dir() -> str:
    base = os.path.join(DATA_DIR, "corpus", "subsets")
    os.makedirs(base, exist_ok=True)
    return base


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "topic"


def _subset_path(name: str) -> str:
    return os.path.join(_subset_dir(), f"{name}.json")


def _read_json(path: str) -> dict[str, Any] | None:
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _write_json(path: str, payload: dict[str, Any]):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def materialize_topic_subset(
    topic: str,
    selected_ids: list[str],
    inclusion_reasons: dict[str, str],
    exclusion_reasons: dict[str, str],
    coverage_mode: str,
    total_scanned: int,
):
    """Persist latest topic subset selection for replay/debug and fast reuse."""
    name = f"topic-{_slugify(topic)}"
    path = _subset_path(name)

    payload = {
        "topic": topic,
        "name": name,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "total_scanned": total_scanned,
        "selected_ids": selected_ids,
        "coverage_mode": coverage_mode,
        "inclusion_reasons": inclusion_reasons,
        "exclusion_reasons": exclusion_reasons,
    }
    _write_json(path, payload)


def load_topic_subset(topic: str, max_age_minutes: int = 120) -> dict[str, Any] | None:
    name = f"topic-{_slugify(topic)}"
    path = _subset_path(name)
    data = _read_json(path)
    if not data:
        return None

    updated_at = str(data.get("updated_at", "")).strip()
    if not updated_at:
        return None

    try:
        ts = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        age_minutes = (datetime.now(timezone.utc) - ts).total_seconds() / 60.0
        if age_minutes > max_age_minutes:
            return None
    except Exception:
        return None

    return data


def build_persona_general_subset(articles: list[Article], max_items: int = 40) -> dict[str, Any]:
    """Create a freshness-first general subset with light category diversity."""
    if not articles:
        return {
            "name": "persona-general",
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "selected_ids": [],
            "inclusion_reasons": {},
        }

    by_category: dict[str, list[Article]] = {}
    for article in sorted(articles, key=lambda a: a.published_at, reverse=True):
        by_category.setdefault(article.category or "general", []).append(article)

    selected: list[Article] = []
    cat_order = sorted(by_category.keys())
    cursor = 0
    while len(selected) < max_items and cat_order:
        category = cat_order[cursor % len(cat_order)]
        pool = by_category.get(category, [])
        if pool:
            selected.append(pool.pop(0))
        if not pool:
            cat_order = [c for c in cat_order if by_category.get(c)]
            cursor = 0
            continue
        cursor += 1

    reasons = {
        article.id: f"freshness_plus_diversity category={article.category or 'general'}"
        for article in selected
    }
    return {
        "name": "persona-general",
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "selected_ids": [article.id for article in selected],
        "inclusion_reasons": reasons,
    }


def materialize_persona_general_subset(articles: list[Article], max_items: int = 40):
    payload = build_persona_general_subset(articles, max_items=max_items)
    _write_json(_subset_path("persona-general"), payload)


def load_persona_general_subset(max_age_minutes: int = 180) -> dict[str, Any] | None:
    path = _subset_path("persona-general")
    data = _read_json(path)
    if not data:
        return None

    updated_at = str(data.get("updated_at", "")).strip()
    if not updated_at:
        return None

    try:
        ts = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        age_minutes = (datetime.now(timezone.utc) - ts).total_seconds() / 60.0
        if age_minutes > max_age_minutes:
            return None
    except Exception:
        return None

    return data


# --- Persona-Specific Subset Materialization ---


def _persona_slug(user_id: str) -> str:
    """Generate a slug for persona-specific subset."""
    return user_id.lower().replace(" ", "-").replace("_", "-")


def _article_matches_persona_interests(article: Article, interests: list[str]) -> bool:
    """Check if article content/category/tags match persona interests (case-insensitive)."""
    if not interests:
        return True

    # Normalize interests and include simple singular/plural variants.
    interests_lower: list[str] = []
    for interest in interests:
        token = interest.lower().strip()
        if not token:
            continue
        interests_lower.append(token)
        if token.endswith("s") and len(token) > 3:
            interests_lower.append(token[:-1])
        else:
            interests_lower.append(f"{token}s")

    # Deduplicate while preserving order.
    interests_lower = list(dict.fromkeys(interests_lower))
    
    # Check article category
    if article.category and article.category.lower() in interests_lower:
        return True

    # Check article title
    article_title_lower = article.title.lower()
    for interest in interests_lower:
        if interest in article_title_lower:
            return True

    # Check article tags
    if article.tags:
        for tag in article.tags:
            if tag.lower() in interests_lower:
                return True

    # Check article content (first 500 chars)
    article_content_lower = article.content[:500].lower()
    for interest in interests_lower:
        if interest in article_content_lower:
            return True

    return False


def build_persona_specific_subset(
    articles: list[Article],
    profile: UserProfile,
    max_items: int = 30,
) -> dict[str, Any]:
    """Create a persona-specific subset based on user interests and reading level.
    
    Strategy:
    1. Filter articles matching persona's interests
    2. Within matched set, apply freshness-first ordering with light category diversity
    3. Prefer articles that match multiple interests (stronger match)
    4. Include tag reasoning for inclusion/exclusion
    """
    if not articles:
        return {
            "name": f"persona-{_persona_slug(profile.user_id)}",
            "user_id": profile.user_id,
            "user_name": profile.name,
            "reading_level": profile.reading_level,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "selected_ids": [],
            "inclusion_reasons": {},
            "exclusion_reasons": {},
        }

    interests = profile.interests or []
    interests_lower: list[str] = []
    for interest in interests:
        token = interest.lower().strip()
        if not token:
            continue
        interests_lower.append(token)
        if token.endswith("s") and len(token) > 3:
            interests_lower.append(token[:-1])
        else:
            interests_lower.append(f"{token}s")
    interests_lower = list(dict.fromkeys(interests_lower))
    
    # Filter articles matching persona interests
    matched_articles: list[tuple[Article, int]] = []
    for article in articles:
        match_count = 0
        if _article_matches_persona_interests(article, interests):
            # Count how many interests this article matches
            article_text = (
                f"{article.title} {article.category or ''} "
                f"{', '.join(article.tags or [])} {article.content[:300]}"
            ).lower()
            for interest in interests_lower:
                if interest in article_text:
                    match_count += 1
            if match_count > 0:
                matched_articles.append((article, match_count))
    
    # If no exact matches, use all articles (fallback)
    if not matched_articles:
        source_articles = articles
        selection_mode = "no_interest_match_fallback_all"
    else:
        # Sort by match strength, then by freshness
        matched_articles.sort(
            key=lambda x: (x[1], x[0].published_at),
            reverse=True,
        )
        source_articles = [a for a, _ in matched_articles]
        selection_mode = "persona_interest_filtered"

    # Within source articles, apply freshness-first + category diversity
    by_category: dict[str, list[Article]] = {}
    for article in sorted(source_articles, key=lambda a: a.published_at, reverse=True):
        by_category.setdefault(article.category or "general", []).append(article)

    selected: list[Article] = []
    cat_order = sorted(by_category.keys())
    cursor = 0
    while len(selected) < max_items and cat_order:
        category = cat_order[cursor % len(cat_order)]
        pool = by_category.get(category, [])
        if pool:
            selected.append(pool.pop(0))
        if not pool:
            cat_order = [c for c in cat_order if by_category.get(c)]
            cursor = 0
            continue
        cursor += 1

    # Prepare inclusion/exclusion reasons
    selected_ids_set = {a.id for a in selected}
    inclusion_reasons = {}
    for article in selected:
        matched_count = next(
            (mc for a, mc in matched_articles if a.id == article.id), 0
        )
        reason_parts = [
            f"interests_matched={matched_count}",
            f"reading_level={profile.reading_level}",
            f"category={article.category or 'general'}",
        ]
        inclusion_reasons[article.id] = "; ".join(reason_parts)

    exclusion_reasons = {}
    for article in articles:
        if article.id not in selected_ids_set:
            if _article_matches_persona_interests(article, interests):
                exclusion_reasons[article.id] = (
                    "interest_matched_but_not_selected_after_diversity_sort"
                )
            else:
                exclusion_reasons[article.id] = "no_match_to_persona_interests"

    return {
        "name": f"persona-{_persona_slug(profile.user_id)}",
        "user_id": profile.user_id,
        "user_name": profile.name,
        "reading_level": profile.reading_level,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "selected_ids": [a.id for a in selected],
        "inclusion_reasons": inclusion_reasons,
        "exclusion_reasons": exclusion_reasons,
        "selection_mode": selection_mode,
        "total_scanned": len(articles),
    }


def materialize_persona_specific_subset(articles: list[Article], profile: UserProfile, max_items: int = 30):
    """Persist a persona-specific subset."""
    payload = build_persona_specific_subset(articles, profile, max_items=max_items)
    _write_json(_subset_path(f"persona-{_persona_slug(profile.user_id)}"), payload)


def load_persona_specific_subset(user_id: str, max_age_minutes: int = 180) -> dict[str, Any] | None:
    """Load a cached persona-specific subset if fresh."""
    path = _subset_path(f"persona-{_persona_slug(user_id)}")
    data = _read_json(path)
    if not data:
        return None

    updated_at = str(data.get("updated_at", "")).strip()
    if not updated_at:
        return None

    try:
        ts = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        age_minutes = (datetime.now(timezone.utc) - ts).total_seconds() / 60.0
        if age_minutes > max_age_minutes:
            return None
    except Exception:
        return None

    return data
