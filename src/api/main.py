"""FastAPI application with all endpoints for the 3 scenarios."""

import sys
import os
import time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from src.models import (
    UserProfile, NavigatorBriefingResponse, NavigatorQueryResponse,
    FeedCompareResponse, VideoGenerateResponse, AuditEntry,
)
from src.audit import get_audit_trail
from src.tools.article_loader import (
    load_budget_articles, load_homepage_articles,
    load_breaking_news, load_breaking_news_articles, load_user_profile,
)
from src.agents.navigator.pipeline import run_navigator_pipeline, handle_query
from src.agents.persona_feed.pipeline import run_feed_comparison
from src.agents.video.pipeline import run_video_pipeline
from src.model_router import get_routing_summary
from src.config import OUTPUT_DIR
from src.tools.corpus.operations import (
    compute_freshness_metrics,
    load_recent_run_summaries,
    run_crawl_refresh,
    run_subset_refresh,
)
from src.tools.corpus.compliance import generate_compliance_report, load_compliance_snapshots
from src.agents.onboarding import (
    QUICK_START_QUESTIONS, DEEP_SETUP_QUESTIONS,
    answers_to_user_profile, save_user_profile, load_user_by_id, list_all_user_profiles
)
from src.agents.corpus_personalizer import profile_to_crawl_queries, profile_to_subset_tags
from src.agents.profile_subset_builder import get_articles_for_user
from src.agents.persona_feed.pipeline import generate_persona_feed
from src.agents.personalized_feed_pipeline import (
    generate_personalized_user_feed, compare_personalized_vs_baseline
)

app = FastAPI(
    title="ET AI News Navigator",
    description="AI-Native News Experience — Track 8, ET AI Hackathon 2026",
    version="1.0.0",
)

# Mount output directory for serving generated videos
os.makedirs(OUTPUT_DIR, exist_ok=True)
app.mount("/output", StaticFiles(directory=OUTPUT_DIR), name="output")


# --- Health & Info ---

@app.get("/api/v1/health")
async def health():
    return {
        "status": "healthy",
        "service": "ET AI News Navigator",
        "model_routing": get_routing_summary(),
    }


# --- Scenario 1: News Navigator ---

class BriefingRequest(BaseModel):
    article_source: str = "budget"  # "budget" loads the 22 budget articles
    topic: str = "Union Budget 2026"
    enforce_topic_coverage: bool = True


class QueryRequest(BaseModel):
    briefing_id: str = "default"
    question: str


@app.post("/api/v1/navigator/briefing", response_model=NavigatorBriefingResponse)
async def create_briefing(request: BriefingRequest):
    """Run the full News Navigator pipeline on budget articles."""
    try:
        articles = load_budget_articles(topic=request.topic)
        result = await run_navigator_pipeline(
            articles,
            session_id="navigator",
            topic=request.topic,
            enforce_topic_coverage=request.enforce_topic_coverage,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/navigator/query", response_model=NavigatorQueryResponse)
async def query_briefing(request: QueryRequest):
    """Ask a follow-up question on an existing briefing."""
    try:
        result = await handle_query(request.question, session_id="navigator")
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --- Scenario 2: Personalised Feed ---

class FeedCompareRequest(BaseModel):
    profile_a_name: str = "cfo_profile"
    profile_b_name: str = "young_investor_profile"


@app.post("/api/v1/feed/compare", response_model=FeedCompareResponse)
async def compare_feeds(request: FeedCompareRequest):
    """Generate side-by-side persona comparison feeds."""
    try:
        articles = load_homepage_articles()
        profile_a = load_user_profile(request.profile_a_name)
        profile_b = load_user_profile(request.profile_b_name)
        result = await run_feed_comparison(articles, profile_a, profile_b)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --- Phase 2: Profile-Aware Personalized Feed ---

class PersonalizedFeedRequest(BaseModel):
    user_id: str
    max_items: int = 10


class PersonalizedFeedResponse(BaseModel):
    user_id: str
    user_name: str
    article_count: int
    articles: list[dict]
    crawl_intents: dict
    subset_tags: dict


@app.post("/api/v1/feed/personalized", response_model=PersonalizedFeedResponse)
async def get_personalized_feed(request: PersonalizedFeedRequest):
    """Get a personalized feed for a specific user (Phase 2).
    
    Uses profile-driven corpus retrieval to show highly relevant articles.
    Articles are filtered and tagged based on user's interests, experience, and role.
    """
    try:
        # Load user profile
        profile = load_user_by_id(request.user_id)
        if not profile:
            raise HTTPException(status_code=404, detail=f"User {request.user_id} not found")
        
        # Get articles
        all_articles = load_homepage_articles(max_items=50)
        
        # Get personalized subset using profile
        articles = get_articles_for_user(
            user_id=request.user_id,
            all_articles=[a.model_dump() for a in all_articles],
            profile=profile,
            use_cache=True,
            max_items=request.max_items,
        )
        
        # Get corpus intents for response
        crawl_intents = profile_to_crawl_queries(profile)
        subset_tags = profile_to_subset_tags(profile)
        
        return PersonalizedFeedResponse(
            user_id=request.user_id,
            user_name=profile.name,
            article_count=len(articles),
            articles=articles,
            crawl_intents=crawl_intents,
            subset_tags=subset_tags,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --- Phase 3: Single-User Personalized Feed (Fully Adapted) ---

class FullPersonalizedFeedRequest(BaseModel):
    user_id: str
    use_personalized_subset: bool = True
    max_items: int = 5


class FullPersonalizedFeedResponse(BaseModel):
    user_id: str
    user_name: str
    feed_items: list[dict]
    explanations: list[dict]  # Why each article, relevance, confidence, matched tags
    personalization_method: str
    total_items: int


@app.post("/api/v1/feed/personalized-full", response_model=FullPersonalizedFeedResponse)
async def get_full_personalized_feed(request: FullPersonalizedFeedRequest):
    """Get a fully personalized feed for a user (Phase 3).
    
    Full pipeline:
    1. Get personalized corpus subset (Phase 2: interest-filtered)
    2. Analyze profile preferences (profiler)
    3. Rank articles by relevance (ranker)
    4. Adapt articles to user's depth/format (adapter)
    5. Explain: why each article, confidence, matched tags
    
    This is the production feed endpoint.
    """
    try:
        # Load user profile
        profile = load_user_by_id(request.user_id)
        if not profile:
            raise HTTPException(status_code=404, detail=f"User {request.user_id} not found")
        
        # Get articles
        all_articles = load_homepage_articles(max_items=50)
        
        # Run full personalized feed pipeline
        result = await generate_personalized_user_feed(
            user_id=request.user_id,
            profile=profile,
            all_articles=all_articles,
            session_id=f"feed_{request.user_id}",
            use_personalized_subset=request.use_personalized_subset,
            top_n=request.max_items,
        )
        
        feed = result["feed"]
        explanations = result["explanations"]
        
        return FullPersonalizedFeedResponse(
            user_id=request.user_id,
            user_name=profile.name,
            feed_items=[item.model_dump() for item in feed.feed_items],
            explanations=explanations,
            personalization_method=result["personalization_method"],
            total_items=len(feed.feed_items),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class FeedComparisonRequest(BaseModel):
    user_id: str


class FeedComparisonResultResponse(BaseModel):
    user_id: str
    user_name: str
    personalized_items: list[dict]
    baseline_items: list[dict]
    delta_metrics: dict


@app.post("/api/v1/feed/comparison-test", response_model=FeedComparisonResultResponse)
async def run_feed_ab_test(request: FeedComparisonRequest):
    """Run A/B test: personalized feed vs. baseline ranking (Phase 3).
    
    Returns both feeds side-by-side for measurement of engagement differences.
    """
    try:
        # Load user profile
        profile = load_user_by_id(request.user_id)
        if not profile:
            raise HTTPException(status_code=404, detail=f"User {request.user_id} not found")
        
        # Get articles
        all_articles = load_homepage_articles(max_items=50)
        
        # Run comparison
        result = await compare_personalized_vs_baseline(
            user_id=request.user_id,
            profile=profile,
            all_articles=all_articles,
            session_id=f"feed_test_{request.user_id}",
        )
        
        return FeedComparisonResultResponse(
            user_id=request.user_id,
            user_name=profile.name,
            personalized_items=[item.model_dump() for item in result["personalized_feed"].feed_items],
            baseline_items=[item.model_dump() for item in result["baseline_feed"].feed_items],
            delta_metrics=result["delta_metrics"],
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --- Scenario 3: Vernacular Video ---

class VideoRequest(BaseModel):
    article_source: str = "breaking"  # loads the breaking news article
    article_id: str | None = None
    target_language: str = "hi"


@app.post("/api/v1/video/generate")
async def generate_video(request: VideoRequest):
    """Generate explainer video from breaking news in requested language."""
    try:
        article = load_breaking_news(article_id=request.article_id)
        session_id = f"video-{article.id}-{request.target_language}-{int(time.time() * 1000)}"
        result = await run_video_pipeline(
            article,
            target_language=request.target_language,
            session_id=session_id,
        )
        return {
            "video_path": result.video_path,
            "video_url": f"/output/{os.path.basename(result.video_path)}" if result.video_path else "",
            "target_language": request.target_language,
            "script": result.script.model_dump() if result.script else None,
            "fact_check": result.fact_check.model_dump() if result.fact_check else None,
            "scene_plan": result.scene_plan.model_dump() if result.scene_plan else None,
            "generation_time_seconds": result.generation_time_seconds,
            "status": result.status,
            "audit_trail": [e.model_dump() for e in get_audit_trail("video")],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --- Audit ---

@app.get("/api/v1/audit/{session_id}")
async def get_audit(session_id: str):
    """Get full audit trail for a session."""
    trail = get_audit_trail(session_id)
    return {"session_id": session_id, "entries": [e.model_dump() for e in trail]}


# --- Articles ---

@app.get("/api/v1/articles")
async def list_articles(source: str = "budget"):
    """List available articles."""
    if source == "budget":
        articles = load_budget_articles()
    elif source == "homepage":
        articles = load_homepage_articles()
    elif source == "breaking":
        articles = load_breaking_news_articles()
    else:
        articles = []
    return {"count": len(articles), "articles": [a.model_dump() for a in articles]}


# --- User Management / Phase 1 Onboarding ---

class OnboardingQuestionsResponse(BaseModel):
    quick_start: list[dict]
    deep_setup: list[dict]


class CreateUserRequest(BaseModel):
    name: str
    quick_start_answers: dict  # question_id -> answer(s)
    is_deep_setup: bool = False
    deep_setup_answers: dict = {}  # question_id -> answer(s) if is_deep_setup=True


class CreateUserResponse(BaseModel):
    user_id: str
    name: str
    role: str
    reading_level: str
    preferred_format: str
    priority_topics: list[str]
    message: str


@app.get("/api/v1/onboarding/questions")
async def get_onboarding_questions():
    """Get all available onboarding questions."""
    return OnboardingQuestionsResponse(
        quick_start=QUICK_START_QUESTIONS,
        deep_setup=DEEP_SETUP_QUESTIONS,
    )


@app.post("/api/v1/users/create", response_model=CreateUserResponse)
async def create_user(request: CreateUserRequest):
    """Create a new user profile from onboarding answers."""
    try:
        import uuid
        
        # Generate unique user_id
        user_id = f"user-{uuid.uuid4().hex[:8]}"
        
        # Combine all answers
        all_answers = {**request.quick_start_answers}
        if request.is_deep_setup:
            all_answers.update(request.deep_setup_answers)
        
        # Convert to user profile
        profile = answers_to_user_profile(
            user_id=user_id,
            name=request.name,
            answers=all_answers,
            is_deep_setup=request.is_deep_setup,
        )
        
        # Save to disk
        success = save_user_profile(profile)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to save user profile")
        
        return CreateUserResponse(
            user_id=user_id,
            name=profile.name,
            role=profile.role,
            reading_level=profile.reading_level,
            preferred_format=profile.preferred_format,
            priority_topics=profile.interests,
            message=f"Welcome, {request.name}! Your personalized feed is ready.",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/users")
async def list_users():
    """List all saved user profiles."""
    try:
        users = list_all_user_profiles()
        return {"count": len(users), "users": users}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/users/{user_id}")
async def get_user(user_id: str):
    """Get a specific user profile."""
    try:
        profile = load_user_by_id(user_id)
        if not profile:
            raise HTTPException(status_code=404, detail=f"User {user_id} not found")
        return profile.model_dump()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --- Operations / Freshness (Phase 4) ---

class CrawlRefreshRequest(BaseModel):
    topic: str = "Union Budget 2026"
    max_pages: int = 60
    max_depth: int = 2
    bootstrap_if_empty: bool = True


class SubsetRefreshRequest(BaseModel):
    topics: list[str] = ["Union Budget 2026"]
    profile_names: list[str] = ["cfo_profile", "young_investor_profile"]
    max_items: int = 40


@app.post("/api/v1/ops/crawl-refresh")
async def ops_crawl_refresh(request: CrawlRefreshRequest):
    try:
        return run_crawl_refresh(
            topic=request.topic,
            max_pages=request.max_pages,
            max_depth=request.max_depth,
            bootstrap_if_empty=request.bootstrap_if_empty,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/ops/subset-refresh")
async def ops_subset_refresh(request: SubsetRefreshRequest):
    try:
        return run_subset_refresh(
            topics=request.topics,
            profile_names=request.profile_names,
            max_items=request.max_items,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/ops/freshness-metrics")
async def ops_freshness_metrics(topic_stale_after_minutes: int = 120, persona_stale_after_minutes: int = 180):
    try:
        return compute_freshness_metrics(
            topic_stale_after_minutes=topic_stale_after_minutes,
            persona_stale_after_minutes=persona_stale_after_minutes,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/ops/run-summaries")
async def ops_run_summaries(limit: int = 20):
    try:
        return {"summaries": load_recent_run_summaries(limit=limit)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/ops/compliance/snapshots")
async def ops_compliance_snapshots(limit: int = 100):
    try:
        return {"snapshots": load_compliance_snapshots(limit=limit)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/ops/compliance/report")
async def ops_compliance_report(limit: int = 500, persist: bool = True):
    try:
        return generate_compliance_report(limit=limit, persist=persist)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
