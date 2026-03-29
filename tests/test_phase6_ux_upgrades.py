"""Phase 6: Experience Quality UX Upgrades — Test Suite (8 tests)."""

import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.models import Article, UserProfile, FeedItem
from src.agents.feed_organizer import (
    organize_feed_into_sections,
    FeedSection,
    get_section_summary_stats,
    filter_section_by_search,
)
from src.agents.metadata_enricher import (
    infer_article_metadata,
    enrich_feed_with_metadata,
    get_urgency_badge,
    get_sentiment_emoji,
    get_credibility_stars,
    format_freshness,
    get_metadata_summary_stats,
)


def test_1_feed_organization_by_interests():
    """Test 1: Feed organizes articles into sections based on user interests."""
    print("\n[Test 1] Feed organization into interest-based sections...")
    
    profile = UserProfile(
        user_id="test-org-001",
        name="Test Organizer",
        age=40,
        role="CFO",
        reading_level="intermediate",
        interests=["markets", "policy"],
        preferred_format="comprehensive",
    )
    
    # Mock feed items
    feed_items = [
        {"id": "art-1", "title": "Markets Rally", "content": "...", "category": "market"},
        {"id": "art-2", "title": "Budget Policy", "content": "...", "category": "policy"},
        {"id": "art-3", "title": "Stock Boom", "content": "...", "category": "market"},
    ]
    
    # Mock explanations
    explanations = [
        {
            "why_shown": "Matches your interests",
            "relevance_score": 0.85,
            "confidence": "high",
            "matched_tags": ["markets:stocks"],
            "format_applied": "standard",
            "boosted": False,
        },
        {
            "why_shown": "Policy impact",
            "relevance_score": 0.70,
            "confidence": "medium",
            "matched_tags": ["policy:regulation"],
            "format_applied": "standard",
            "boosted": False,
        },
        {
            "why_shown": "Matches your interests",
            "relevance_score": 0.75,
            "confidence": "high",
            "matched_tags": ["markets:indices"],
            "format_applied": "standard",
            "boosted": False,
        },
    ]
    
    organized = organize_feed_into_sections(
        user_id=profile.user_id,
        user_profile=profile,
        feed_items=feed_items,
        explanations=explanations,
    )
    
    # Debug information
    print(f"  DEBUG: Total sections: {len(organized.sections)}")
    for section in organized.sections:
        print(f"    Section '{section.section_name}': {len(section.articles)} articles")
        for article in section.articles:
            title = article['item'].get('title', 'no title')
            print(f"      - {title}")
    print(f"  DEBUG: Total articles across all sections: {organized.total_articles}")
    
    assert len(organized.sections) > 0, "Should have at least one section"
    assert organized.total_articles == 3, f"Should have all 3 articles distributed, got {organized.total_articles}"
    
    print(f"  Sections created: {len(organized.sections)}")
    for section in organized.sections:
        print(f"    - {section.section_name}: {section.article_count} articles")
    
    print("  ✅ Test 1 PASSED: Feed organized into sections")


def test_2_section_filtering_by_search():
    """Test 2: Sections can be filtered by search query."""
    print("\n[Test 2] Filtering sections by search query...")
    
    section = FeedSection(
        section_id="markets",
        section_name="Markets",
        topic="markets",
        description="Market news",
        articles=[
            {
                "item": {"id": "art-1", "title": "Stock Market Rally", "content": "..."},
                "explanation": {"relevance_score": 0.85},
            },
            {
                "item": {"id": "art-2", "title": "Bond Market Trends", "content": "..."},
                "explanation": {"relevance_score": 0.75},
            },
            {
                "item": {"id": "art-3", "title": "Tech Stock Boom", "content": "..."},
                "explanation": {"relevance_score": 0.80},
            },
        ],
    )
    
    # Filter for "stock"
    filtered = filter_section_by_search(section, "stock")
    
    assert filtered.article_count == 2, "Should have 2 articles matching 'stock'"
    print(f"  Original articles: {section.article_count}")
    print(f"  Filtered articles (search='stock'): {filtered.article_count}")
    
    # Filter for "bond"
    filtered_bond = filter_section_by_search(section, "bond")
    assert filtered_bond.article_count == 1, "Should have 1 article for 'bond'"
    
    print("  ✅ Test 2 PASSED: Section filtering works")


def test_3_section_summary_statistics():
    """Test 3: Generate statistics for sections."""
    print("\n[Test 3] Computing section summary statistics...")
    
    section = FeedSection(
        section_id="tech",
        section_name="Technology",
        topic="tech",
        description="Tech news",
        articles=[
            {
                "item": {"id": "art-1", "title": "AI Boom", "content": "..."},
                "explanation": {"relevance_score": 0.95, "confidence": "high", "boosted": True},
            },
            {
                "item": {"id": "art-2", "title": "Startup News", "content": "..."},
                "explanation": {"relevance_score": 0.70, "confidence": "medium", "boosted": False},
            },
            {
                "item": {"id": "art-3", "title": "Tech Regulation", "content": "..."},
                "explanation": {"relevance_score": 0.65, "confidence": "low", "boosted": False},
            },
        ],
    )
    
    stats = get_section_summary_stats(section)
    
    assert stats["article_count"] == 3, "Should count all articles"
    assert 0.75 < stats["avg_relevance"] < 0.85, "Avg relevance should be calculated"
    assert stats["confidence_distribution"]["high"] == 1, "Should count high confidence"
    assert stats["has_boosted"] == True, "Should detect boosted articles"
    
    print(f"  Articles: {stats['article_count']}")
    print(f"  Avg Relevance: {stats['avg_relevance']:.2f}")
    print(f"  Confidence: {stats['confidence_distribution']}")
    print(f"  Has Boosted: {stats['has_boosted']}")
    
    print("  ✅ Test 3 PASSED: Section statistics computed")


def test_4_metadata_inference_sentiment():
    """Test 4: Infer sentiment from article content."""
    print("\n[Test 4] Sentiment inference from article content...")
    
    test_cases = [
        {
            "title": "Stock Market Rally Surges to New Heights",
            "content": "Markets boom with incredible growth and strong gains",
            "expected_sentiment": "bullish",
        },
        {
            "title": "Market Crash Plunges Investors Into Crisis",
            "content": "Severe losses and declining trends threaten portfolios",
            "expected_sentiment": "bearish",
        },
        {
            "title": "Mixed Economic Data Released",
            "content": "The economy shows mixed signals with some gains and some losses",
            "expected_sentiment": "neutral",
        },
    ]
    
    for i, tc in enumerate(test_cases, 1):
        article = {
            "id": f"art-{i}",
            "title": tc["title"],
            "content": tc["content"],
            "author": "Test",
            "published_at": "2026-03-29T00:00:00",
        }
        
        metadata = infer_article_metadata(article)
        
        assert metadata.sentiment == tc["expected_sentiment"], \
            f"Expected {tc['expected_sentiment']}, got {metadata.sentiment}"
        
        emoji = get_sentiment_emoji(metadata)
        print(f"  Case {i}: {tc['expected_sentiment'].title()} {emoji}")
    
    print("  ✅ Test 4 PASSED: Sentiment inference works")


def test_5_metadata_urgency_badges():
    """Test 5: Detect urgency badges from headlines."""
    print("\n[Test 5] Urgency badge detection from titles...")
    
    test_cases = [
        ("BREAKING: Market Crash Announced", "breaking"),
        ("Major Policy Change Announced Today", "important"),
        ("Routine earnings report released", "routine"),
    ]
    
    for title, expected_urgency in test_cases:
        article = {
            "id": "test",
            "title": title,
            "content": "content",
            "author": "Test",
            "published_at": "2026-03-29T00:00:00",
        }
        
        metadata = infer_article_metadata(article)
        
        assert metadata.urgency == expected_urgency, \
            f"Expected {expected_urgency}, got {metadata.urgency}"
        
        badge = get_urgency_badge(metadata)
        print(f"  {title[:40]:<40} → {metadata.urgency.upper():<10} {badge}")
    
    print("  ✅ Test 5 PASSED: Urgency badges detected")


def test_6_credibility_scoring():
    """Test 6: Credibility score based on source and content quality."""
    print("\n[Test 6] Credibility scoring from source and content...")
    
    # High-credibility article
    high_cred = {
        "id": "art-1",
        "title": "Market Analysis",
        "content": "This is a comprehensive analysis with detailed insights " * 20,
        "author": "Reuters",
        "published_at": "2026-03-29T00:00:00",
    }
    
    # Low-credibility article
    low_cred = {
        "id": "art-2",
        "title": "Quick reaction",
        "content": "Quick take",
        "author": "Twitter",
        "published_at": "2026-03-29T00:00:00",
    }
    
    high_metadata = infer_article_metadata(high_cred)
    low_metadata = infer_article_metadata(low_cred)
    
    assert high_metadata.credibility_score > low_metadata.credibility_score, \
        "High-quality source should have higher credibility"
    
    high_stars = get_credibility_stars(high_metadata)
    low_stars = get_credibility_stars(low_metadata)
    
    print(f"  Reuters article: {high_stars} ({high_metadata.credibility_score:.2f})")
    print(f"  Twitter article: {low_stars} ({low_metadata.credibility_score:.2f})")
    
    print("  ✅ Test 6 PASSED: Credibility scoring works")


def test_7_freshness_formatting():
    """Test 7: Format article freshness as human-readable text."""
    print("\n[Test 7] Freshness formatting...")
    
    from datetime import datetime, timedelta
    
    now = datetime.now()
    
    test_cases = [
        (now, "Just now"),
        (now - timedelta(hours=3), "3h ago"),
        (now - timedelta(hours=24), "1 day ago"),
    ]
    
    for dt, expected_text in test_cases:
        article = {
            "id": "test",
            "title": "Test",
            "content": "content",
            "author": "Test",
            "published_at": dt.isoformat(),
        }
        
        metadata = infer_article_metadata(article)
        freshness_text = format_freshness(metadata)
        
        # Check that output is reasonable
        assert any(word in freshness_text.lower() for word in ["ago", "just", "now"]), \
            f"Freshness text should mention time: {freshness_text}"
        
        print(f"  {article['published_at']:<30} → {freshness_text}")
    
    print("  ✅ Test 7 PASSED: Freshness formatting works")


def test_8_full_metadata_enrichment():
    """Test 8: Full enrichment pipeline with multiple articles."""
    print("\n[Test 8] Full metadata enrichment pipeline...")
    
    articles = [
        {
            "id": "art-1",
            "title": "BREAKING: Stock Market Surge",
            "content": "Markets rally strongly with significant gains and growth",
            "author": "Reuters",
            "published_at": "2026-03-29T10:00:00",
        },
        {
            "id": "art-2",
            "title": "Policy Change Announced",
            "content": "Government announces new regulation affecting sectors",
            "author": "ET",
            "published_at": "2026-03-29T08:00:00",
        },
        {
            "id": "art-3",
            "title": "Quick earnings take",
            "content": "Company earnings released",
            "author": "Twitter",
            "published_at": "2026-03-29T06:00:00",
        },
    ]
    
    metadata_map = enrich_feed_with_metadata(articles)
    
    assert len(metadata_map) == 3, "Should enrich all 3 articles"
    
    # Check stats
    stats = get_metadata_summary_stats(metadata_map)
    
    print(f"  Total articles enriched: {stats['total_articles']}")
    print(f"  Sentiment distribution: {stats['sentiment_distribution']}")
    print(f"  Urgency distribution: {stats['urgency_distribution']}")
    print(f"  Avg credibility: {stats['avg_credibility']:.2f}")
    print(f"  Content quality: {stats['content_quality_distribution']}")
    
    # Verify breaking article is detected
    breaking_count = stats['urgency_distribution'].get('breaking', 0)
    assert breaking_count > 0, "Should detect breaking news"
    
    # Verify sentiment distribution exists
    assert sum(stats['sentiment_distribution'].values()) == 3, "All articles should have sentiment"
    
    print("  ✅ Test 8 PASSED: Full enrichment pipeline works")


if __name__ == "__main__":
    print("\n" + "="*70)
    print("PHASE 6: EXPERIENCE QUALITY UX UPGRADES — TEST SUITE")
    print("="*70)
    
    tests = [
        test_1_feed_organization_by_interests,
        test_2_section_filtering_by_search,
        test_3_section_summary_statistics,
        test_4_metadata_inference_sentiment,
        test_5_metadata_urgency_badges,
        test_6_credibility_scoring,
        test_7_freshness_formatting,
        test_8_full_metadata_enrichment,
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
