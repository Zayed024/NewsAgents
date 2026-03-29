"""Test Phase 1 onboarding flow."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.agents.onboarding import (
    QUICK_START_QUESTIONS, DEEP_SETUP_QUESTIONS,
    answers_to_preference_vector, answers_to_user_profile,
    save_user_profile, load_user_by_id, list_all_user_profiles
)


def test_phase1_onboarding():
    """Test the complete Phase 1 onboarding flow."""
    
    print("\n=== Phase 1 Onboarding Test ===\n")
    
    # 1. Test questions structure
    print("✅ Test 1: Questions structure")
    print(f"   Quick start questions: {len(QUICK_START_QUESTIONS)}")
    print(f"   Deep setup questions: {len(DEEP_SETUP_QUESTIONS)}")
    assert len(QUICK_START_QUESTIONS) == 4, "Should have 4 quick questions"
    assert len(DEEP_SETUP_QUESTIONS) == 6, "Should have 6 deep questions"
    print("   PASSED\n")
    
    # 2. Test answer-to-preference conversion
    print("✅ Test 2: Answer-to-preference conversion")
    sample_answers = {
        "role": "Salaried Professional",
        "investing_experience": "1-3 years",
        "primary_interests": ["Personal savings & tax optimization", "Mutual funds & passive investing"],
        "content_preference": "Mix of formats",
        "age_range": "26-35",
        "risk_appetite": "Moderate (balanced growth)",
    }
    
    pref = answers_to_preference_vector(sample_answers)
    print(f"   Content depth: {pref['content_depth']}")
    print(f"   Format: {pref['format_preference']}")
    print(f"   Tone: {pref['tone']}")
    print(f"   Priority topics: {pref['priority_topics']}")
    assert pref['content_depth'] == "intermediate"
    assert pref['tone'] == "formal_analytical"  # "Salaried Professional" role triggers this
    print("   PASSED\n")
    
    # 3. Test answer-to-profile conversion
    print("✅ Test 3: Answer-to-user-profile conversion")
    profile = answers_to_user_profile(
        user_id="test-user-001",
        name="Test User",
        answers=sample_answers,
    )
    print(f"   User ID: {profile.user_id}")
    print(f"   Name: {profile.name}")
    print(f"   Role: {profile.role}")
    print(f"   Age: {profile.age}")
    print(f"   Reading level: {profile.reading_level}")
    assert profile.user_id == "test-user-001"
    assert profile.name == "Test User"
    assert profile.age == 26  # start of 26-35 range
    print("   PASSED\n")
    
    # 4. Test save and load
    print("✅ Test 4: Save and load user profile")
    success = save_user_profile(profile)
    assert success, "Should save profile successfully"
    print(f"   Saved: {profile.user_id}")
    
    loaded_profile = load_user_by_id("test-user-001")
    assert loaded_profile is not None, "Should load saved profile"
    assert loaded_profile.name == "Test User"
    print(f"   Loaded: {loaded_profile.user_id}")
    print("   PASSED\n")
    
    # 5. Test list all profiles
    print("✅ Test 5: List all user profiles")
    all_users = list_all_user_profiles()
    print(f"   Total profiles in system: {len(all_users)}")
    print(f"   Profiles: {[u['name'] for u in all_users]}")
    assert len(all_users) >= 2, "Should have at least the test user and existing profiles"
    print("   PASSED\n")
    
    print("=== All Phase 1 Tests Passed! ===\n")


if __name__ == "__main__":
    test_phase1_onboarding()
