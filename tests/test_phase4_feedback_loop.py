"""Test Phase 4: Card Feedback Loop."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
from src.models import UserProfile
from src.agents.engagement_tracker import (
    log_article_feedback,
    get_user_feedback_summary,
    get_feedback_signal_for_ranker,
    should_show_article_again,
    FEEDBACK_REASONS,
)


def test_phase4_article_feedback():
    """Test the complete Phase 4 article feedback loop."""
    
    print("\n=== Phase 4 Card Feedback Loop Test ===\n")
    
    # Create test profile
    profile = UserProfile(
        user_id="user-phase4-test",
        name="Test User Phase 4",
        age=32,
        role="Product Manager",
        interests=["Tech trends", "Startup news"],
        reading_level="intermediate",
        preferred_format="standard",
        portfolio_exposure=["Tech stocks"],
        news_consumption="Daily",
        investing_experience="5-10 years",
    )
    
    # Test 1: Article feedback constants
    print("✅ Test 1: Feedback reasons available")
    print(f"   Interested reasons: {len(FEEDBACK_REASONS['interested'])}")
    print(f"   Not interested reasons: {len(FEEDBACK_REASONS['not_interested'])}")
    
    for reason in FEEDBACK_REASONS["interested"]:
        print(f"     ✓ {reason}")
    
    print("   Not interested:")
    for reason in FEEDBACK_REASONS["not_interested"]:
        print(f"     ✓ {reason}")
    
    assert len(FEEDBACK_REASONS["interested"]) > 0
    assert len(FEEDBACK_REASONS["not_interested"]) > 0
    print("   PASSED\n")
    
    # Test 2: Log interested feedback
    print("✅ Test 2: Log 'interested' feedback")
    
    feedback1 = log_article_feedback(
        user_id=profile.user_id,
        article_id="art-001",
        feedback_type="interested",
        reason=None,
        session_id="test_phase4",
    )
    
    print(f"   Article: {feedback1['article_id']}")
    print(f"   Feedback: {feedback1['feedback_type']}")
    print(f"   Timestamp: {feedback1['timestamp']}")
    
    assert feedback1["feedback_type"] == "interested"
    assert feedback1["article_id"] == "art-001"
    print("   PASSED\n")
    
    # Test 3: Log not interested feedback with reason
    print("✅ Test 3: Log 'not interested' feedback with reason")
    
    reason = "Already know this"
    feedback2 = log_article_feedback(
        user_id=profile.user_id,
        article_id="art-002",
        feedback_type="not_interested",
        reason=reason,
        session_id="test_phase4",
    )
    
    print(f"   Article: {feedback2['article_id']}")
    print(f"   Feedback: {feedback2['feedback_type']}")
    print(f"   Reason: {feedback2['reason']}")
    
    assert feedback2["feedback_type"] == "not_interested"
    assert feedback2["reason"] == reason
    print("   PASSED\n")
    
    # Test 4: Log multiple feedback signals
    print("✅ Test 4: Log multiple feedback signals (simulating session)")
    
    # Simulate user rating multiple articles
    for i in range(5):
        feedback_type = "interested" if i % 2 == 0 else "not_interested"
        reason = None
        if feedback_type == "not_interested":
            reason = FEEDBACK_REASONS["not_interested"][i % len(FEEDBACK_REASONS["not_interested"])]
        
        log_article_feedback(
            user_id=profile.user_id,
            article_id=f"art-{i:03d}",
            feedback_type=feedback_type,
            reason=reason,
            session_id="test_phase4",
        )
        print(f"   Art-{i:03d}: {feedback_type} {f'({reason})' if reason else ''}")
    
    print("   PASSED\n")
    
    # Test 5: Get feedback summary
    print("✅ Test 5: Get feedback summary")
    
    summary = get_user_feedback_summary(profile.user_id)
    
    print(f"   Interested: {summary['interested_count']}")
    print(f"   Not interested: {summary['not_interested_count']}")
    print(f"   Interested reasons: {summary['interested_reasons']}")
    print(f"   Not interested reasons: {summary['not_interested_reasons']}")
    
    assert summary["interested_count"] > 0
    assert summary["not_interested_count"] > 0
    print("   PASSED\n")
    
    # Test 6: Should show article again
    print("✅ Test 6: Should show article again check")
    
    # art-002 was marked not_interested in Test 3
    show_again_002 = should_show_article_again(profile.user_id, "art-002")
    print(f"   Should show art-002 (marked not interested): {show_again_002}")
    assert show_again_002 == False, "art-002 should be marked as not_interested"
    
    # art-000 was marked interested in Test 4
    show_again_000 = should_show_article_again(profile.user_id, "art-000")
    print(f"   Should show art-000 (marked interested): {show_again_000}")
    assert show_again_000 == True, "art-000 was marked interested"
    
    # art-999 was never rated
    show_again_999 = should_show_article_again(profile.user_id, "art-999")
    print(f"   Should show art-999 (never rated): {show_again_999}")
    assert show_again_999 == True, "art-999 was never rated"
    
    print("   PASSED\n")
    
    # Test 7: Get feedback signal for ranker
    print("✅ Test 7: Get feedback signal for ranker (Phase 5 hook)")
    
    signal = get_feedback_signal_for_ranker(profile.user_id)
    
    print(f"   Liked count: {signal['liked_count']}")
    print(f"   Disliked count: {signal['disliked_count']}")
    print(f"   Liked reasons: {signal['liked_reasons']}")
    print(f"   Disliked reasons: {signal['disliked_reasons']}")
    print(f"   Session feedback weight: {signal['session_feedback_weight']:.2f}")
    
    assert "liked_count" in signal
    assert "disliked_count" in signal
    assert "session_feedback_weight" in signal
    print("   PASSED\n")
    
    # Test 8: Persistence check
    print("✅ Test 8: Feedback persistence across function calls")
    
    # Create new summary instance
    summary2 = get_user_feedback_summary(profile.user_id)
    
    print(f"   First call - interested: {summary['interested_count']}")
    print(f"   Second call - interested: {summary2['interested_count']}")
    
    assert summary["interested_count"] == summary2["interested_count"], "Feedback should persist"
    print("   PASSED\n")
    
    print("=== All Phase 4 Tests Passed! ===\n")
    print("✅ Article feedback logging working")
    print("✅ Feedback reasons tracked and stored")
    print("✅ Feedback summary generation ready")
    print("✅ Signals ready for Phase 5 ranker integration\n")
    print("Next: Phase 5 will use feedback signals to re-rank articles in real-time")


if __name__ == "__main__":
    test_phase4_article_feedback()
