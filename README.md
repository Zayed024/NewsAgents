# ET AI News Navigator

**Track 8: AI-Native News Experience | ET AI Hackathon 2026**

A multi-agent AI system that transforms how business news is consumed — from static, one-size-fits-all articles to interactive, personalised, multilingual experiences.

## What It Does

| Scenario | Description | Demo |
|----------|-------------|------|
| **News Navigator** | Synthesises 22 Union Budget articles into an interactive briefing with 6 navigable angles and non-overlapping Q&A | Primary showcase |
| **Personalised Feed** | Same articles, completely different experience for a CFO vs a 24-year-old first-time investor | Side-by-side comparison |
| **Vernacular Video** | Breaking news → 60-90s Hindi explainer video in under 60 seconds, fact-checked against source | Full autonomous pipeline |

## Architecture

12 specialised agents across 3 pipelines, orchestrated with Google ADK:

- **Smart Model Routing**: Gemini Flash for extraction/classification, Gemini Pro for synthesis/reasoning, Ollama for fallback — 77% cost reduction vs all-Pro
- **Enterprise Readiness**: Audit trails on every step, 3-tier fallback chain, graceful degradation
- **Autonomy**: Each pipeline runs end-to-end without human intervention

See [architecture.md](architecture.md) for the full architecture document.

## Quick Start

### Prerequisites
- Python 3.11+
- Gemini API key (set as `GOOGLE_API_KEY` environment variable)
- Ollama with `qwen2.5vl:3b` model (optional, for fallback)
- ffmpeg (for video generation)

### Setup

```bash
# Clone and install
git clone <repo-url>
cd ET
pip install -r requirements.txt

# Set API key
export GOOGLE_API_KEY=your_key_here  # Linux/Mac
set GOOGLE_API_KEY=your_key_here     # Windows

# Start Ollama (optional, for fallback)
ollama serve &
ollama pull qwen2.5vl:3b
```

### Run the Streamlit App

```bash
streamlit run ui/app.py
```

### Run the FastAPI Server

```bash
uvicorn src.api.main:app --reload --port 8000
```

API docs available at: http://localhost:8000/docs

## Current Capabilities

- Interactive deep briefing generation with angle-wise exploration and follow-up Q&A.
- Topic coverage mode that scans available corpus articles before briefing synthesis.
- Entity Explorer to navigate entities to related angles and source article clusters.
- Store-backed corpus retrieval option in addition to bundled static demo datasets.
- Hybrid relevance filtering with explainable inclusion/exclusion reasons in navigator outputs.

For implementation roadmap, completed phases, and pending plan, see [IMPLEMENTATION_PHASES_STATUS.md](IMPLEMENTATION_PHASES_STATUS.md).

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/navigator/briefing` | Generate full News Navigator briefing |
| POST | `/api/v1/navigator/query` | Ask follow-up question on briefing |
| POST | `/api/v1/feed/compare` | Generate side-by-side persona feeds |
| POST | `/api/v1/video/generate` | Generate Hindi explainer video |
| POST | `/api/v1/ops/crawl-refresh` | Run corpus crawl/ingestion refresh |
| POST | `/api/v1/ops/subset-refresh` | Refresh topic and persona subsets |
| GET | `/api/v1/ops/freshness-metrics` | Freshness and staleness metrics |
| GET | `/api/v1/ops/run-summaries` | Recent operational run summaries |
| GET | `/api/v1/ops/compliance/snapshots` | Recent compliance evidence snapshots |
| GET | `/api/v1/ops/compliance/report` | Aggregate compliance report |
| GET | `/api/v1/health` | Health check with model routing info |
| GET | `/api/v1/audit/{session_id}` | Full audit trail for any session |

## Operations Runner (Phase 4)

Use the CLI runner for scheduler integration (Task Scheduler/cron):

```bash
# Crawl + ingest refresh
python -m src.tools.corpus.operations_runner crawl-refresh --topic "Union Budget 2026" --max-pages 60 --max-depth 2

# Refresh topic/persona subsets
python -m src.tools.corpus.operations_runner subset-refresh --topics "Union Budget 2026" --profiles cfo_profile young_investor_profile

# Compute freshness metrics only
python -m src.tools.corpus.operations_runner freshness-metrics --topic-stale-after 120 --persona-stale-after 180

# Show compliance snapshots
python -m src.tools.corpus.operations_runner compliance-snapshots --limit 100

# Generate compliance report
python -m src.tools.corpus.operations_runner compliance-report --limit 500
```

Compliance controls:

- Set `CORPUS_KILL_SWITCH=1` to force safe fallback/deny behavior for corpus ingestion and topic retrieval.
- Set `CORPUS_KILL_SWITCH=0` (or unset) for normal operation.

## Project Structure

```
ET/
├── src/
│   ├── agents/
│   │   ├── navigator/     # Scenario 1: 5 agents (Ingestor, EntityExtractor, AngleClustering, Synthesizer, QueryResponder)
│   │   ├── persona_feed/  # Scenario 2: 3 agents (Profiler, Ranker, Adapter)
│   │   └── video/         # Scenario 3: 5 agents (BreakingIngestor, ScriptWriter, FactChecker, AudioGen, VideoComposer)
│   ├── api/               # FastAPI endpoints
│   ├── tools/             # Shared tools (article loader, corpus provider/store/crawler, Ollama fallback, TTS)
│   ├── config.py          # Configuration and model routing
│   ├── models.py          # Pydantic schemas
│   ├── llm.py             # Unified LLM interface with fallback
│   ├── model_router.py    # Smart routing table
│   └── audit.py           # Audit trail system
├── ui/
│   └── app.py             # Streamlit 3-tab frontend
├── data/                  # Sample datasets (22 budget articles, profiles, breaking news)
├── assets/fonts/          # Hindi font for video frames
├── architecture.md        # Architecture document
├── IMPACT_MODEL.md        # Business impact quantification
└── requirements.txt
```

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Agent Framework | Google ADK 1.18.0 |
| LLMs | Gemini 2.0 Pro + Flash, Ollama qwen2.5vl:3b |
| Backend | FastAPI + Uvicorn |
| Frontend | Streamlit |
| Hindi TTS | edge-tts (hi-IN-SwaraNeural) |
| Video | Pillow + ffmpeg |
| Data Models | Pydantic v2 |

## Impact

- **95% reduction** in news consumption time (45 min → 2 min)
- **240x faster** vernacular video production
- **77% cost reduction** through smart model routing
- **Rs 100+ crore/year** revenue opportunity for ET

See [IMPACT_MODEL.md](IMPACT_MODEL.md) for detailed calculations.

---

Built for ET AI Hackathon 2026 by a solo developer.
