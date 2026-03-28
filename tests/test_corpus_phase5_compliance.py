import asyncio
from datetime import datetime, timezone

from src.models import Article
from src.agents.navigator.topic_relevance import select_relevant_articles_for_topic
from src.tools.corpus import compliance
from src.tools.corpus import operations


def _article(article_id: str, title: str, content: str) -> Article:
    return Article(
        id=article_id,
        title=title,
        published_at=datetime.now(timezone.utc).isoformat(),
        category="economy",
        content=content,
        author="ET Staff",
        tags=["economy"],
        url=f"https://economictimes.com/{article_id}",
    )


def test_crawl_preflight_denies_out_of_policy():
    preflight = compliance.validate_crawl_preflight(
        topic="Union Budget 2026",
        max_pages=999,
        max_depth=10,
    )

    assert preflight["allowed"] is False
    assert "max_pages_out_of_policy" in preflight["reasons"]
    assert "max_depth_out_of_policy" in preflight["reasons"]


def test_subset_refresh_denied_with_kill_switch(tmp_path, monkeypatch):
    monkeypatch.setattr(compliance, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(operations, "DATA_DIR", str(tmp_path))
    monkeypatch.setenv("CORPUS_KILL_SWITCH", "1")

    summary = operations.run_subset_refresh(topics=["Union Budget 2026"], profile_names=["cfo_profile"])

    assert summary["status"] == "denied_policy"
    assert summary["preflight"]["allowed"] is False

    snapshots = compliance.load_compliance_snapshots(limit=10)
    assert snapshots, "Expected compliance snapshots to be persisted"
    assert snapshots[-1]["operation"] == "subset_refresh"


def test_retrieval_kill_switch_falls_back_all_articles(tmp_path, monkeypatch):
    monkeypatch.setattr(compliance, "DATA_DIR", str(tmp_path))
    monkeypatch.setenv("CORPUS_KILL_SWITCH", "1")

    articles = [
        _article("a1", "Budget update", "Fiscal deficit details"),
        _article("a2", "Markets update", "Equity movement details"),
    ]

    selected, report = asyncio.run(
        select_relevant_articles_for_topic(
            topic="Union Budget 2026",
            articles=articles,
            session_id="test-phase5",
        )
    )

    assert len(selected) == 2
    assert report.coverage_mode == "compliance_kill_switch_all_articles"
    assert report.relevant_articles_count == 2


def test_compliance_report_aggregates_decisions(tmp_path, monkeypatch):
    monkeypatch.setattr(compliance, "DATA_DIR", str(tmp_path))

    allow_pf = {"allowed": True, "reasons": ["policy_pass"]}
    deny_pf = {"allowed": False, "reasons": ["kill_switch_enabled"]}

    compliance.write_compliance_snapshot("crawl_refresh", allow_pf, "allowed", {"topic": "budget"})
    compliance.write_compliance_snapshot("subset_refresh", deny_pf, "denied_policy", {"topics": ["budget"]})

    report = compliance.generate_compliance_report(limit=50, persist=False)

    assert report["rows_analyzed"] >= 2
    assert report["decision_counts"].get("allowed", 0) >= 1
    assert report["decision_counts"].get("denied_policy", 0) >= 1
    assert report["denied_by_reason"].get("kill_switch_enabled", 0) >= 1
