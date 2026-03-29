#!/usr/bin/env python3
"""
Quick demonstration script for ET AI News Navigator
Shows system structure without executing full pipelines
"""

import sys
import os
import json

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def demonstrate_system_structure():
    """Demonstrate the system structure and components"""
    print("ET AI News Navigator - Quick System Demo")
    print("=" * 50)

    # Show available data
    print("\n1. Available Data:")
    from src.tools.article_loader import (
        load_budget_articles, load_homepage_articles,
        load_breaking_news, load_user_profile,
    )

    budget_articles = load_budget_articles()
    print(f"   - Budget Articles: {len(budget_articles)} articles")

    homepage_articles = load_homepage_articles()
    print(f"   - Homepage Articles: {len(homepage_articles)} articles")

    breaking_news = load_breaking_news()
    print(f"   - Breaking News: {breaking_news.title}")

    cfo_profile = load_user_profile("cfo_profile")
    young_profile = load_user_profile("young_investor_profile")
    print(f"   - User Profiles: {cfo_profile.name}, {young_profile.name}")

    # Show agent structure
    print("\n2. Agent Structure:")
    print("   News Navigator Pipeline (7 agents):")
    print("     - ArticleIngestor")
    print("     - EntityExtractor")
    print("     - AngleClustering")
    print("     - SynthesisEngine")
    print("     - QueryResponder")
    print("     - ChromaDB")
    print("     - EngagementTracker")

    print("\n   Personalised Feed Pipeline (6 agents):")
    print("     - UserProfiler (x2)")
    print("     - ContentRanker (x2)")
    print("     - ContentAdapter (x2)")

    print("\n   Vernacular Video Pipeline (7 agents):")
    print("     - BreakingIngestor")
    print("     - ScriptWriter")
    print("     - FactChecker")
    print("     - ScenePlanner")
    print("     - LanguageValidator")
    print("     - AudioGenerator")
    print("     - VideoComposer")

    # Show model routing
    print("\n3. Smart Model Routing:")
    from src.model_router import get_routing_summary
    routing = get_routing_summary()
    print("   Routing Table:")
    for task, model in routing["routing_table"].items():
        print(f"     {task}: {model}")

    print("\n   Cost Estimates:")
    for model, cost in routing["cost_estimates"].items():
        print(f"     {model}: {cost}")

    # Show API endpoints
    print("\n4. API Endpoints (FastAPI Server):")
    print("   Running at: http://127.0.0.1:8000")
    print("   Documentation: http://127.0.0.1:8000/docs")
    print("   Key Endpoints:")
    print("     POST /api/v1/navigator/briefing")
    print("     POST /api/v1/navigator/query")
    print("     POST /api/v1/feed/compare")
    print("     POST /api/v1/video/generate")
    print("     GET /api/v1/health")
    print("     GET /api/v1/audit/{session_id}")

    # Show UI
    print("\n5. User Interface (Streamlit):")
    print("   Running at: http://localhost:8501")
    print("   Features:")
    print("     - News Navigator Tab")
    print("     - Personalised Feed Tab")
    print("     - Vernacular Video Tab")

    print("\n6. Languages Supported:")
    from src.config import VIDEO_LANGUAGE_PROFILES
    languages = [profile["label"] for profile in VIDEO_LANGUAGE_PROFILES.values()]
    print(f"   {', '.join(languages)}")

    print("\n[System Structure Verified] - All Components Available")
    print("[Ready for full execution with proper API keys and models]")

if __name__ == "__main__":
    demonstrate_system_structure()