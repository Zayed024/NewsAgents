from src.models import (
    AngleCluster,
    AuditEntry,
    NavigatorBriefingResponse,
    RetrievalFreshness,
    SynthesisEntry,
    TopicRetrievalContract,
)
from src.config import is_retrieval_contracts_enabled


def test_topic_retrieval_contract_shape_and_defaults():
    contract = TopicRetrievalContract(
        topic="Union Budget 2026",
        total_articles_scanned=22,
        relevant_articles_count=10,
        relevant_article_ids=["a1", "a2"],
        excluded_article_ids=["a3"],
        coverage_mode="hybrid_bm25_embedding_llm",
        inclusion_reasons={"a1": "strong_lexical=0.9"},
        exclusion_reasons={"a3": "not_selected_after_rerank"},
        freshness=RetrievalFreshness(
            subset_reused=True,
            freshness_max_minutes=120,
            subset_age_minutes=6.5,
            subset_updated_at="2026-03-29T10:00:00+00:00",
        ),
    )

    assert contract.topic == "Union Budget 2026"
    assert contract.freshness.subset_reused is True
    assert contract.freshness.freshness_max_minutes == 120
    assert contract.coverage_mode.startswith("hybrid")


def test_navigator_response_keeps_legacy_fields_and_contract():
    contract = TopicRetrievalContract(
        topic="Union Budget 2026",
        total_articles_scanned=5,
        relevant_articles_count=3,
        relevant_article_ids=["a1", "a2", "a4"],
        excluded_article_ids=["a3", "a5"],
        coverage_mode="hybrid_bm25_embedding_llm",
        inclusion_reasons={"a1": "strong_lexical=0.8"},
        exclusion_reasons={"a3": "not_selected"},
        freshness=RetrievalFreshness(subset_reused=False, freshness_max_minutes=120),
    )

    response = NavigatorBriefingResponse(
        briefing_id="session-1",
        topic=contract.topic,
        total_articles_scanned=contract.total_articles_scanned,
        relevant_articles_count=contract.relevant_articles_count,
        relevant_article_ids=contract.relevant_article_ids,
        excluded_article_ids=contract.excluded_article_ids,
        coverage_mode=contract.coverage_mode,
        inclusion_reasons=contract.inclusion_reasons,
        exclusion_reasons=contract.exclusion_reasons,
        retrieval_contract=contract,
        angles=[
            AngleCluster(
                angle_name="Macro Impact",
                description="Macro implications",
                article_ids=["a1"],
                key_themes=["fiscal deficit"],
            )
        ],
        syntheses=[
            SynthesisEntry(
                angle_name="Macro Impact",
                synthesis="Summary text",
                source_articles=["a1"],
                key_takeaways=["Takeaway"],
            )
        ],
        audit_trail=[AuditEntry(agent_name="NavigatorPipeline", action="full_pipeline")],
    )

    # Backward compatibility: legacy fields still populated.
    assert response.topic == "Union Budget 2026"
    assert response.relevant_articles_count == 3
    assert response.coverage_mode == "hybrid_bm25_embedding_llm"

    # Phase 3 contract field is available.
    assert response.retrieval_contract is not None
    assert response.retrieval_contract.topic == response.topic
    assert response.retrieval_contract.relevant_article_ids == response.relevant_article_ids


def test_retrieval_contract_serialization_stable_keys():
    contract = TopicRetrievalContract(
        topic="Budget",
        total_articles_scanned=10,
        relevant_articles_count=4,
        relevant_article_ids=["a1", "a2", "a3", "a4"],
        excluded_article_ids=["a5"],
        coverage_mode="hybrid_bm25_embedding_fallback",
        inclusion_reasons={"a1": "selected"},
        exclusion_reasons={"a5": "not_selected"},
    )

    payload = contract.model_dump()
    assert "topic" in payload
    assert "coverage_mode" in payload
    assert "freshness" in payload
    assert "subset_reused" in payload["freshness"]


def test_feature_flag_defaults_enabled(monkeypatch):
    monkeypatch.delenv("RETRIEVAL_CONTRACTS_ENABLED", raising=False)
    assert is_retrieval_contracts_enabled() is True


def test_feature_flag_disable_switch(monkeypatch):
    monkeypatch.setenv("RETRIEVAL_CONTRACTS_ENABLED", "0")
    assert is_retrieval_contracts_enabled() is False


def test_navigator_response_without_contract_still_valid():
    response = NavigatorBriefingResponse(
        briefing_id="session-legacy",
        topic="Budget",
        total_articles_scanned=2,
        relevant_articles_count=2,
        relevant_article_ids=["a1", "a2"],
        excluded_article_ids=[],
        coverage_mode="all_articles",
        inclusion_reasons={"a1": "all_articles_mode", "a2": "all_articles_mode"},
        exclusion_reasons={},
        retrieval_contract=None,
        angles=[
            AngleCluster(
                angle_name="Macro",
                description="Macro view",
                article_ids=["a1"],
                key_themes=["growth"],
            )
        ],
        syntheses=[
            SynthesisEntry(
                angle_name="Macro",
                synthesis="S",
                source_articles=["a1"],
                key_takeaways=["K"],
            )
        ],
    )

    assert response.topic == "Budget"
    assert response.retrieval_contract is None
