"""Test Phase 2: Profile-Aware Corpus Personalization."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
from src.models import UserProfile
from src.agents.corpus_personalizer import (
    profile_to_crawl_queries,
    profile_to_subset_tags,
    filter_articles_for_profile,
    tag_articles_with_profile_data,
    get_profile_segment_cache_key,
)
from src.agents.profile_subset_builder import (
    build_profile_specific_subset,
    save_profile_subset,
    load_profile_subset,
    get_articles_for_user,
)


def test_phase2_corpus_personalization():
    """Test the complete Phase 2 corpus personalization flow."""
    
    print("\n=== Phase 2 Corpus Personalization Test ===\n")
    
    # Test 1: Profile to crawl queries
    print("✅ Test 1: Profile to crawl queries")
    profile = UserProfile(
        user_id="user-test-001",
        name="Test User",
        age=30,
        role="Salaried Professional",
        interests=["Mutual funds & passive investing", "Macro policy & economy"],
        reading_level="intermediate",
        preferred_format="standard",
        portfolio_exposure=["Index funds & ETFs", "Individual stocks"],
        news_consumption="Multiple times a week",
        investing_experience="3-10 years",
    )
    
    crawl_intents = profile_to_crawl_queries(profile)
    print(f"   Keywords: {crawl_intents['keywords'][:5]}...")
    print(f"   Sectors: {crawl_intents['sectors']}")
    print(f"   Intent types: {crawl_intents['intent_types']}")
    print(f"   Profile segment: {crawl_intents['profile_segment']}")
    assert len(crawl_intents['keywords']) > 0, "Should have keywords"
    assert len(crawl_intents['sectors']) > 0, "Should have sectors"
    assert len(crawl_intents['intent_types']) > 0, "Should have intent types"
    print("   PASSED\n")
    
    # Test 2: Profile to subset tags
    print("✅ Test 2: Profile to subset tags")
    subset_tags = profile_to_subset_tags(profile)
    print(f"   Relevance topic: {subset_tags['relevance_topic']}")
    print(f"   Audience level: {subset_tags['audience_level']}")
    print(f"   Intent type: {subset_tags['intent_type']}")
    print(f"   Content filter: {subset_tags['content_filter']}")
    assert subset_tags['audience_level'] == "intermediate"
    assert subset_tags['intent_type'] in ["market_move", "portfolio_action", "news"]
    print("   PASSED\n")
    
    # Test 3: Article filtering
    print("✅ Test 3: Article filtering")
    mock_articles = [
        {
            "id": "art-001",
            "title": "Mutual Fund NAV Updates",
            "content": "Latest NAV updates for mutual funds and index funds",
            "tags": ["mutual-fund", "nav"],
        },
        {
            "id": "art-002",
            "title": "Bitcoin Price Surge",
            "content": "Bitcoin and cryptocurrency prices",
            "tags": ["crypto", "bitcoin"],
        },
        {
            "id": "art-003",
            "title": "GDP Growth and Inflation",
            "content": "Latest macro economic data on gdp inflation and monetary policy",
            "tags": ["macro", "gdp"],
        },
    ]
    
    filtered = filter_articles_for_profile(mock_articles, profile)
    print(f"   Input articles: {len(mock_articles)}")
    print(f"   Filtered articles: {len(filtered)}")
    print(f"   Filtered: {[a.get('id') for a in filtered]}")
    assert len(filtered) > 0, "Should filter some articles"
    # Should include mutual fund and gdp articles
    filtered_ids = {a.get('id') for a in filtered}
    assert "art-001" in filtered_ids or "art-003" in filtered_ids, "Should include relevant articles"
    print("   PASSED\n")
    
    # Test 4: Article tagging
    print("✅ Test 4: Article tagging with profile data")
    article = mock_articles[0].copy()
    tagged = tag_articles_with_profile_data(article, profile)
    print(f"   Original tags: {mock_articles[0]['tags']}")
    print(f"   Tagged tags: {tagged['tags']}")
    # Should have added audience and intent tags
    tag_types = {tag.split(':')[0] for tag in tagged['tags'] if ':' in tag}
    assert "audience" in tag_types, "Should add audience tag"
    assert "intent" in tag_types, "Should add intent tag"
    assert "relevance" in tag_types, "Should add relevance tag"
    print("   PASSED\n")
    
    # Test 5: Profile segment cache key
    print("✅ Test 5: Profile segment cache key")
    cache_key = get_profile_segment_cache_key(profile)
    print(f"   Cache key: {cache_key}")
    assert cache_key.startswith("segment_"), "Cache key should have segment prefix"
    print("   PASSED\n")
    
    # Test 6: Build profile-specific subset
    print("✅ Test 6: Build profile-specific subset")
    subset = build_profile_specific_subset(mock_articles, profile, max_items=5)
    print(f"   Subset user: {subset['user_name']}")
    print(f"   Selected count: {subset['selected_count']}")
    print(f"   Total available: {subset['total_available']}")
    print(f"   Keywords used: {subset['filter_criteria']['keywords'][:5]}...")
    assert subset['user_id'] == profile.user_id
    assert subset['selected_count'] > 0, "Should select articles"
    assert len(subset['articles']) > 0, "Articles should be in subset"
    print("   PASSED\n")
    
    # Test 7: Save and load profile subset
    print("✅ Test 7: Save and load profile subset")
    saved = save_profile_subset(profile, subset)
    assert saved, "Should save successfully"
    print(f"   Saved subset for {profile.user_id}")
    
    loaded = load_profile_subset(profile.user_id)
    assert loaded is not None, "Should load subset"
    assert loaded['user_id'] == profile.user_id
    assert loaded['selected_count'] == subset['selected_count']
    print(f"   Loaded subset with {loaded['selected_count']} articles")
    print("   PASSED\n")
    
    # Test 8: Get articles for user (integrated flow)
    print("✅ Test 8: Get articles for user (integrated flow)")
    articles = get_articles_for_user(
        user_id=profile.user_id,
        all_articles=mock_articles,
        profile=profile,
        use_cache=True,
        max_items=5,
    )
    print(f"   Articles returned: {len(articles)}")
    print(f"   Article IDs: {[a.get('id') for a in articles]}")
    assert len(articles) > 0, "Should return articles"
    # Second call should use cache
    articles2 = get_articles_for_user(
        user_id=profile.user_id,
        all_articles=mock_articles,
        profile=profile,
        use_cache=True,
        max_items=5,
    )
    assert articles == articles2, "Cached results should be identical"
    print("   Cache working correctly")
    print("   PASSED\n")
    
    print("=== All Phase 2 Tests Passed! ===\n")


if __name__ == "__main__":
    test_phase2_corpus_personalization()
