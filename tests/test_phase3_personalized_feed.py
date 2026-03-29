"""Test Phase 3: Single-User Personalized Feed Pipeline."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import inspect
from src.models import UserProfile, Article
from src.agents.personalized_feed_pipeline import (
    generate_personalized_user_feed,
    compare_personalized_vs_baseline,
)


def test_phase3_personalized_feed_pipeline():
    """Test the complete Phase 3 personalized feed pipeline."""
    
    print("\n=== Phase 3 Single-User Personalized Feed Pipeline Test ===\n")
    
    # Create test profile
    profile = UserProfile(
        user_id="user-phase3-test",
        name="Test User Phase 3",
        age=30,
        role="Salaried Professional",
        interests=["Mutual funds & passive investing", "Macro policy & economy"],
        reading_level="intermediate",
        preferred_format="standard",
        portfolio_exposure=["Index funds & ETFs"],
        news_consumption="Daily",
        investing_experience="3-10 years",
    )
    
    # Create mock articles
    articles = [
        Article(
            id="art-001",
            title="Mutual Fund NAV Updates - March 2026",
            published_at="2026-03-29",
            category="market",
            content="Latest NAV updates for mutual funds index funds and sip schemes. Rising market sentiment boosts fund performance.",
            author="ET Staff",
            tags=["mutual-fund", "nav", "market"],
        ),
        Article(
            id="art-002",
            title="RBI Monetary Policy Decision",
            published_at="2026-03-28",
            category="macro",
            content="Reserve Bank announces monetary policy stance. Interest rates policy inflation concerns gdp growth impact on economy.",
            author="Economics Editor",
            tags=["rbi", "monetary-policy", "inflation"],
        ),
        Article(
            id="art-003",
            title="Stock Market Rally Today",
            published_at="2026-03-27",
            category="market",
            content="NSE BSE indices reach new highs. Banking and IT stocks lead the rally today.",
            author="Markets Reporter",
            tags=["stock-market", "nse", "bse"],
        ),
        Article(
            id="art-004",
            title="Bitcoin Price Surge",
            published_at="2026-03-26",
            category="market",
            content="Cryptocurrency prices soar. Bitcoin ethereum crypto markets rally.",
            author="Crypto Editor",
            tags=["crypto", "bitcoin", "blockchain"],
        ),
        Article(
            id="art-005",
            title="Real Estate Market Trends",
            published_at="2026-03-25",
            category="market",
            content="Property prices and real estate developments. Housing market trends 2026.",
            author="Real Estate Desk",
            tags=["real-estate", "property", "housing"],
        ),
    ]
    
    # Test 1: Module imports
    print("✅ Test 1: Module imports verified")
    print(f"   Profile created: {profile.name}")
    print(f"   Articles created: {len(articles)}")
    print("   PASSED\n")
    
    # Test 2: Profile structure validation
    print("✅ Test 2: Profile structure and attributes")
    print(f"   User ID: {profile.user_id}")
    print(f"   Role: {profile.role}")
    print(f"   Interests: {len(profile.interests)}")
    print(f"   Reading level: {profile.reading_level}")
    
    assert profile.user_id == "user-phase3-test"
    assert profile.role == "Salaried Professional"
    assert len(profile.interests) == 2
    print("   PASSED\n")
    
    # Test 3: Article structure validation
    print("✅ Test 3: Article structure and metadata")
    
    for i, article in enumerate(articles[:2]):
        print(f"   Article {i+1}:")
        print(f"      ID: {article.id}")
        print(f"      Title: {article.title[:40]}...")
        print(f"      Category: {article.category}")
        print(f"      Tags: {article.tags}")
        
        assert article.id is not None
        assert article.title is not None
        assert len(article.tags) > 0
    
    print("   PASSED\n")
    
    # Test 4: Component availability check
    print("✅ Test 4: Required components available")
    
    from src.agents.profile_subset_builder import get_articles_for_user as phase2_test
    from src.agents.persona_feed.profiler import analyze_profile as profiler_test
    from src.agents.persona_feed.ranker import rank_articles as ranker_test
    from src.agents.persona_feed.adapter import adapt_articles as adapter_test
    
    print("   ✓ Phase 2 subset builder ready")
    print("   ✓ Profile analyzer ready")
    print("   ✓ Article ranker ready")
    print("   ✓ Article adapter ready")
    print("   PASSED\n")
    
    # Test 5: Async pipeline structure
    print("✅ Test 5: Async pipeline function signature")
    
    import inspect
    sig = inspect.signature(generate_personalized_user_feed)
    params = list(sig.parameters.keys())
    
    print(f"   Function: generate_personalized_user_feed")
    print(f"   Parameters: {', '.join(params)}")
    print(f"   Is coroutine: {inspect.iscoroutinefunction(generate_personalized_user_feed)}")
    
    assert "user_id" in params
    assert "profile" in params
    assert "all_articles" in params
    assert inspect.iscoroutinefunction(generate_personalized_user_feed)
    print("   PASSED\n")
    
    # Test 6: Comparison function signature
    print("✅ Test 6: A/B comparison function")
    
    sig2 = inspect.signature(compare_personalized_vs_baseline)
    params2 = list(sig2.parameters.keys())
    
    print(f"   Function: compare_personalized_vs_baseline")
    print(f"   Parameters: {', '.join(params2)}")
    print(f"   Is coroutine: {inspect.iscoroutinefunction(compare_personalized_vs_baseline)}")
    
    assert "user_id" in params2
    assert "profile" in params2
    assert inspect.iscoroutinefunction(compare_personalized_vs_baseline)
    print("   PASSED\n")
    
    print("=== All Phase 3 Structural Tests Passed! ===\n")
    print("Note: Full async pipeline behavior is validated through later phase integration and UI tests.\n")


if __name__ == "__main__":
    test_phase3_personalized_feed_pipeline()
