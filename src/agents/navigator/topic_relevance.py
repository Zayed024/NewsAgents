"""Topic relevance selector for strict article-coverage briefing mode."""

from datetime import datetime, timezone

from src.audit import AuditTimer, log_agent_step
from src.models import Article, RetrievalFreshness, TopicRetrievalContract
from src.tools.corpus.relevance import hybrid_rank_articles, llm_rerank_top
from src.tools.corpus.subsets import materialize_topic_subset, load_topic_subset
from src.tools.corpus.compliance import (
    is_corpus_kill_switch_enabled,
    validate_retrieval_preflight,
    write_compliance_snapshot,
)


async def select_relevant_articles_for_topic(
    topic: str,
    articles: list[Article],
    session_id: str = "default",
    freshness_max_minutes: int = 120,
) -> tuple[list[Article], TopicRetrievalContract]:
    """Scan full corpus and return topic-relevant articles with coverage report.
    
    Reuses fresh cached subset if available to avoid expensive hybrid ranking + LLM reranking.
    Falls back to full pipeline if subset is stale or missing.
    """
    if not topic.strip():
        all_ids = [a.id for a in articles]
        return articles, TopicRetrievalContract(
            topic="",
            total_articles_scanned=len(articles),
            relevant_articles_count=len(articles),
            relevant_article_ids=all_ids,
            excluded_article_ids=[],
            coverage_mode="all_articles",
            inclusion_reasons={aid: "all_articles_mode" for aid in all_ids},
            exclusion_reasons={},
            freshness=RetrievalFreshness(
                subset_reused=False,
                freshness_max_minutes=freshness_max_minutes,
            ),
        )

    preflight = validate_retrieval_preflight(topic=topic)
    if (not preflight.get("allowed", False)) or is_corpus_kill_switch_enabled():
        all_ids = [a.id for a in articles]
        snapshot = write_compliance_snapshot(
            operation="retrieval_topic_relevance",
            preflight=preflight,
            decision="blocked_kill_switch" if is_corpus_kill_switch_enabled() else "denied_policy",
            metadata={"topic": topic, "scanned": len(articles)},
        )

        log_agent_step(
            agent_name="TopicRelevanceSelector",
            action="compliance_block_or_kill_switch",
            model_used="policy",
            input_summary=f"topic={topic}, scanned={len(articles)}",
            output_summary=f"all_articles_fallback={len(all_ids)}",
            latency_ms=0,
            session_id=session_id,
            status="fallback",
            error_detail=str(snapshot.get("decision", "policy")),
        )

        return articles, TopicRetrievalContract(
            topic=topic,
            total_articles_scanned=len(articles),
            relevant_articles_count=len(articles),
            relevant_article_ids=all_ids,
            excluded_article_ids=[],
            coverage_mode="compliance_kill_switch_all_articles",
            inclusion_reasons={aid: "compliance_fallback_all_articles" for aid in all_ids},
            exclusion_reasons={},
            freshness=RetrievalFreshness(
                subset_reused=False,
                freshness_max_minutes=freshness_max_minutes,
            ),
        )

    # Check for fresh cached subset first (shortcut optimization).
    cached_subset = load_topic_subset(topic, max_age_minutes=freshness_max_minutes)
    if cached_subset:
        selected_ids_set = set(cached_subset.get("selected_ids", []))
        if selected_ids_set:
            selected = [a for a in articles if a.id in selected_ids_set]
            excluded = [a.id for a in articles if a.id not in selected_ids_set]
            subset_updated_at = str(cached_subset.get("updated_at", "")).strip() or None
            subset_age_minutes = None
            if subset_updated_at:
                try:
                    ts = datetime.fromisoformat(subset_updated_at.replace("Z", "+00:00"))
                    if ts.tzinfo is None:
                        ts = ts.replace(tzinfo=timezone.utc)
                    subset_age_minutes = round(
                        (datetime.now(timezone.utc) - ts).total_seconds() / 60.0,
                        2,
                    )
                except Exception:
                    subset_age_minutes = None
            
            log_agent_step(
                agent_name="TopicRelevanceSelector",
                action="reuse_fresh_subset_shortcut",
                model_used="cache",
                input_summary=f"topic={topic}, scanned={len(articles)}",
                output_summary=f"relevant={len(selected)}, excluded={len(excluded)}, reused_subset=True",
                latency_ms=0,
                session_id=session_id,
                status="success",
            )
            
            report = TopicRetrievalContract(
                topic=topic,
                total_articles_scanned=len(articles),
                relevant_articles_count=len(selected),
                relevant_article_ids=[a.id for a in selected],
                excluded_article_ids=excluded,
                coverage_mode=str(cached_subset.get("coverage_mode", "cached_hybrid")),
                inclusion_reasons=dict(cached_subset.get("inclusion_reasons", {}) or {}),
                exclusion_reasons=dict(cached_subset.get("exclusion_reasons", {}) or {}),
                freshness=RetrievalFreshness(
                    subset_reused=True,
                    freshness_max_minutes=freshness_max_minutes,
                    subset_age_minutes=subset_age_minutes,
                    subset_updated_at=subset_updated_at,
                ),
            )
            
            return selected, report

    # Full pipeline: hybrid ranking + LLM rerank (cache miss or stale).
    with AuditTimer() as timer:
        ranked = hybrid_rank_articles(topic=topic, articles=articles, top_k=min(100, len(articles)))
        selected_ids, llm_reasons, mode = await llm_rerank_top(
            topic=topic,
            ranked_rows=ranked,
            session_id=session_id,
            top_k=min(18, len(ranked)),
            final_k=min(max(8, len(ranked) // 2), len(ranked)),
        )

        selected_ids_set = set(selected_ids)
        if not selected_ids_set:
            selected_ids_set = {a.id for a in articles}
            mode = "hybrid_fallback_all"

        ranked_by_id = {row["article_id"]: row for row in ranked}
        inclusion_reasons = {
            aid: llm_reasons.get(aid, ranked_by_id.get(aid, {}).get("base_reason", "selected"))
            for aid in selected_ids_set
        }
        exclusion_reasons = {}
        for a in articles:
            if a.id in selected_ids_set:
                continue
            row = ranked_by_id.get(a.id)
            if row:
                exclusion_reasons[a.id] = (
                    f"not_selected_after_rerank combined={row['combined_score']}; "
                    f"lexical={row['bm25_score']}; semantic={row['embedding_score']}"
                )
            else:
                exclusion_reasons[a.id] = "not_in_top_hybrid_candidates"

        selected = [a for a in articles if a.id in selected_ids_set]
        excluded = [a.id for a in articles if a.id not in selected_ids_set]

        materialize_topic_subset(
            topic=topic,
            selected_ids=[a.id for a in selected],
            inclusion_reasons=inclusion_reasons,
            exclusion_reasons=exclusion_reasons,
            coverage_mode=mode,
            total_scanned=len(articles),
        )

    log_agent_step(
        agent_name="TopicRelevanceSelector",
        action="scan_all_articles_for_topic",
        model_used="flash",
        input_summary=f"topic={topic}, scanned={len(articles)}",
        output_summary=f"relevant={len(selected)}, excluded={len(excluded)}, subset_reused=False",
        latency_ms=timer.elapsed_ms,
        status="success",
        session_id=session_id,
    )

    report = TopicRetrievalContract(
        topic=topic,
        total_articles_scanned=len(articles),
        relevant_articles_count=len(selected),
        relevant_article_ids=[a.id for a in selected],
        excluded_article_ids=excluded,
        coverage_mode=mode,
        inclusion_reasons=inclusion_reasons,
        exclusion_reasons=exclusion_reasons,
        freshness=RetrievalFreshness(
            subset_reused=False,
            freshness_max_minutes=freshness_max_minutes,
        ),
    )

    return selected, report
