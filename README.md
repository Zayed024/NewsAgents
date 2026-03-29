# ET AI News Navigator

**Track 8: AI-Native News Experience | ET AI Hackathon 2026**

A **15-agent multi-agent system** that transforms how business news is consumed — from static, one-size-fits-all articles to interactive, personalised, multilingual experiences.

Phase roadmap status: **Phases 1-7 complete** plus **Experience Intelligence Layer (5 steps) complete** (personal impact explainers, contrarian views, live sentiment pulse).

## What It Does

| Scenario | Description | Agents |
|----------|-------------|--------|
| **News Navigator** | Synthesises 22 Union Budget articles into an interactive briefing with 6 navigable angles, non-overlapping Q&A, and engagement-aware retuning | 7 (Ingestor, EntityExtractor, AngleClustering, Synthesizer, QueryResponder, ChromaDB, EngagementTracker) |
| **Personalised Feed** | Same articles, completely different experience for a CFO vs a 24-year-old first-time investor — different depth, format, framing | 6 (Profiler x2, Ranker x2, Adapter x2) |
| **Vernacular Video** | Breaking news to chaptered, fact-checked explainer video in **7 Indian languages** in under 60 seconds | 7 (BreakingIngestor, ScriptWriter, FactChecker, ScenePlanner, LanguageValidator, AudioGenerator, VideoComposer) |

## Key Differentiators

- **Smart Model Routing**: NVIDIA Nemotron + Llama-4 (primary), Gemini (fallback), Ollama (local) — **3-tier fallback with free primary**
- **15 Specialised Agents**: Clear role separation with handoff protocols across 3 pipelines
- **Interactive Entity Graph**: Hoverable Plotly network visualization showing entity-angle relationships with metadata drill-down
- **8 Languages**: Hindi, Marathi, Tamil, Telugu, Kannada, Bhojpuri, Punjabi, English — with language-specific TTS voices and writing systems
- **Engagement Tracking**: Cross-session learning retunes content delivery without LLM cost (extra credit feature)
- **Story Arc Depth**: Chaptered videos with sentiment tracking, contrarian perspectives, and "what to watch next"
- **So What Explainer Layer**: One-click "What does this mean for me?" personal impact summary in the personalised feed
- **Contrarian View Toggle**: "Hear the other side" in both News Navigator and Personalised Feed to avoid echo-chamber bias
- **Live Sentiment Pulse**: Bullish/Cautious/Bearish pulse with one-line reason in sectioned feed and Story Arc chapters
- **Full Audit Trail**: Every agent step logged with model, latency, token count, and estimated cost

## Quick Start

### Prerequisites
- Python 3.11+
- NVIDIA API key (free at build.nvidia.com) **or** Gemini API key
- ffmpeg (for video generation)
- Ollama with `qwen2.5vl:3b` (optional, local fallback)

### Setup

```bash
git clone https://github.com/Zayed024/NewsAgents.git
cd NewsAgents
pip install -r requirements.txt

# Set API key (at least one required; NVIDIA recommended — free endpoint)
export NVIDIA_API_KEY=your_nvidia_key   # Linux/Mac
set NVIDIA_API_KEY=your_nvidia_key      # Windows

# Or use Gemini
export GOOGLE_API_KEY=your_key_here     # Linux/Mac

# Optional: Start Ollama for local fallback
ollama serve &
ollama pull qwen2.5vl:3b
```

### Run

```bash
# Streamlit UI (recommended for demo)
streamlit run ui/app.py

# FastAPI server
uvicorn src.api.main:app --reload --port 8000
```

API docs: http://localhost:8000/docs

### Run Tests

```bash
python tests/test_smoke.py

# Phase test suites
.venv\Scripts\python tests/test_phase1_onboarding.py
.venv\Scripts\python tests/test_phase2_corpus_personalization.py
.venv\Scripts\python tests/test_phase3_personalized_feed.py
.venv\Scripts\python tests/test_phase4_feedback_loop.py
.venv\Scripts\python tests/test_phase5_adaptive_learning.py
.venv\Scripts\python tests/test_phase6_ux_upgrades.py
.venv\Scripts\python tests/test_phase7_measurement_ab.py
.venv\Scripts\python -m pytest -q tests/test_phase8_signal_layers.py
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/navigator/briefing` | Generate full News Navigator briefing |
| POST | `/api/v1/navigator/query` | Ask follow-up question on briefing |
| POST | `/api/v1/feed/compare` | Generate side-by-side persona feeds |
| POST | `/api/v1/feed/personalized` | Profile-aware corpus-personalized feed subset |
| POST | `/api/v1/feed/personalized-full` | End-to-end personalized feed with explanations |
| POST | `/api/v1/feed/comparison-test` | Personalized vs baseline A/B comparison for one user |
| POST | `/api/v1/video/generate` | Generate vernacular explainer video |
| GET | `/api/v1/onboarding/questions` | Retrieve onboarding question sets |
| POST | `/api/v1/users/create` | Create user profile from onboarding answers |
| GET | `/api/v1/users` | List saved user profiles |
| GET | `/api/v1/users/{user_id}` | Fetch single saved user profile |
| POST | `/api/v1/ops/crawl-refresh` | Run corpus crawl/ingestion refresh |
| POST | `/api/v1/ops/subset-refresh` | Refresh topic and persona subsets |
| GET | `/api/v1/ops/freshness-metrics` | Freshness and staleness metrics |
| GET | `/api/v1/ops/run-summaries` | Recent operational run summaries |
| GET | `/api/v1/ops/compliance/snapshots` | Recent compliance evidence snapshots |
| GET | `/api/v1/ops/compliance/report` | Aggregate compliance report |
| GET | `/api/v1/health` | Health check with model routing info |
| GET | `/api/v1/audit/{session_id}` | Full audit trail for any session |

## Architecture

15 agents across 3 pipelines, orchestrated with Google ADK patterns:

```
Scenario 1 (Navigator):    Ingest -> Extract -> Cluster -> Synthesise -> Q&A -> Engagement
Scenario 2 (Feed):         Profile -> Rank -> Adapt (x2 personas in parallel)
Scenario 3 (Video):        Ingest -> Script -> FactCheck -> ScenePlan -> LangValidate -> Audio -> Video
```

UI layout: Tab 1 News Navigator, Tab 2 My ET onboarding, Tab 3 Personalised Feed, Tab 4 Vernacular Video (+ Settings page for ops/compliance/measurement).

See [architecture.md](architecture.md) for the full architecture document with diagrams.

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Agent Framework | Google ADK 1.18.0 |
| LLMs | NVIDIA Nemotron + Llama-4 (primary), Gemini (fallback), Ollama (local) |
| Backend | FastAPI + Uvicorn |
| Frontend | Streamlit |
| Vernacular TTS | edge-tts (language-specific voices) |
| Video | Pillow + ffmpeg |
| Vector Search | ChromaDB |
| Data Models | Pydantic v2 |

## Impact

- **95% reduction** in news consumption time (45 min -> 2 min)
- **240x faster** vernacular video production at 99.99% lower cost
- **77% cost reduction** through smart model routing
- **7 languages** serving 30M+ underserved vernacular users
- **Rs 175+ crore/year** combined revenue opportunity for ET

See [IMPACT_MODEL.md](IMPACT_MODEL.md) for detailed calculations.

## Supported Languages

| Language | Script | TTS Voice | Status |
|----------|--------|-----------|--------|
| English | Latin | en-IN-NeerjaNeural | Full support |
| Hindi | Devanagari | hi-IN-SwaraNeural | Full support |
| Marathi | Devanagari | mr-IN-AarohiNeural | Full support |
| Tamil | Tamil | ta-IN-PallaviNeural | Full support |
| Telugu | Telugu | te-IN-ShrutiNeural | Full support |
| Kannada | Kannada | kn-IN-SapnaNeural | Full support |
| Bhojpuri | Devanagari | hi-IN-SwaraNeural (fallback) | Text + fallback voice |
| Punjabi | Gurmukhi | pa-IN-OjasNeural | Full support |

---

Built for ET AI Hackathon 2026 | Track 8: AI-Native News Experience
