"""Phase 4 corpus operations: scheduled refresh and freshness monitoring."""

from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timezone
from typing import Any

from src.config import DATA_DIR
from src.models import UserProfile
from src.tools.article_loader import load_user_profile
from src.tools.corpus.bootstrap import bootstrap_from_local_files, ingest_topic_from_web
from src.tools.corpus.store import ArticleCorpusStore
from src.tools.corpus.subsets import (
    build_persona_specific_subset,
    materialize_persona_general_subset,
    materialize_topic_subset,
)
from src.tools.corpus.relevance import hybrid_rank_articles, llm_rerank_top
from src.tools.corpus.compliance import (
    validate_crawl_preflight,
    validate_subset_preflight,
    write_compliance_snapshot,
)


def _ops_dir() -> str:
    path = os.path.join(DATA_DIR, "corpus", "ops")
    os.makedirs(path, exist_ok=True)
    return path


def _subset_dir() -> str:
    path = os.path.join(DATA_DIR, "corpus", "subsets")
    os.makedirs(path, exist_ok=True)
    return path


def _summaries_path() -> str:
    return os.path.join(_ops_dir(), "run_summaries.jsonl")


def _append_summary(summary: dict[str, Any]) -> None:
    with open(_summaries_path(), "a", encoding="utf-8") as f:
        f.write(json.dumps(summary, ensure_ascii=False) + "\n")


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        ts = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return ts
    except Exception:
        return None


def _percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return round(ordered[0], 2)
    rank = (len(ordered) - 1) * p
    lo = int(rank)
    hi = min(lo + 1, len(ordered) - 1)
    frac = rank - lo
    val = ordered[lo] * (1.0 - frac) + ordered[hi] * frac
    return round(val, 2)


def _read_subset_files() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for name in os.listdir(_subset_dir()):
        if not name.endswith(".json"):
            continue
        path = os.path.join(_subset_dir(), name)
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            data["_file"] = name
            out.append(data)
        except Exception:
            continue
    return out


def compute_freshness_metrics(
    topic_stale_after_minutes: int = 120,
    persona_stale_after_minutes: int = 180,
) -> dict[str, Any]:
    """Compute corpus freshness metrics and stale subset rates."""
    now = datetime.now(timezone.utc)
    store = ArticleCorpusStore()
    articles = store.list_articles()
    subsets = _read_subset_files()

    article_ages_hours: list[float] = []
    for article in articles:
        ts = _parse_iso(article.published_at)
        if ts:
            article_ages_hours.append((now - ts).total_seconds() / 3600.0)

    topic_ages_minutes: list[float] = []
    persona_ages_minutes: list[float] = []
    topic_stale = 0
    persona_stale = 0

    for subset in subsets:
        ts = _parse_iso(str(subset.get("updated_at", "")).strip())
        if ts is None:
            continue
        age_minutes = (now - ts).total_seconds() / 60.0
        name = str(subset.get("name", ""))
        if name.startswith("topic-"):
            topic_ages_minutes.append(age_minutes)
            if age_minutes > topic_stale_after_minutes:
                topic_stale += 1
        elif name.startswith("persona-"):
            persona_ages_minutes.append(age_minutes)
            if age_minutes > persona_stale_after_minutes:
                persona_stale += 1

    topic_total = len(topic_ages_minutes)
    persona_total = len(persona_ages_minutes)

    return {
        "generated_at": now.isoformat(),
        "corpus": {
            "article_count": len(articles),
            "article_age_hours": {
                "min": round(min(article_ages_hours), 2) if article_ages_hours else 0.0,
                "p50": _percentile(article_ages_hours, 0.50),
                "p95": _percentile(article_ages_hours, 0.95),
                "max": round(max(article_ages_hours), 2) if article_ages_hours else 0.0,
            },
        },
        "topic_subsets": {
            "total": topic_total,
            "stale": topic_stale,
            "stale_rate": round((topic_stale / topic_total) if topic_total else 0.0, 4),
            "age_minutes": {
                "min": round(min(topic_ages_minutes), 2) if topic_ages_minutes else 0.0,
                "p50": _percentile(topic_ages_minutes, 0.50),
                "p95": _percentile(topic_ages_minutes, 0.95),
                "max": round(max(topic_ages_minutes), 2) if topic_ages_minutes else 0.0,
            },
            "stale_after_minutes": topic_stale_after_minutes,
        },
        "persona_subsets": {
            "total": persona_total,
            "stale": persona_stale,
            "stale_rate": round((persona_stale / persona_total) if persona_total else 0.0, 4),
            "age_minutes": {
                "min": round(min(persona_ages_minutes), 2) if persona_ages_minutes else 0.0,
                "p50": _percentile(persona_ages_minutes, 0.50),
                "p95": _percentile(persona_ages_minutes, 0.95),
                "max": round(max(persona_ages_minutes), 2) if persona_ages_minutes else 0.0,
            },
            "stale_after_minutes": persona_stale_after_minutes,
        },
    }


async def _refresh_topic_subset(topic: str, max_candidates: int = 100) -> dict[str, Any]:
    """Refresh one topic subset using hybrid + rerank path."""
    store = ArticleCorpusStore()
    articles = store.list_articles()
    if not articles:
        return {
            "topic": topic,
            "status": "skipped_empty_corpus",
            "selected_count": 0,
            "scanned": 0,
        }

    ranked = hybrid_rank_articles(topic=topic, articles=articles, top_k=min(max_candidates, len(articles)))
    selected_ids, reasons, mode = await llm_rerank_top(
        topic=topic,
        ranked_rows=ranked,
        session_id="ops-subset-refresh",
        top_k=min(18, len(ranked)),
        final_k=min(max(8, len(ranked) // 2), len(ranked)),
    )

    selected_set = set(selected_ids)
    if not selected_set:
        selected_set = {a.id for a in articles}
        mode = "hybrid_fallback_all"

    ranked_by_id = {row["article_id"]: row for row in ranked}
    inclusion_reasons = {
        aid: reasons.get(aid, ranked_by_id.get(aid, {}).get("base_reason", "selected"))
        for aid in selected_set
    }
    exclusion_reasons: dict[str, str] = {}
    for article in articles:
        if article.id in selected_set:
            continue
        row = ranked_by_id.get(article.id)
        if row:
            exclusion_reasons[article.id] = (
                f"not_selected_after_rerank combined={row['combined_score']}; "
                f"lexical={row['bm25_score']}; semantic={row['embedding_score']}"
            )
        else:
            exclusion_reasons[article.id] = "not_in_top_hybrid_candidates"

    materialize_topic_subset(
        topic=topic,
        selected_ids=[a.id for a in articles if a.id in selected_set],
        inclusion_reasons=inclusion_reasons,
        exclusion_reasons=exclusion_reasons,
        coverage_mode=mode,
        total_scanned=len(articles),
    )

    return {
        "topic": topic,
        "status": "success",
        "selected_count": len(selected_set),
        "scanned": len(articles),
        "coverage_mode": mode,
    }


def _refresh_persona_subsets(profile_names: list[str], max_items: int = 40) -> list[dict[str, Any]]:
    store = ArticleCorpusStore()
    articles = store.list_articles()
    if not articles:
        return [{"status": "skipped_empty_corpus"}]

    summaries: list[dict[str, Any]] = []

    materialize_persona_general_subset(articles, max_items=max_items)
    summaries.append(
        {
            "subset": "persona-general",
            "status": "success",
            "selected_count": min(max_items, len(articles)),
        }
    )

    for profile_name in profile_names:
        try:
            profile: UserProfile = load_user_profile(profile_name)
            payload = build_persona_specific_subset(articles, profile, max_items=max_items)
            path = os.path.join(_subset_dir(), f"persona-{profile.user_id.lower().replace('_', '-').replace(' ', '-')}.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            summaries.append(
                {
                    "subset": f"persona-{profile.user_id}",
                    "status": "success",
                    "selected_count": len(payload.get("selected_ids", [])),
                }
            )
        except Exception as exc:
            summaries.append(
                {
                    "subset": f"persona-{profile_name}",
                    "status": "error",
                    "error": str(exc),
                }
            )

    return summaries


def run_crawl_refresh(
    topic: str,
    max_pages: int = 60,
    max_depth: int = 2,
    bootstrap_if_empty: bool = True,
) -> dict[str, Any]:
    """Scheduled runner entrypoint for corpus crawl/refresh."""
    started_at = datetime.now(timezone.utc)
    preflight = validate_crawl_preflight(topic=topic, max_pages=max_pages, max_depth=max_depth)
    if not preflight.get("allowed", False):
        snapshot = write_compliance_snapshot(
            operation="crawl_refresh",
            preflight=preflight,
            decision="denied_policy",
            metadata={"topic": topic, "max_pages": max_pages, "max_depth": max_depth},
        )
        summary = {
            "run_type": "crawl_refresh",
            "topic": topic,
            "started_at": started_at.isoformat(),
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "status": "denied_policy",
            "preflight": preflight,
            "compliance_snapshot": snapshot,
        }
        _append_summary(summary)
        return summary

    store = ArticleCorpusStore()
    before_count = len(store.list_articles())

    bootstrap_inserted = 0
    if bootstrap_if_empty and before_count == 0:
        bootstrap_inserted = bootstrap_from_local_files()

    inserted_or_updated = ingest_topic_from_web(topic=topic, max_pages=max_pages, max_depth=max_depth)
    after_count = len(store.list_articles())

    summary = {
        "run_type": "crawl_refresh",
        "topic": topic,
        "started_at": started_at.isoformat(),
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "status": "success",
        "bootstrap_inserted": bootstrap_inserted,
        "ingested_inserted_or_updated": inserted_or_updated,
        "article_count_before": before_count,
        "article_count_after": after_count,
        "article_count_delta": after_count - before_count,
        "max_pages": max_pages,
        "max_depth": max_depth,
        "preflight": preflight,
    }
    snapshot = write_compliance_snapshot(
        operation="crawl_refresh",
        preflight=preflight,
        decision="allowed",
        metadata={
            "topic": topic,
            "article_count_before": before_count,
            "article_count_after": after_count,
        },
    )
    summary["compliance_snapshot"] = snapshot
    summary["freshness_metrics"] = compute_freshness_metrics()
    _append_summary(summary)
    return summary


def run_subset_refresh(
    topics: list[str],
    profile_names: list[str] | None = None,
    max_items: int = 40,
) -> dict[str, Any]:
    """Scheduled runner entrypoint for topic/persona subset refresh."""
    started_at = datetime.now(timezone.utc)
    profile_names = profile_names or ["cfo_profile", "young_investor_profile"]

    preflight = validate_subset_preflight(topics=topics, profile_names=profile_names, max_items=max_items)
    if not preflight.get("allowed", False):
        snapshot = write_compliance_snapshot(
            operation="subset_refresh",
            preflight=preflight,
            decision="denied_policy",
            metadata={"topics": topics, "profile_names": profile_names, "max_items": max_items},
        )
        summary = {
            "run_type": "subset_refresh",
            "started_at": started_at.isoformat(),
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "status": "denied_policy",
            "topics": topics,
            "preflight": preflight,
            "compliance_snapshot": snapshot,
        }
        _append_summary(summary)
        return summary

    topic_results: list[dict[str, Any]] = []
    for topic in topics:
        topic_results.append(_run_maybe_async(_refresh_topic_subset(topic=topic)))

    persona_results = _refresh_persona_subsets(profile_names=profile_names, max_items=max_items)

    metrics = compute_freshness_metrics()
    alerts: list[str] = []
    topic_stale_rate = float(metrics.get("topic_subsets", {}).get("stale_rate", 0.0))
    persona_stale_rate = float(metrics.get("persona_subsets", {}).get("stale_rate", 0.0))
    if topic_stale_rate > 0.25:
        alerts.append(f"topic_subset_stale_rate_high:{topic_stale_rate}")
    if persona_stale_rate > 0.25:
        alerts.append(f"persona_subset_stale_rate_high:{persona_stale_rate}")

    summary = {
        "run_type": "subset_refresh",
        "started_at": started_at.isoformat(),
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "status": "success" if not alerts else "warning",
        "topics": topics,
        "topic_results": topic_results,
        "persona_results": persona_results,
        "alerts": alerts,
        "freshness_metrics": metrics,
        "preflight": preflight,
    }
    snapshot = write_compliance_snapshot(
        operation="subset_refresh",
        preflight=preflight,
        decision="allowed_with_warning" if alerts else "allowed",
        metadata={"topics": topics, "alerts": alerts},
    )
    summary["compliance_snapshot"] = snapshot
    _append_summary(summary)
    return summary


def _run_maybe_async(value: Any) -> Any:
    """Run coroutine values, passthrough non-coroutine values."""
    if asyncio.iscoroutine(value):
        return asyncio.run(value)
    return value


def load_recent_run_summaries(limit: int = 20) -> list[dict[str, Any]]:
    """Load most recent operation run summaries."""
    path = _summaries_path()
    if not os.path.exists(path):
        return []

    rows: list[dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
    if limit <= 0:
        return rows
    return rows[-limit:]
