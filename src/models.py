from pydantic import BaseModel, Field
from datetime import datetime


# --- Article Models ---
class Article(BaseModel):
    id: str
    title: str
    published_at: str
    category: str  # macro, sector, market, expert, historical, tax
    content: str
    author: str
    tags: list[str] = []
    url: str = ""


# --- Entity Models ---
class EntityMap(BaseModel):
    people: dict[str, list[str]] = {}       # person_name -> [article_ids]
    companies: dict[str, list[str]] = {}    # company_name -> [article_ids]
    sectors: dict[str, list[str]] = {}      # sector_name -> [article_ids]
    policies: dict[str, list[str]] = {}     # policy_item -> [article_ids]
    keywords: dict[str, list[str]] = {}     # keyword -> [article_ids]


# --- Angle / Cluster Models ---
class AngleCluster(BaseModel):
    angle_name: str          # e.g. "Macro Impact", "Sector Winners & Losers"
    description: str         # brief description of this angle
    article_ids: list[str]   # which articles belong to this cluster
    key_themes: list[str]    # main themes within this angle


class AngleClusters(BaseModel):
    angles: list[AngleCluster]


# --- Synthesis Models ---
class SynthesisEntry(BaseModel):
    angle_name: str
    synthesis: str           # dense paragraph with citations
    source_articles: list[str]  # article IDs cited
    key_takeaways: list[str]


class BriefingSynthesis(BaseModel):
    entries: list[SynthesisEntry]


# --- Query Models ---
class QueryRequest(BaseModel):
    briefing_id: str = "default"
    question: str


class QueryResponse(BaseModel):
    answer: str
    sources: list[str]
    angle: str
    is_non_overlapping: bool = True


# --- User Profile Models ---
class UserProfile(BaseModel):
    user_id: str
    name: str
    age: int
    role: str
    interests: list[str] = []
    reading_level: str = "intermediate"  # beginner, intermediate, expert
    preferred_format: str = "standard"
    portfolio_exposure: list[str] = []
    news_consumption: str = ""
    investing_experience: str = ""
    company_type: str = ""


# --- Personalised Feed Models ---
class FeedItem(BaseModel):
    article_id: str
    original_title: str
    adapted_title: str
    adapted_content: str
    format_type: str        # "executive_summary", "explainer", "data_table", "card"
    relevance_score: float
    adaptation_notes: str   # what was changed and why


class PersonaFeed(BaseModel):
    user_profile: UserProfile
    feed_items: list[FeedItem]
    reading_level_applied: str
    format_applied: str


class FeedComparison(BaseModel):
    feed_a: PersonaFeed
    feed_b: PersonaFeed
    delta_summary: str      # e.g. "8 of 10 stories differ..."


# --- Video Models ---
class VideoScript(BaseModel):
    script_hindi: str
    script_transliteration: str
    estimated_duration_seconds: int
    key_facts_used: list[str]
    analogies_used: list[str] = []


class VideoScene(BaseModel):
    chapter: str
    heading: str
    text: str
    narration_text: str = ""
    visual_hint: str = ""
    sentiment: str = "neutral"
    duration_seconds: int
    scene_type: str = "narrative"  # narrative, numbers, impact, timeline, closing


class VideoScenePlan(BaseModel):
    target_duration_seconds: int
    scenes: list[VideoScene] = []
    story_arc_summary: str = ""
    key_players: list[str] = []
    sentiment_shifts: list[str] = []
    contrarian_perspective: str = ""
    watch_next: list[str] = []


class FactCheckClaim(BaseModel):
    claim: str
    source_match: bool
    source_text: str = ""


class FactCheckReport(BaseModel):
    claims: list[FactCheckClaim]
    accuracy_score: float
    flagged_claims: list[str] = []


class VideoResult(BaseModel):
    video_path: str = ""
    script: VideoScript | None = None
    fact_check: FactCheckReport | None = None
    scene_plan: VideoScenePlan | None = None
    generation_time_seconds: float = 0.0
    audio_path: str = ""
    status: str = "success"  # success, degraded, failed


# --- Audit Models ---
class AuditEntry(BaseModel):
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    session_id: str = "default"
    agent_name: str = ""
    action: str = ""
    model_used: str = ""
    input_summary: str = ""
    output_summary: str = ""
    latency_ms: int = 0
    estimated_input_tokens: int = 0
    estimated_output_tokens: int = 0
    estimated_cost_usd: float = 0.0
    status: str = "success"  # success, fallback, error
    error_detail: str = ""


# --- Retrieval Contract Models (Phase 3) ---
class RetrievalFreshness(BaseModel):
    subset_reused: bool = False
    freshness_max_minutes: int = 120
    subset_age_minutes: float | None = None
    subset_updated_at: str | None = None


class TopicRetrievalContract(BaseModel):
    topic: str = ""
    total_articles_scanned: int = 0
    relevant_articles_count: int = 0
    relevant_article_ids: list[str] = []
    excluded_article_ids: list[str] = []
    coverage_mode: str = "all_articles"
    inclusion_reasons: dict[str, str] = {}
    exclusion_reasons: dict[str, str] = {}
    freshness: RetrievalFreshness = RetrievalFreshness()


# --- API Response Wrappers ---
class NavigatorBriefingResponse(BaseModel):
    briefing_id: str
    topic: str = ""
    total_articles_scanned: int = 0
    relevant_articles_count: int = 0
    relevant_article_ids: list[str] = []
    excluded_article_ids: list[str] = []
    coverage_mode: str = "all_articles"
    inclusion_reasons: dict[str, str] = {}
    exclusion_reasons: dict[str, str] = {}
    retrieval_contract: TopicRetrievalContract | None = None
    angles: list[AngleCluster]
    syntheses: list[SynthesisEntry]
    deep_briefing_markdown: str = ""
    suggested_questions: list[str] = []
    entity_navigation: dict[str, list[dict]] = {}
    entity_map: EntityMap | None = None
    audit_trail: list[AuditEntry] = []


class NavigatorQueryResponse(BaseModel):
    answer: str
    sources: list[str]
    angle: str
    audit_trail: list[AuditEntry] = []


class FeedCompareResponse(BaseModel):
    feed_a: PersonaFeed
    feed_b: PersonaFeed
    delta_summary: str
    audit_trail: list[AuditEntry] = []


class VideoGenerateResponse(BaseModel):
    video_path: str
    script: VideoScript | None = None
    fact_check: FactCheckReport | None = None
    scene_plan: VideoScenePlan | None = None
    generation_time_seconds: float
    audit_trail: list[AuditEntry] = []
