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

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/navigator/briefing` | Generate full News Navigator briefing |
| POST | `/api/v1/navigator/query` | Ask follow-up question on briefing |
| POST | `/api/v1/feed/compare` | Generate side-by-side persona feeds |
| POST | `/api/v1/video/generate` | Generate Hindi explainer video |
| GET | `/api/v1/health` | Health check with model routing info |
| GET | `/api/v1/audit/{session_id}` | Full audit trail for any session |

## Project Structure

```
ET/
├── src/
│   ├── agents/
│   │   ├── navigator/     # Scenario 1: 5 agents (Ingestor, EntityExtractor, AngleClustering, Synthesizer, QueryResponder)
│   │   ├── persona_feed/  # Scenario 2: 3 agents (Profiler, Ranker, Adapter)
│   │   └── video/         # Scenario 3: 5 agents (BreakingIngestor, ScriptWriter, FactChecker, AudioGen, VideoComposer)
│   ├── api/               # FastAPI endpoints
│   ├── tools/             # Shared tools (article loader, Ollama fallback, TTS)
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
