"""FastAPI application with all endpoints for the 3 scenarios."""

import sys
import os
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
    load_breaking_news, load_user_profile,
)
from src.agents.navigator.pipeline import run_navigator_pipeline, handle_query
from src.agents.persona_feed.pipeline import run_feed_comparison
from src.agents.video.pipeline import run_video_pipeline
from src.model_router import get_routing_summary
from src.config import OUTPUT_DIR

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


class QueryRequest(BaseModel):
    briefing_id: str = "default"
    question: str


@app.post("/api/v1/navigator/briefing", response_model=NavigatorBriefingResponse)
async def create_briefing(request: BriefingRequest):
    """Run the full News Navigator pipeline on budget articles."""
    try:
        articles = load_budget_articles()
        result = await run_navigator_pipeline(articles, session_id="navigator")
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


# --- Scenario 3: Vernacular Video ---

class VideoRequest(BaseModel):
    article_source: str = "breaking"  # loads the breaking news article
    target_language: str = "hi"


@app.post("/api/v1/video/generate")
async def generate_video(request: VideoRequest):
    """Generate explainer video from breaking news in requested language."""
    try:
        article = load_breaking_news()
        result = await run_video_pipeline(
            article,
            target_language=request.target_language,
            session_id="video",
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
    else:
        articles = []
    return {"count": len(articles), "articles": [a.model_dump() for a in articles]}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
