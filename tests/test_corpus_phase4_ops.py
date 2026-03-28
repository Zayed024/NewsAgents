import json
from datetime import datetime, timedelta, timezone

from src.models import Article
from src.tools.corpus import operations


class _FakeStore:
    def __init__(self, articles):
        self._articles = articles

    def list_articles(self):
        return list(self._articles)


def test_compute_freshness_metrics_with_subset_ages(tmp_path, monkeypatch):
    monkeypatch.setattr(operations, "DATA_DIR", str(tmp_path))

    now = datetime.now(timezone.utc)
    subset_dir = tmp_path / "corpus" / "subsets"
    subset_dir.mkdir(parents=True, exist_ok=True)

    topic_payload = {
        "name": "topic-union-budget-2026",
        "updated_at": (now - timedelta(minutes=150)).isoformat(),
        "selected_ids": ["a1"],
    }
    persona_payload = {
        "name": "persona-user-cfo-001",
        "updated_at": (now - timedelta(minutes=60)).isoformat(),
        "selected_ids": ["a2"],
    }
    with open(subset_dir / "topic-union-budget-2026.json", "w", encoding="utf-8") as f:
        json.dump(topic_payload, f)
    with open(subset_dir / "persona-user-cfo-001.json", "w", encoding="utf-8") as f:
        json.dump(persona_payload, f)

    articles = [
        Article(
            id="a1",
            title="Budget",
            published_at=(now - timedelta(hours=2)).isoformat(),
            category="economy",
            content="x",
            author="ET",
            tags=["economy"],
            url="u",
        )
    ]
    monkeypatch.setattr(operations, "ArticleCorpusStore", lambda: _FakeStore(articles))

    metrics = operations.compute_freshness_metrics(
        topic_stale_after_minutes=120,
        persona_stale_after_minutes=180,
    )

    assert metrics["corpus"]["article_count"] == 1
    assert metrics["topic_subsets"]["total"] == 1
    assert metrics["topic_subsets"]["stale"] == 1
    assert metrics["persona_subsets"]["total"] == 1
    assert metrics["persona_subsets"]["stale"] == 0


def test_run_subset_refresh_persists_summary(tmp_path, monkeypatch):
    monkeypatch.setattr(operations, "DATA_DIR", str(tmp_path))

    # Keep refresh internals deterministic and offline.
    async def _fake_refresh_topic_subset(topic, max_candidates=100):
        return {
            "topic": topic,
            "status": "success",
            "selected_count": 3,
            "scanned": 5,
            "coverage_mode": "hybrid_bm25_embedding_fallback",
        }

    monkeypatch.setattr(
        operations,
        "_refresh_topic_subset",
        _fake_refresh_topic_subset,
    )
    monkeypatch.setattr(
        operations,
        "_refresh_persona_subsets",
        lambda profile_names, max_items=40: [
            {"subset": "persona-general", "status": "success", "selected_count": 4}
        ],
    )
    monkeypatch.setattr(
        operations,
        "compute_freshness_metrics",
        lambda topic_stale_after_minutes=120, persona_stale_after_minutes=180: {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "corpus": {"article_count": 5, "article_age_hours": {"min": 1, "p50": 1, "p95": 1, "max": 1}},
            "topic_subsets": {"total": 1, "stale": 0, "stale_rate": 0.0, "age_minutes": {"min": 1, "p50": 1, "p95": 1, "max": 1}, "stale_after_minutes": 120},
            "persona_subsets": {"total": 1, "stale": 0, "stale_rate": 0.0, "age_minutes": {"min": 1, "p50": 1, "p95": 1, "max": 1}, "stale_after_minutes": 180},
        },
    )

    summary = operations.run_subset_refresh(topics=["Union Budget 2026"], profile_names=["cfo_profile"])

    assert summary["run_type"] == "subset_refresh"
    assert summary["status"] == "success"
    rows = operations.load_recent_run_summaries(limit=10)
    assert rows, "Expected persisted run summaries"
    assert rows[-1]["run_type"] == "subset_refresh"
