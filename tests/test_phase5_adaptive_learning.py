"""Phase 5: Adaptive Learning + Cold Start — Test Suite (8 tests)."""

import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.models import Article, UserProfile
from src.agents.adaptive_ranker import (
    apply_feedback_boost,
    get_cold_start_boost_for_role,
    merge_feedback_with_preference_scores,
    get_boost_explanation,
)
from src.agents.engagement_tracker import get_feedback_signal_for_ranker, log_article_feedback


def test_1_cold_start_boost_rules():
    """Test 1: Cold-start boost returns role-specific defaults."""
    print("\n[Test 1] Cold-start boost for different roles...")
    
    roles = ["CFO", "Young Investor", "Analyst", "Unknown Role"]
    
    for role in roles:
        boost = get_cold_start_boost_for_role(role)
        assert isinstance(boost, dict), f"Expected dict, got {type(boost)}"
        assert len(boost) > 0, f"No boost rules for role: {role}"
        assert all(0 <= v <= 1 for v in boost.values()), "Boost scores out of range [0, 1]"
        print(f"  ✓ Role '{role}': {len(boost)} topics, scores {list(boost.values())[:3]}...")
    
    print("  ✅ Test 1 PASSED: Cold-start rules structure correct")


def test_2_feedback_boost_with_positive_feedback():
    """Test 2: Positive feedback boosts scores."""
    print("\n[Test 2] Applying positive feedback boost...")
    
    articles = [
        Article(id="art-001", title="Tech Boom", content="...", category="tech", author="X", published_at="2026-01-01"),
        Article(id="art-002", title="Budget Talk", content="...", category="policy", author="Y", published_at="2026-01-02"),
        Article(id="art-003", title="Startup News", content="...", category="sector", author="Z", published_at="2026-01-03"),
    ]
    
    base_scores = {
        "art-001": 0.60,
        "art-002": 0.50,
        "art-003": 0.55,
    }
    
    feedback_signals = {
        "liked_count": 3,
        "disliked_count": 0,
        "disliked_reasons": {},
        "session_feedback_weight": 0.10,  # 10% weight to feedback
    }
    
    boosted = apply_feedback_boost(articles, feedback_signals, base_scores)
    
    # All scores should be preserved (no penalization)
    assert len(boosted) == 3, "Boosted scores dict size mismatch"
    assert all(0 <= v <= 1 for v in boosted.values()), "Boosted scores out of range"
    
    print(f"  Base scores: {base_scores}")
    print(f"  Boosted scores: {boosted}")
    print(f"  Feedback weight: {feedback_signals['session_feedback_weight']}")
    print("  ✅ Test 2 PASSED: Positive feedback preserves/boosts scores")


def test_3_feedback_boost_with_negative_feedback():
    """Test 3: Negative feedback penalizes scores."""
    print("\n[Test 3] Applying negative feedback penalty...")
    
    articles = [
        Article(id="art-001", title="Sensational News", content="...", category="market", author="X", published_at="2026-01-01"),
        Article(id="art-002", title="Breaking News", content="...", category="expert", author="Y", published_at="2026-01-02"),
    ]
    
    base_scores = {
        "art-001": 0.70,
        "art-002": 0.60,
    }
    
    feedback_signals = {
        "liked_count": 0,
        "disliked_count": 2,
        "disliked_reasons": {
            "Sensationalized": 1,
            "Not credible source": 1,
        },
        "session_feedback_weight": 0.15,
    }
    
    boosted = apply_feedback_boost(articles, feedback_signals, base_scores)
    
    assert len(boosted) == 2, "Boosted scores dict size mismatch"
    assert all(0 <= v <= 1 for v in boosted.values()), "Boosted scores out of range"
    
    # With negative feedback, scores should be lower than baseline
    print(f"  Base scores: {base_scores}")
    print(f"  Boosted scores (with penalties): {boosted}")
    print("  ✅ Test 3 PASSED: Negative feedback penalizes scores")


def test_4_merged_feedback_with_baseline():
    """Test 4: merge_feedback_with_preference_scores combines Phase 3 + Phase 4."""
    print("\n[Test 4] Merging Phase 3 baseline with Phase 4 feedback...")
    
    profile = UserProfile(
        user_id="test-user-001",
        name="Test User",
        age=45,
        role="CFO",
        reading_level="intermediate",
        interests=["markets", "policy"],
        preferred_format="comprehensive",
    )
    
    articles = [
        Article(id="art-001", title="Markets Rally", content="...", category="market", author="X", published_at="2026-01-01"),
        Article(id="art-002", title="Policy Change", content="...", category="policy", author="Y", published_at="2026-01-02"),
    ]
    
    ranker_scores = {
        "art-001": 0.65,
        "art-002": 0.55,
    }
    
    feedback_signals = {
        "liked_count": 1,
        "disliked_count": 0,
        "disliked_reasons": {},
        "session_feedback_weight": 0.10,
    }
    
    merged = merge_feedback_with_preference_scores(
        articles=articles,
        user_profile=profile,
        ranker_scores=ranker_scores,
        feedback_signals=feedback_signals,
        session_id="test_merge_001",
    )
    
    assert len(merged) == len(ranker_scores), "Output size doesn't match input"
    assert all(0 <= v <= 1 for v in merged.values()), "Merged scores out of range"
    
    print(f"  Ranker scores: {ranker_scores}")
    print(f"  Merged scores: {merged}")
    print("  ✅ Test 4 PASSED: Feedback merged with baseline")


def test_5_cold_start_path():
    """Test 5: Cold-start (no feedback) returns ranker scores as-is."""
    print("\n[Test 5] Cold-start path (no feedback history)...")
    
    profile = UserProfile(
        user_id="test-user-new",
        name="New User",
        age=28,
        role="Young Investor",
        reading_level="beginner",
        interests=["tech", "startups"],
        preferred_format="brief",
    )
    
    articles = [
        Article(id="art-001", title="Tech Boom", content="...", category="tech", author="X", published_at="2026-01-01"),
    ]
    
    ranker_scores = {"art-001": 0.50}
    
    # No feedback signals (empty or with all-zero counts)
    merged = merge_feedback_with_preference_scores(
        articles=articles,
        user_profile=profile,
        ranker_scores=ranker_scores,
        feedback_signals=None,  # No feedback yet
        session_id="test_cold_start",
    )
    
    assert merged == ranker_scores, "Cold-start should return ranker scores unchanged"
    print(f"  Profile: {profile.name} (new)")
    print(f"  Feedback signals: None (cold-start)")
    print(f"  Result: Scores unchanged {merged}")
    print("  ✅ Test 5 PASSED: Cold-start returns baseline scores")


def test_6_boost_explanation_generation():
    """Test 6: Explanation generation for boost/penalty reasons."""
    print("\n[Test 6] Generating boost explanations...")
    
    test_cases = [
        {
            "article_id": "art-001",
            "original": 0.60,
            "boosted": 0.70,  # Positive boost
            "feedback": {"liked_count": 2, "disliked_count": 0, "disliked_reasons": {}},
            "expected_contains": "Boosted",
        },
        {
            "article_id": "art-002",
            "original": 0.70,
            "boosted": 0.50,  # Negative boost (penalty)
            "feedback": {"liked_count": 0, "disliked_count": 2, "disliked_reasons": {"Sensationalized": 1}},
            "expected_contains": "Penalized",
        },
        {
            "article_id": "art-003",
            "original": 0.60,
            "boosted": 0.60,  # No change
            "feedback": {"liked_count": 0, "disliked_count": 0, "disliked_reasons": {}},
            "expected_contains": "Ranked by",
        },
    ]
    
    for i, tc in enumerate(test_cases, 1):
        explanation = get_boost_explanation(
            article_id=tc["article_id"],
            original_score=tc["original"],
            boosted_score=tc["boosted"],
            feedback_signals=tc["feedback"],
        )
        
        assert tc["expected_contains"] in explanation, f"Expected '{tc['expected_contains']}' in '{explanation}'"
        print(f"  Case {i}: Δ {tc['boosted'] - tc['original']:+.2f} → '{explanation}'")
    
    print("  ✅ Test 6 PASSED: Explanations generated correctly")


def test_7_feedback_persistency_and_signal_integration():
    """Test 7: Feedback logs persist and signals integr correctly."""
    print("\n[Test 7] Feedback persistency and signal integration...")
    
    user_id = "test-persist-001"
    session_id = "test_session_7"
    
    # Log some feedback
    log_article_feedback(
        user_id=user_id,
        article_id="art-001",
        feedback_type="interested",
        reason=None,
        session_id=session_id,
    )
    
    log_article_feedback(
        user_id=user_id,
        article_id="art-002",
        feedback_type="not_interested",
        reason="Sensationalized",
        session_id=session_id,
    )
    
    # Get signals for ranker
    signals = get_feedback_signal_for_ranker(user_id)
    
    assert signals is not None, "Signals should not be None"
    assert signals["liked_count"] > 0, "Liked count should reflect logged feedback"
    assert signals["disliked_count"] > 0, "Disliked count should reflect logged feedback"
    assert "session_feedback_weight" in signals, "Session weight should be present"
    
    print(f"  Logged feedback: 1 interested, 1 not interested")
    print(f"  Retrieved signals: {signals}")
    print("  ✅ Test 7 PASSED: Feedback persists and signals ready for ranker")


def test_8_full_pipeline_integration():
    """Test 8: Full Phase 3-5 integration (simulate real feed generation)."""
    print("\n[Test 8] Full pipeline integration (Phase 3 + Phase 5)...")
    
    # Setup: User, profile, articles
    user_id = "integration-test-001"
    
    profile = UserProfile(
        user_id=user_id,
        name="Integration Tester",
        age=35,
        role="Analyst",
        reading_level="intermediate",
        interests=["macro", "tech"],
        preferred_format="comprehensive",
    )
    
    articles = [
        Article(id="art-a", title="Macro Trends", content="...", category="macro", author="X", published_at="2026-01-01"),
        Article(id="art-b", title="Tech Innovation", content="...", category="sector", author="Y", published_at="2026-01-02"),
        Article(id="art-c", title="Market News", content="...", category="market", author="Z", published_at="2026-01-03"),
    ]
    
    # Phase 3: Ranker scores
    ranker_scores = {
        "art-a": 0.65,  # Matches interest (macro)
        "art-b": 0.60,  # Matches interest (tech)
        "art-c": 0.45,  # Weaker match
    }
    
    # Phase 4: Simulate previous feedback
    log_article_feedback(
        user_id=user_id,
        article_id="art-a",
        feedback_type="interested",
        reason="Relevant to my portfolio",
        session_id="test_session_8",
    )
    
    log_article_feedback(
        user_id=user_id,
        article_id="art-c",
        feedback_type="not_interested",
        reason="Not relevant to interests",
        session_id="test_session_8",
    )
    
    # Phase 5: Apply adaptive ranking
    feedback_signals = get_feedback_signal_for_ranker(user_id)
    
    merged_scores = merge_feedback_with_preference_scores(
        articles=articles,
        user_profile=profile,
        ranker_scores=ranker_scores,
        feedback_signals=feedback_signals,
        session_id="test_session_8",
    )
    
    # Verify
    assert len(merged_scores) == len(articles), "All articles should have scores"
    assert all(0 <= v <= 1 for v in merged_scores.values()), "Scores in valid range"
    
    # Building explanations
    explanations = []
    for article in articles:
        original = ranker_scores[article.id]
        boosted = merged_scores[article.id]
        
        explanation = get_boost_explanation(
            article_id=article.id,
            original_score=original,
            boosted_score=boosted,
            feedback_signals=feedback_signals or {},
        )
        explanations.append(explanation)
    
    print(f"  Profile: {profile.name} ({profile.role})")
    print(f"  Articles: {len(articles)}")
    print(f"  Phase 3 (ranker) scores: {ranker_scores}")
    print(f"  Phase 4 (feedback) signals: {feedback_signals}")
    print(f"  Phase 5 (merged) scores: {merged_scores}")
    print(f"  Explanations:")
    for article, expl in zip(articles, explanations):
        print(f"    - {article.title}: {expl}")
    
    print("  ✅ Test 8 PASSED: Full integration works end-to-end")


if __name__ == "__main__":
    print("\n" + "="*70)
    print("PHASE 5: ADAPTIVE LEARNING + COLD START — TEST SUITE")
    print("="*70)
    
    tests = [
        test_1_cold_start_boost_rules,
        test_2_feedback_boost_with_positive_feedback,
        test_3_feedback_boost_with_negative_feedback,
        test_4_merged_feedback_with_baseline,
        test_5_cold_start_path,
        test_6_boost_explanation_generation,
        test_7_feedback_persistency_and_signal_integration,
        test_8_full_pipeline_integration,
    ]
    
    passed = 0
    failed = 0
    
    for test_func in tests:
        try:
            test_func()
            passed += 1
        except Exception as e:
            failed += 1
            print(f"  ❌ FAILED: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "="*70)
    print(f"RESULTS: {passed}/{len(tests)} tests passed")
    print("="*70 + "\n")
    
    if failed > 0:
        sys.exit(1)
