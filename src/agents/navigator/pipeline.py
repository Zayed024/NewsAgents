"""News Navigator pipeline — orchestrates all agents sequentially + engagement tracking."""

from src.models import (
    Article, EntityMap, AngleCluster, SynthesisEntry,
    NavigatorBriefingResponse, NavigatorQueryResponse, AuditEntry,
    TopicRetrievalContract, RetrievalFreshness,
)
from src.audit import get_audit_trail, clear_audit_trail, log_agent_step, AuditTimer
from src.config import is_retrieval_contracts_enabled
from src.agents.navigator.ingestor import ingest_articles
from src.agents.navigator.entity_extractor import extract_entities
from src.agents.navigator.angle_clusterer import cluster_angles
from src.agents.navigator.synthesizer import synthesize_angles
from src.agents.navigator.briefing_builder import build_interactive_briefing
from src.agents.navigator.topic_relevance import select_relevant_articles_for_topic
from src.agents.navigator.entity_graph import build_entity_navigation_map
from src.agents.navigator.query_responder import respond_to_query, clear_query_history
from src.agents.navigator.chroma_store import index_articles, search_articles
from src.agents.navigator.contradiction_detector import detect_contradictions
from src.agents.navigator.blind_spot_detector import detect_blind_spots
from src.agents.navigator.reading_path import generate_reading_path
from src.agents.engagement_tracker import (
    log_angle_click, log_query, log_session_start,
    get_retuned_angle_order, get_user_interest_vector,
)


# In-memory briefing cache
_briefing_cache: dict[str, dict] = {}


async def run_navigator_pipeline(
    articles: list[Article],
    session_id: str = "default",
    topic: str = "",
    enforce_topic_coverage: bool = False,
    user_id: str = "anonymous",
) -> NavigatorBriefingResponse:
    """Run the full News Navigator pipeline.

    Steps:
    1. TopicRelevance — filter articles if enforce_topic_coverage (Flash)
    2. ArticleIngestor — parse and extract metadata (Flash)
    3. EntityExtractor — build entity-to-article index (Flash)
    4. AngleClustering — cluster into 5-7 angles (Pro)
    5. SynthesisEngine — synthesize each angle (Pro)
    6. BriefingBuilder — build unified deep briefing (Pro)
    7. ChromaDB indexing — embed articles for follow-up Q&A
    8. EngagementTracker — retune angle order from history

    Args:
        articles: List of raw articles
        session_id: Session ID for audit and caching
        topic: Topic for relevance filtering
        enforce_topic_coverage: Whether to filter by topic
        user_id: User ID for engagement tracking

    Returns:
        NavigatorBriefingResponse with angles, syntheses, and audit trail
    """
    clear_audit_trail(session_id)
    clear_query_history(session_id)
    log_session_start(user_id, session_id)

    coverage_report = TopicRetrievalContract(
        topic=topic,
        total_articles_scanned=len(articles),
        relevant_articles_count=len(articles),
        relevant_article_ids=[a.id for a in articles],
        excluded_article_ids=[],
        coverage_mode="all_articles",
        inclusion_reasons={a.id: "all_articles_mode" for a in articles},
        exclusion_reasons={},
        freshness=RetrievalFreshness(subset_reused=False),
    )
    working_articles = articles

    with AuditTimer() as total_timer:
        if enforce_topic_coverage and topic.strip():
            working_articles, coverage_report = await select_relevant_articles_for_topic(
                topic,
                articles,
                session_id,
            )

        # Step 1: Ingest articles
        article_metadata = await ingest_articles(working_articles, session_id)

        # Step 2: Extract entities
        entity_map = await extract_entities(article_metadata, session_id)

        # Step 3: Cluster into angles
        angles = await cluster_angles(working_articles, article_metadata, entity_map, session_id)

        # Step 4: Synthesize each angle
        syntheses = await synthesize_angles(angles, working_articles, session_id)

        # Step 4.5: Build entity-driven navigation graph
        entity_navigation = build_entity_navigation_map(
            entity_map=entity_map,
            angles=angles,
            session_id=session_id,
        )

        # Step 5: Build single deep briefing document
        deep_briefing_markdown, suggested_questions = await build_interactive_briefing(
            angles,
            syntheses,
            session_id,
        )

        # Step 5.5: Detect contradictions across syntheses
        contradictions = await detect_contradictions(syntheses, working_articles, session_id)

        # Step 5.6: Detect coverage blind spots
        blind_spots = await detect_blind_spots(
            working_articles, angles,
            topic=topic or "Union Budget 2026",
            session_id=session_id,
        )

        # Step 5.7: Generate optimal reading path
        reading_path = await generate_reading_path(
            working_articles, syntheses, session_id=session_id,
        )

        # Step 6: Index articles in ChromaDB for semantic search
        try:
            indexed = index_articles(articles)
            log_agent_step(
                agent_name="ChromaDB",
                action="index_articles",
                model_used="sentence-transformers (local)",
                input_summary=f"{len(articles)} articles",
                output_summary=f"{indexed} newly indexed",
                latency_ms=0,
                session_id=session_id,
            )
        except Exception:
            pass  # ChromaDB is optional — don't fail the pipeline

        # Step 7: Retune angle order based on engagement history
        angle_names = [a.angle_name for a in angles]
        retuned_order = get_retuned_angle_order(user_id, angle_names)
        if retuned_order != angle_names:
            angle_map = {a.angle_name: a for a in angles}
            angles = [angle_map[name] for name in retuned_order if name in angle_map]
            synth_map = {s.angle_name: s for s in syntheses}
            syntheses = [synth_map[name] for name in retuned_order if name in synth_map]

            log_agent_step(
                agent_name="EngagementTracker",
                action="retune_angle_order",
                model_used="local (no LLM)",
                input_summary=f"User: {user_id}, original: {angle_names[:3]}",
                output_summary=f"Retuned: {retuned_order[:3]}",
                latency_ms=0,
                session_id=session_id,
            )

    # Log overall pipeline completion
    log_agent_step(
        agent_name="NavigatorPipeline",
        action="full_pipeline",
        model_used="multi-model",
        input_summary=f"{len(working_articles)} articles",
        output_summary=f"{len(angles)} angles, {len(syntheses)} syntheses",
        latency_ms=total_timer.elapsed_ms,
        session_id=session_id,
    )

    # Cache for query follow-ups
    _briefing_cache[session_id] = {
        "articles": working_articles,
        "syntheses": syntheses,
        "angles": angles,
        "entity_map": entity_map,
        "entity_navigation": entity_navigation,
        "deep_briefing_markdown": deep_briefing_markdown,
        "suggested_questions": suggested_questions,
        "coverage_report": coverage_report,
        "contradictions": contradictions,
        "blind_spots": blind_spots,
        "reading_path": reading_path,
        "user_id": user_id,
    }

    return NavigatorBriefingResponse(
        briefing_id=session_id,
        topic=coverage_report.topic,
        total_articles_scanned=coverage_report.total_articles_scanned,
        relevant_articles_count=coverage_report.relevant_articles_count,
        relevant_article_ids=coverage_report.relevant_article_ids,
        excluded_article_ids=coverage_report.excluded_article_ids,
        coverage_mode=coverage_report.coverage_mode,
        inclusion_reasons=coverage_report.inclusion_reasons,
        exclusion_reasons=coverage_report.exclusion_reasons,
        retrieval_contract=coverage_report if is_retrieval_contracts_enabled() else None,
        angles=angles,
        syntheses=syntheses,
        deep_briefing_markdown=deep_briefing_markdown,
        suggested_questions=suggested_questions,
        entity_navigation=entity_navigation,
        entity_map=entity_map,
        audit_trail=get_audit_trail(session_id),
    )


async def handle_query(
    question: str,
    session_id: str = "default",
) -> NavigatorQueryResponse:
    """Handle a follow-up question on an existing briefing.

    Uses ChromaDB for semantic article retrieval and logs engagement.

    Args:
        question: User's question
        session_id: Session ID to look up cached briefing

    Returns:
        NavigatorQueryResponse with answer and audit trail
    """
    cache = _briefing_cache.get(session_id)
    if not cache:
        return NavigatorQueryResponse(
            answer="No briefing found. Please generate a briefing first.",
            sources=[],
            angle="none",
            audit_trail=[],
        )

    # Use ChromaDB to find most relevant articles for this question
    try:
        relevant = search_articles(question, n_results=5)
        if relevant:
            log_agent_step(
                agent_name="ChromaDB",
                action="semantic_search",
                model_used="sentence-transformers (local)",
                input_summary=f"Query: {question[:80]}",
                output_summary=f"Top match: {relevant[0]['title'][:60]}",
                latency_ms=0,
                session_id=session_id,
            )
    except Exception:
        relevant = []

    result = await respond_to_query(
        question=question,
        syntheses=cache["syntheses"],
        articles=cache["articles"],
        session_id=session_id,
    )

    # Log engagement signal
    user_id = cache.get("user_id", "anonymous")
    log_query(user_id, question, result.angle, session_id)

    return NavigatorQueryResponse(
        answer=result.answer,
        sources=result.sources,
        angle=result.angle,
        audit_trail=get_audit_trail(session_id),
    )
