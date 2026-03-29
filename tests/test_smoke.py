"""Smoke tests for all 3 pipelines — verifies imports, data loading, and basic functionality."""

import sys
import os
import asyncio
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_all_imports():
    """Verify all modules import without error."""
    from src.config import GEMINI_FLASH, GEMINI_PRO, get_genai_client
    from src.models import Article, UserProfile, AuditEntry, VideoScene, VideoScenePlan
    from src.model_router import get_model, get_routing_summary
    from src.audit import log_agent_step, AuditTimer, get_audit_trail, get_session_cost_summary
    from src.llm import call_llm, parse_json_response

    # Navigator agents
    from src.agents.navigator.ingestor import ingest_articles
    from src.agents.navigator.entity_extractor import extract_entities
    from src.agents.navigator.angle_clusterer import cluster_angles
    from src.agents.navigator.synthesizer import synthesize_angles
    from src.agents.navigator.query_responder import respond_to_query
    from src.agents.navigator.pipeline import run_navigator_pipeline, handle_query
    from src.agents.navigator.chroma_store import index_articles, search_articles

    # Video agents
    from src.agents.video.breaking_ingestor import extract_breaking_facts
    from src.agents.video.script_writer import write_script
    from src.agents.video.fact_checker import check_facts
    from src.agents.video.scene_planner import plan_scenes
    from src.agents.video.language_validator import validate_and_correct_language
    from src.agents.video.audio_gen import generate_audio, generate_scene_audio
    from src.agents.video.video_composer import compose_video
    from src.agents.video.article_visuals import fetch_article_visuals
    from src.agents.video.pipeline import run_video_pipeline

    # Persona feed agents
    from src.agents.persona_feed.profiler import analyze_profile
    from src.agents.persona_feed.ranker import rank_articles
    from src.agents.persona_feed.adapter import adapt_articles
    from src.agents.persona_feed.pipeline import run_feed_comparison

    # Engagement tracker
    from src.agents.engagement_tracker import (
        log_angle_click, log_query, log_session_start,
        get_retuned_angle_order, get_user_interest_vector, get_engagement_summary,
    )

    print("ALL IMPORTS OK")


def test_data_loading():
    """Verify all sample data loads correctly."""
    from src.tools.article_loader import (
        load_budget_articles, load_homepage_articles,
        load_breaking_news, load_user_profile,
    )

    budget = load_budget_articles()
    assert len(budget) == 22, f"Expected 22 budget articles, got {len(budget)}"

    homepage = load_homepage_articles()
    assert len(homepage) == 15, f"Expected 15 homepage articles, got {len(homepage)}"

    breaking = load_breaking_news()
    assert breaking.title, "Breaking news title is empty"
    assert len(breaking.content) > 100, "Breaking news content too short"

    cfo = load_user_profile("cfo_profile")
    assert cfo.name == "Rajesh Mehta"
    assert cfo.reading_level == "expert"

    young = load_user_profile("young_investor_profile")
    assert young.name == "Priya Sharma"
    assert young.reading_level == "beginner"

    print("ALL DATA LOADING OK")


def test_model_routing():
    """Verify smart model routing returns correct models."""
    from src.model_router import get_model, get_routing_summary

    assert "flash" in get_model("extraction").lower()
    assert "flash" in get_model("fact_checking").lower()
    summary = get_routing_summary()
    assert "routing_table" in summary
    assert "cost_estimates" in summary

    print("MODEL ROUTING OK")


def test_audit_trail():
    """Verify audit trail with cost tracking works."""
    from src.audit import (
        log_agent_step, get_audit_trail, clear_audit_trail,
        get_session_cost_summary, estimate_tokens, estimate_cost,
    )

    clear_audit_trail("test")
    entry = log_agent_step(
        agent_name="TestAgent",
        action="test_action",
        model_used="gemini-2.0-flash",
        input_summary="Test input " * 20,
        output_summary="Test output " * 10,
        latency_ms=100,
        session_id="test",
    )

    assert entry.estimated_input_tokens > 0
    assert entry.estimated_cost_usd >= 0

    trail = get_audit_trail("test")
    assert len(trail) == 1

    cost = get_session_cost_summary("test")
    assert cost["steps"] == 1
    assert cost["total_cost_usd"] >= 0

    clear_audit_trail("test")
    print("AUDIT TRAIL OK")


def test_engagement_tracker():
    """Verify engagement tracking works."""
    from src.agents.engagement_tracker import (
        log_angle_click, log_query, log_session_start,
        get_retuned_angle_order, get_user_interest_vector,
        get_engagement_summary,
    )

    log_session_start("test_user", "test")
    log_angle_click("test_user", "Macro Impact", "test")
    log_angle_click("test_user", "Macro Impact", "test")
    log_angle_click("test_user", "Sector Winners", "test")
    log_query("test_user", "What about IT?", "Sector Winners", "test")

    # Retuning should put Macro Impact first
    default = ["Sector Winners", "Macro Impact", "Tax Changes"]
    retuned = get_retuned_angle_order("test_user", default)
    assert retuned[0] == "Macro Impact", f"Expected Macro Impact first, got {retuned[0]}"

    interest = get_user_interest_vector("test_user")
    assert interest["engagement_depth"] in ["low", "medium", "high"]
    assert "Macro Impact" in interest["preferred_angles"]

    summary = get_engagement_summary()
    assert summary["total_sessions"] >= 1

    print("ENGAGEMENT TRACKER OK")


def test_chromadb_indexing():
    """Verify ChromaDB article indexing works."""
    from src.agents.navigator.chroma_store import index_articles, search_articles, clear_index
    from src.tools.article_loader import load_budget_articles

    clear_index()
    articles = load_budget_articles()[:5]  # Index just 5 for speed
    indexed = index_articles(articles)
    assert indexed == 5, f"Expected 5 indexed, got {indexed}"

    results = search_articles("fiscal deficit GDP impact", n_results=3)
    assert len(results) > 0, "No search results returned"
    assert "id" in results[0]

    clear_index()
    print("CHROMADB OK")


def test_video_frame_generation():
    """Verify video frame generation with Hindi text."""
    from src.agents.video.video_composer import (
        generate_title_frame, generate_facts_frame,
        generate_chapter_frame, generate_timeline_scene_frame,
    )

    frame = generate_title_frame("टेस्ट शीर्षक")
    assert frame.size == (1280, 720)

    facts = [{"label": "कर्ज़", "value": "₹47,000 करोड़", "context": "14 बैंक"}]
    frame2 = generate_facts_frame(facts)
    assert frame2.size == (1280, 720)

    frame3 = generate_chapter_frame("अध्याय 1", "शीर्षक", "सामग्री", 0, 5)
    assert frame3.size == (1280, 720)

    frame4 = generate_timeline_scene_frame("शुरुआत -> मध्य -> अंत")
    assert frame4.size == (1280, 720)

    print("VIDEO FRAMES OK")


def test_hindi_tts():
    """Verify Hindi TTS generation."""
    from src.agents.video.audio_gen import generate_audio
    from src.config import OUTPUT_DIR

    path = asyncio.get_event_loop().run_until_complete(
        generate_audio("नमस्कार दोस्तों।", output_filename="test_smoke.mp3", session_id="test")
    )
    assert path and os.path.exists(path), "TTS audio not generated"
    assert os.path.getsize(path) > 1000, "TTS audio too small"

    os.remove(path)
    print("HINDI TTS OK")


def test_language_profiles():
    """Verify all 7 language profiles are configured."""
    from src.config import VIDEO_LANGUAGE_PROFILES, get_video_language_profile, get_font_path_for_language

    expected = ["bho", "hi", "kn", "mr", "pa", "ta", "te"]
    for lang in expected:
        profile = get_video_language_profile(lang)
        assert profile["label"], f"Missing label for {lang}"
        assert profile.get("writing_hint"), f"Missing writing_hint for {lang}"

    font = get_font_path_for_language("hi")
    assert os.path.exists(font), f"Hindi font not found at {font}"

    print("LANGUAGE PROFILES OK")


def test_json_parsing():
    """Verify JSON response parsing handles edge cases."""
    from src.llm import parse_json_response

    assert parse_json_response('{"a": 1}') == {"a": 1}
    assert parse_json_response('```json\n{"a": 1}\n```') == {"a": 1}
    assert parse_json_response('```\n[1, 2, 3]\n```') == [1, 2, 3]

    print("JSON PARSING OK")


if __name__ == "__main__":
    tests = [
        test_all_imports,
        test_data_loading,
        test_model_routing,
        test_audit_trail,
        test_engagement_tracker,
        test_chromadb_indexing,
        test_video_frame_generation,
        test_hindi_tts,
        test_language_profiles,
        test_json_parsing,
    ]

    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"FAILED: {test.__name__}: {e}")
            failed += 1

    print(f"\n{'='*50}")
    print(f"Results: {passed} passed, {failed} failed out of {len(tests)}")
    if failed == 0:
        print("ALL SMOKE TESTS PASSED")
    else:
        print("SOME TESTS FAILED")
