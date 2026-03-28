import asyncio

import pytest
from src.models import Article, UserProfile
from src.tools.corpus.relevance import hybrid_rank_articles
from src.tools.corpus.subsets import (
    build_persona_general_subset,
    build_persona_specific_subset,
    materialize_topic_subset,
    load_topic_subset,
)
from src.agents.navigator.topic_relevance import select_relevant_articles_for_topic


def _article(article_id: str, title: str, category: str, content: str, published_at: str) -> Article:
    return Article(
        id=article_id,
        title=title,
        published_at=published_at,
        category=category,
        content=content,
        author="ET Staff",
        tags=[category],
        url=f"https://economictimes.com/{article_id}",
    )


def test_hybrid_rank_prioritizes_topic_matches():
    articles = [
        _article(
            "a1",
            "Budget boosts capex",
            "economy",
            "Union budget increases capex and infrastructure spending significantly.",
            "2026-01-10T00:00:00+00:00",
        ),
        _article(
            "a2",
            "Markets close mixed",
            "markets",
            "Equity benchmark closes mixed amid global cues and sector rotation.",
            "2026-01-11T00:00:00+00:00",
        ),
    ]

    ranked = hybrid_rank_articles("union budget infrastructure", articles, top_k=2)
    assert ranked
    assert ranked[0]["article_id"] == "a1"
    assert ranked[0]["combined_score"] >= ranked[1]["combined_score"]


def test_topic_subset_materialization_roundtrip(tmp_path, monkeypatch):
    from src.tools.corpus import subsets

    monkeypatch.setattr(subsets, "_subset_dir", lambda: str(tmp_path))

    materialize_topic_subset(
        topic="union budget",
        selected_ids=["a1", "a2"],
        inclusion_reasons={"a1": "strong_lexical=0.9", "a2": "semantic_match=0.7"},
        exclusion_reasons={"a3": "not_selected_after_rerank"},
        coverage_mode="hybrid_bm25_embedding_fallback",
        total_scanned=3,
    )

    loaded = load_topic_subset("union budget", max_age_minutes=1000)
    assert loaded is not None
    assert loaded["topic"] == "union budget"
    assert loaded["selected_ids"] == ["a1", "a2"]
    assert loaded["inclusion_reasons"]["a1"]


def test_persona_general_subset_builder_is_bounded_and_reasoned():
    articles = [
        _article("a1", "Econ One", "economy", "c1", "2026-01-11T00:00:00+00:00"),
        _article("a2", "Market One", "markets", "c2", "2026-01-10T00:00:00+00:00"),
        _article("a3", "Tech One", "technology", "c3", "2026-01-09T00:00:00+00:00"),
        _article("a4", "Econ Two", "economy", "c4", "2026-01-08T00:00:00+00:00"),
    ]

    payload = build_persona_general_subset(articles, max_items=3)
    assert len(payload["selected_ids"]) == 3
    assert payload["inclusion_reasons"]


def test_fresh_subset_reuse_shortcut_skips_hybrid_ranking(tmp_path, monkeypatch):
    """Verify that fresh subset shortcut avoids expensive hybrid ranking + LLM rerank."""
    from src.tools.corpus import subsets
    from unittest.mock import patch

    # Setup mock subset directory
    monkeypatch.setattr(subsets, "_subset_dir", lambda: str(tmp_path))

    articles = [
        _article("a1", "Budget boosts capex", "economy", 
                "Union budget increases capex and infrastructure spending significantly.",
                "2026-01-10T00:00:00+00:00"),
        _article("a2", "Markets close mixed", "markets",
                "Equity benchmark closes mixed amid global cues and sector rotation.",
                "2026-01-11T00:00:00+00:00"),
        _article("a3", "Tech merger news", "technology",
                "Two major tech companies announce merger deal.",
                "2026-01-09T00:00:00+00:00"),
    ]

    # Pre-populate a fresh subset
    materialize_topic_subset(
        topic="union budget",
        selected_ids=["a1", "a2"],
        inclusion_reasons={"a1": "strong_lexical=0.9", "a2": "semantic_match=0.7"},
        exclusion_reasons={"a3": "not_in_top_candidates"},
        coverage_mode="hybrid_bm25_embedding_llm",
        total_scanned=3,
    )

    # Track if hybrid_rank_articles and llm_rerank_top are called
    with patch("src.agents.navigator.topic_relevance.hybrid_rank_articles") as mock_hybrid:
        with patch("src.agents.navigator.topic_relevance.llm_rerank_top") as mock_llm:
            selected, report = asyncio.run(
                select_relevant_articles_for_topic(
                    topic="union budget",
                    articles=articles,
                    session_id="test",
                    freshness_max_minutes=120,  # Fresh subset within 120 minutes
                )
            )

            # Verify that the shortcut was taken (functions not called)
            assert mock_hybrid.call_count == 0, "hybrid_rank_articles should not be called for fresh subset"
            assert mock_llm.call_count == 0, "llm_rerank_top should not be called for fresh subset"

            # Verify the results match the cached subset
            assert len(selected) == 2
            assert selected[0].id == "a1"
            assert selected[1].id == "a2"
            assert report.freshness.subset_reused is True
            assert report.coverage_mode == "hybrid_bm25_embedding_llm"


def test_stale_subset_triggers_full_pipeline(tmp_path, monkeypatch):
    """Verify that stale subset triggers full hybrid ranking + LLM rerank."""
    from src.tools.corpus import subsets
    from unittest.mock import patch

    # Setup mock subset directory
    monkeypatch.setattr(subsets, "_subset_dir", lambda: str(tmp_path))

    articles = [
        _article("a1", "Budget boosts capex", "economy", 
                "Union budget increases capex and infrastructure spending significantly.",
                "2026-01-10T00:00:00+00:00"),
        _article("a2", "Markets close mixed", "markets",
                "Equity benchmark closes mixed amid global cues and sector rotation.",
                "2026-01-11T00:00:00+00:00"),
    ]

    # Pre-populate a stale subset (max_age_minutes=0 means it's always stale)
    materialize_topic_subset(
        topic="union budget",
        selected_ids=["a1"],
        inclusion_reasons={"a1": "old_selection"},
        exclusion_reasons={"a2": "old_exclusion"},
        coverage_mode="hybrid_bm25_embedding_llm",
        total_scanned=2,
    )

    # Mock the expensive functions
    with patch("src.agents.navigator.topic_relevance.hybrid_rank_articles") as mock_hybrid:
        with patch("src.agents.navigator.topic_relevance.llm_rerank_top") as mock_llm:
            mock_hybrid.return_value = [
                {
                    "article": articles[0],
                    "article_id": "a1",
                    "bm25_score": 0.9,
                    "embedding_score": 0.8,
                    "combined_score": 0.85,
                    "base_reason": "strong_match",
                }
            ]
            mock_llm.return_value = (["a1"], {"a1": "llm_selected"}, "hybrid_bm25_embedding_llm")

            selected, report = asyncio.run(
                select_relevant_articles_for_topic(
                    topic="union budget",
                    articles=articles,
                    session_id="test",
                    freshness_max_minutes=0,  # Force stale (max_age = 0 minutes old = stale)
                )
            )

            # Verify that the full pipeline was triggered
            assert mock_hybrid.call_count == 1, "hybrid_rank_articles should be called for stale subset"
            assert mock_llm.call_count == 1, "llm_rerank_top should be called for stale subset"
            assert report.freshness.subset_reused is False


def test_persona_specific_subset_filters_by_interests():
    """Verify persona-specific subset filters articles by user interests."""
    cfo_profile = UserProfile(
        user_id="user-cfo-001",
        name="Rajesh Mehta",
        age=45,
        role="CFO",
        interests=["macro policy", "fiscal deficit", "taxation", "RBI"],
        reading_level="expert",
        preferred_format="data-dense executive summary",
        portfolio_exposure=["banking", "infrastructure"],
    )

    articles = [
        _article("a1", "RBI monetary policy tightens", "monetary", 
                "RBI announces monetary tightening in latest policy review.",
                "2026-01-11T00:00:00+00:00"),
        _article("a2", "Union Budget 2026 analysis", "budget",
                "Fiscal deficit targets and taxation implications analyzed.",
                "2026-01-10T00:00:00+00:00"),
        _article("a3", "Meme stocks rally on social media", "markets",
                "Retail traders push meme stocks higher amid social media buzz.",
                "2026-01-09T00:00:00+00:00"),
        _article("a4", "Tech startup IPO filing", "technology",
                "New tech startup prepares for IPO with 10-K filing.",
                "2026-01-08T00:00:00+00:00"),
    ]

    payload = build_persona_specific_subset(articles, cfo_profile, max_items=30)
    
    # CFO should match interest in RBI, fiscal deficit, taxation
    assert "a1" in payload["selected_ids"], "RBI policy article should match CFO interests"
    assert "a2" in payload["selected_ids"], "Budget article should match CFO interests"
    
    # CFO is less interested in meme stocks and tech IPOs
    assert len(payload["selected_ids"]) >= 2, "Should have selected at least 2 articles"
    assert payload["inclusion_reasons"]["a1"], "Should have inclusion reason for a1"


def test_persona_specific_subset_young_investor_preferences():
    """Verify young investor persona gets different subset than CFO."""
    young_investor = UserProfile(
        user_id="user-young-001",
        name="Priya Sharma",
        age=24,
        role="Software Developer",
        interests=["SIPs", "tax saving", "tech stocks", "mutual funds", "personal finance"],
        reading_level="beginner",
        preferred_format="explainer with analogies",
    )

    articles = [
        _article("a1", "RBI monetary policy", "monetary",
                "Complex RBI policy analysis.",
                "2026-01-11T00:00:00+00:00"),
        _article("a2", "SIP calculator guide", "finance",
                "How to calculate returns on SIP investments.",
                "2026-01-10T00:00:00+00:00"),
        _article("a3", "Tech stocks investment", "technology",
                "5 tech stocks to consider for long-term growth.",
                "2026-01-09T00:00:00+00:00"),
        _article("a4", "Mutual fund comparison", "finance",
                "Comparing best mutual funds for beginners.",
                "2026-01-08T00:00:00+00:00"),
    ]

    payload = build_persona_specific_subset(articles, young_investor, max_items=30)
    
    # Young investor should prefer personal finance, tech stocks, SIPs
    selected_ids = payload["selected_ids"]
    assert "a2" in selected_ids, "SIP guide should match young investor interests"
    assert "a3" in selected_ids, "Tech stocks should appeal to young investor"
    assert "a4" in selected_ids, "Mutual fund comparison should match young investor"
    
    # Less likely to prioritize complex RBI policy
    assert len(selected_ids) >= 3, "Should select at least 3 relevant articles"


def test_persona_subset_counts_multiple_interest_matches():
    """Verify that articles matching multiple interests are prioritized."""
    persona = UserProfile(
        user_id="user-test",
        name="Test User",
        age=30,
        role="Analyst",
        interests=["banking", "infrastructure", "capex"],
        reading_level="intermediate",
    )

    articles = [
        _article("a1", "Banking infrastructure capex boost", "economy",
                "Banks increase capex for infrastructure projects.",
                "2026-01-11T00:00:00+00:00"),  # Matches all 3 interests
        _article("a2", "Banking sector news", "banking",
                "Banks report quarterly earnings.",
                "2026-01-10T00:00:00+00:00"),  # Matches 1 interest
        _article("a3", "Tech news", "technology",
                "New AI breakthrough announced.",
                "2026-01-09T00:00:00+00:00"),  # No match
    ]

    payload = build_persona_specific_subset(articles, persona, max_items=30)
    
    # All 3 should be in excluded or selection mode should be fallback
    assert "a1" in payload["selected_ids"], "Multi-match article should be selected"
    assert "a2" in payload["selected_ids"], "Single-match article should be selected"
    assert payload["selection_mode"] == "persona_interest_filtered"
