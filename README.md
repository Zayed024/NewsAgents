# ET AI News Navigator

**Track 8: AI-Native News Experience | ET AI Hackathon 2026**

A **15-agent multi-agent system** that transforms how business news is consumed — from static, one-size-fits-all articles to interactive, personalised, multilingual experiences.

## What It Does

| Scenario | Description | Agents |
|----------|-------------|--------|
| **News Navigator** | Synthesises 22 Union Budget articles into an interactive briefing with 6 navigable angles, non-overlapping Q&A, and engagement-aware retuning | 7 (Ingestor, EntityExtractor, AngleClustering, Synthesizer, QueryResponder, ChromaDB, EngagementTracker) |
| **Personalised Feed** | Same articles, completely different experience for a CFO vs a 24-year-old first-time investor — different depth, format, framing | 6 (Profiler x2, Ranker x2, Adapter x2) |
| **Vernacular Video** | Breaking news to chaptered, fact-checked explainer video in **7 Indian languages** in under 60 seconds | 7 (BreakingIngestor, ScriptWriter, FactChecker, ScenePlanner, LanguageValidator, AudioGenerator, VideoComposer) |

## Key Differentiators

- **Smart Model Routing**: Gemini Flash for extraction, Gemini Pro for synthesis, Ollama for fallback — **77% cost reduction**
- **15 Specialised Agents**: Clear role separation with handoff protocols across 3 pipelines
- **Interactive Entity Graph**: Hoverable Plotly network visualization showing entity-angle relationships with metadata drill-down
- **8 Languages**: Hindi, Marathi, Tamil, Telugu, Kannada, Bhojpuri, Punjabi, English — with language-specific TTS voices and writing systems
- **Engagement Tracking**: Cross-session learning retunes content delivery without LLM cost (extra credit feature)
- **Story Arc Depth**: Chaptered videos with sentiment tracking, contrarian perspectives, and "what to watch next"
- **Full Audit Trail**: Every agent step logged with model, latency, token count, and estimated cost

## Quick Start

### Prerequisites
- Python 3.11+
- Gemini API key
- ffmpeg (for video generation)
- Ollama with `qwen2.5vl:3b` (optional, for fallback)

### Setup

```bash
git clone https://github.com/Zayed024/NewsAgents.git
cd NewsAgents
pip install -r requirements.txt

# Set API key
export GOOGLE_API_KEY=your_key_here     # Linux/Mac
set GOOGLE_API_KEY=your_key_here        # Windows

# Optional: Start Ollama for fallback
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
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/navigator/briefing` | Generate full News Navigator briefing |
| POST | `/api/v1/navigator/query` | Ask follow-up question on briefing |
| POST | `/api/v1/feed/compare` | Generate side-by-side persona feeds |
| POST | `/api/v1/video/generate` | Generate vernacular explainer video |
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

See [architecture.md](architecture.md) for the full architecture document with diagrams.

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Agent Framework | Google ADK 1.18.0 |
| LLMs | Gemini 2.0 Pro + Flash, Ollama qwen2.5vl:3b |
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
