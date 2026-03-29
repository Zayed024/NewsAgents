#!/usr/bin/env python3
"""
Demonstration script for ET AI News Navigator
Shows how to interact with the system programmatically
"""

import sys
import os
import asyncio
import json

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.tools.article_loader import (
    load_budget_articles, load_homepage_articles,
    load_breaking_news, load_user_profile,
)
from src.agents.navigator.pipeline import run_navigator_pipeline, handle_query
from src.agents.persona_feed.pipeline import run_feed_comparison
from src.agents.video.pipeline import run_video_pipeline
from src.audit import get_audit_trail, get_session_cost_summary

async def demonstrate_navigator():
    """Demonstrate the News Navigator pipeline"""
    print("=== News Navigator Demonstration ===")

    # Load articles
    articles = load_budget_articles()
    print(f"Loaded {len(articles)} budget articles")

    # Run navigator pipeline
    print("Running navigator pipeline...")
    result = await run_navigator_pipeline(articles, session_id="demo_navigator")

    print(f"Generated briefing with {len(result.angles)} angles")
    print(f"Synthesized content for {len(result.syntheses)} angles")

    # Show cost information
    cost = get_session_cost_summary("demo_navigator")
    print(f"Estimated cost: ${cost['total_cost_usd']:.4f}")

    # Show first angle
    if result.angles:
        print(f"\nFirst angle: {result.angles[0].angle_name}")
        print(f"Description: {result.angles[0].description}")

    return result

async def demonstrate_personalized_feed():
    """Demonstrate the Personalized Feed pipeline"""
    print("\n=== Personalized Feed Demonstration ===")

    # Load articles and profiles
    articles = load_homepage_articles()
    cfo_profile = load_user_profile("cfo_profile")
    young_profile = load_user_profile("young_investor_profile")

    print(f"Loaded {len(articles)} homepage articles")
    print(f"CFO Profile: {cfo_profile.name}, {cfo_profile.role}")
    print(f"Young Investor Profile: {young_profile.name}, {young_profile.role}")

    # Run feed comparison
    print("Running feed comparison...")
    result = await run_feed_comparison(articles, cfo_profile, young_profile)

    print(f"Generated comparison with {len(result.feed_a.feed_items)} items for CFO")
    print(f"Generated comparison with {len(result.feed_b.feed_items)} items for Young Investor")
    print(f"Delta summary: {result.delta_summary}")

    return result

async def demonstrate_video_pipeline():
    """Demonstrate the Vernacular Video pipeline"""
    print("\n=== Vernacular Video Demonstration ===")

    # Load breaking news
    article = load_breaking_news()
    print(f"Loaded breaking news: {article.title}")

    # Run video pipeline (using Hindi as example)
    print("Running video pipeline for Hindi...")
    result = await run_video_pipeline(article, target_language="hi", session_id="demo_video")

    print(f"Video generation status: {result.status}")
    print(f"Generation time: {result.generation_time_seconds:.1f} seconds")

    if result.script:
        print(f"Script length: {len(result.script.script_hindi)} characters")

    if result.video_path and os.path.exists(result.video_path):
        print(f"Video generated at: {result.video_path}")

    return result

async def main():
    """Main demonstration function"""
    print("ET AI News Navigator - System Demonstration")
    print("=" * 50)

    try:
        # Run all demonstrations
        navigator_result = await demonstrate_navigator()
        feed_result = await demonstrate_personalized_feed()
        video_result = await demonstrate_video_pipeline()

        print("\n=== Demonstration Complete ===")
        print("All three pipelines executed successfully!")
        print("System is ready for production use.")

    except Exception as e:
        print(f"\nError during demonstration: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())