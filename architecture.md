# Architecture Document — ET AI News Navigator

## Track 8: AI-Native News Experience | ET AI Hackathon 2026

---

## System Overview

The ET AI News Navigator is a **15-agent multi-agent system** that transforms how business news is consumed. It processes raw news articles through autonomous agent pipelines to deliver three distinct experiences:

1. **News Navigator** — Synthesises 22+ articles into an interactive, angle-based intelligence briefing with non-overlapping Q&A
2. **Personalised Feed** — Generates meaningfully different content surfaces for different user personas, with engagement-aware retuning
3. **Vernacular Video** — Converts breaking news into a chaptered, fact-checked explainer video in **7 Indian languages** in under 60 seconds

---

## Architecture Diagram

```
                              +---------------------------+
                              |     Streamlit Frontend     |
                              |  Tab 1 | Tab 2 | Tab 3    |
                              +---------------------------+
                                         |
                              +---------------------------+
                              |     FastAPI Gateway        |
                              |  /briefing /feed /video    |
                              +---------------------------+
                                         |
               +-------------------------+---------------------------+
               |                         |                           |
     Scenario 1: Navigator      Scenario 2: Feed           Scenario 3: Video
     (5 agents, sequential)     (3 agents x2, parallel)    (7 agents, sequential)
               |                         |                           |
    +----------+----------+    +---------+---------+    +------------+-----------+
    |                     |    |                   |    |                        |
    v                     v    v                   v    v                        v
 ArticleIngestor      SynthesisEngine  UserProfiler(x2)  BreakingIngestor     ScenePlanner
 [Flash]              [Pro]            [Flash]            [Flash]              [Flash]
    |                     |              |                    |                    |
    v                     v              v                    v                    v
 EntityExtractor      QueryResponder  ContentRanker(x2)   ScriptWriter       LanguageValidator
 [Flash]              [Pro]           [Flash]             [Pro]              [Flash, conditional]
    |                                    |                    |                    |
    v                                    v                    v                    v
 AngleClustering                   ContentAdapter(x2)     FactChecker        AudioGenerator
 [Pro]                             [Pro]                  [Flash]            [edge-tts, per-scene]
                                                              |                    |
                                        EngagementTracker     v                    v
                                        [local, cross-session]  ArticleVisualFetcher  VideoComposer
                                                              [httpx]            [PIL+ffmpeg]
```

---

## Smart Model Routing (Cost Efficiency)

A deterministic routing table assigns each task type to the optimal model — **no LLM-based router overhead**:

| Task Type | Model | Cost | Rationale |
|-----------|-------|------|-----------|
| Extraction, NER, classification | Gemini 2.0 Flash | $0.10/M tokens | Fast, structured output |
| Ranking, fact-checking, scene planning | Gemini 2.0 Flash | $0.10/M tokens | Comparison/structuring tasks |
| Language validation | Gemini 2.0 Flash | $0.10/M tokens | Conditional — only runs when leakage detected |
| Multi-article synthesis | Gemini 2.0 Pro | $1.25/M tokens | Requires editorial judgment |
| Creative writing (vernacular) | Gemini 2.0 Pro | $1.25/M tokens | Nuance, cultural adaptation |
| Creative writing (multilingual scripts) | Gemini 2.0 Pro | $1.25/M tokens | Nuance, cultural adaptation |
| Fallback / degradation | Ollama qwen2.5vl:3b | $0.00 (local) | Enterprise resilience |

**Estimated cost per full pipeline run**: ~$0.08 (vs ~$0.35 if all tasks used Pro)
**Cost reduction**: **77% through smart routing**

Each agent step logs estimated token count and USD cost in the audit trail, making the cost saving verifiable.

---

## Agent Roles & Communication

### Scenario 1: News Navigator (5 agents + engagement tracker)

| # | Agent | Model | Input | Output | Key Behaviour |
|---|-------|-------|-------|--------|---------------|
| 1 | ArticleIngestor | Flash | 22 raw articles | Structured metadata + summaries | Extracts entities, categories, sentiment per article |
| 2 | EntityExtractor | Flash | Article metadata | Entity-to-article index | Normalises names, builds cross-article lookup |
| 3 | AngleClustering | Pro | Metadata + entities | 5-7 angle clusters | Editorial judgment on angle separation, minimises overlap |
| 4 | SynthesisEngine | Pro | Angle clusters + full articles | Dense synthesis per angle | Non-overlapping, source-cited, with key takeaways |
| 5 | QueryResponder | Pro | Question + full history | Targeted answer | Receives all previous answers, guarantees no repetition |
| 6 | EngagementTracker | Local | User clicks, queries, dwell time | Retuned angle ordering | Cross-session learning, no LLM cost |

**Inter-agent communication**: Sequential pipeline with shared state. QueryResponder receives the complete synthesis history and all previous Q&A to guarantee non-overlapping answers. EngagementTracker logs interaction signals and feeds back into angle/content ranking for subsequent sessions.

### Scenario 2: Personalised Feed (3 agent types x 2 personas)

| # | Agent | Model | Key Behaviour |
|---|-------|-------|---------------|
| 1 | UserProfiler | Flash | Converts profile → content depth, format, tone, jargon level, priority topics |
| 2 | ContentRanker | Flash | Ranks articles by persona-specific relevance (0-1 score + reason) |
| 3 | ContentAdapter | Pro | Rewrites content: CFO gets exec summaries + data tables; beginner gets ELI5 + analogies |

**Runs in parallel** for both personas. Delta summary quantifies differences (story overlap, format changes, reading level shift).

### Scenario 3: Vernacular Video (7 agents, 7 languages, <60s)

| # | Agent | Model | Key Behaviour |
|---|-------|-------|---------------|
| 1 | UserProfiler | Flash | Converts profile JSON to content delivery preferences |
| 2 | ContentRanker | Flash | Ranks articles by persona-specific relevance |
| 3 | ContentAdapter | Pro | Rewrites content: CFO gets data tables, beginner gets ELI5 |

**Runs in parallel** for both personas, then compares outputs.

### Scenario 3: Vernacular Video (5 agents, <60s budget)

| # | Agent | Model | Time Budget | Key Behaviour |
|---|-------|-------|-------------|---------------|
| 1 | BreakingIngestor | Flash | ~2s | 5W1H extraction |
| 2 | ScriptWriter | Pro | ~8s | Hindi script, no English jargon, cultural analogies |
| 3 | FactChecker | Flash | ~3s | Claim-by-claim verification against source |
| 4 | AudioGenerator | edge-tts | ~15s | Hindi TTS (hi-IN-SwaraNeural) |
| 5 | VideoComposer | PIL+ffmpeg | ~15s | Visual frames + audio → MP4 |

---

## Error Handling & Enterprise Readiness

### Three-Tier Fallback Chain

```
Gemini Pro/Flash → (rate limit/error) → Retry once → Ollama qwen2.5vl:3b (local)
                                                    → (if Ollama down) → Heuristic/deterministic fallback
```

### Graceful Degradation by Scenario

| Component Failure | Degraded Output | User Experience |
|-------------------|-----------------|-----------------|
| Gemini API down | Ollama handles extraction; heuristic fallbacks for synthesis | Warning banner, partial results |
| LLM returns sparse data | Heuristic enrichment fills key_numbers, impact_points from article text | Complete output, slightly less nuanced |
| TTS voice unavailable | Fallback voice chain per language; text-only if all fail | Script readable, degraded audio |
| ffmpeg fails | Audio + frames returned separately | Audio playable, frames viewable |
| Language leakage | LanguageValidator corrects; deterministic cleanup as last resort | Clean output in target language |
| Timeout (>90s) | Return whatever completed | Partial results with status |

### Audit Trail with Cost Tracking

Every agent step logs:
- Agent name, action, model used
- Input/output summaries (truncated to 200 chars)
- Latency in milliseconds
- **Estimated token count (input + output)**
- **Estimated cost in USD**
- Status (success/fallback/error)
- Error details if applicable

Audit trails are returned with every API response and displayed in the UI with cumulative cost per pipeline run.

---

## Technology Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| Agent Framework | Google ADK 1.18.0 | Native Gemini integration, SequentialAgent/ParallelAgent patterns |
| LLMs | Gemini 2.0 Pro + Flash | Smart routing for cost efficiency |
| Local Fallback | Ollama + qwen2.5vl:3b | Zero-cost degradation, enterprise resilience |
| Backend | FastAPI 0.115.9 | Async-native, OpenAPI docs |
| Frontend | Streamlit 1.48.1 | Rapid prototyping, 3-tab interface |
| Graph Visualization | Plotly 5.0.0 | Interactive, hoverable entity-angle network graphs |
| TTS | edge-tts 7.2.8 | 8 Indian languages with language-specific voices |
| Video | Pillow + ffmpeg 8.0 | Frame generation + composition |
| Vector Store | ChromaDB 1.0.11 | Article embeddings (available for extension) |

---

## Frontend UI Features

The Streamlit interface exposes all three pipelines through a 3-tab design with integrated visualization and controls:

### Tab 1: News Navigator
- **Briefing Generation**: Topic input with optional topic coverage enforcement
- **Angle-based Navigation**: Non-overlapping summary per angle with metadata
- **Entity Graph**: Interactive Plotly network visualization showing:
  - Entity nodes (left arc) with hoverable metadata: name, type, article count, related angles
  - Angle nodes (right lane) with connection details
  - Automatic fallback to Graphviz if Plotly unavailable
- **Entity Explorer**: Dropdown selector to drill into specific entities and their connected angles
- **Follow-up Q&A**: Ask clarifying questions on the briefing (history-aware, non-repeating answers)
- **Engagement Metrics**: Article count, angle count, pipeline latency, estimated cost

### Tab 2: Personalised Feed
- **Persona Selection**: CFO vs. Young Investor profiles (extensible)
- **Side-by-side Comparison**: Delta summary showing story overlap, format changes, reading level
- **Adaptive Content**: Persona-specific rewrites (depth, tone, jargon, visualizations)

### Tab 3: Vernacular Video
- **Language Selection**: 8 languages with native voices (Hindi, Marathi, Tamil, Telugu, Kannada, Bhojpuri, Punjabi, English)
- **Video Generation**: Chaptered explainer video with fact-checked narration
- **Scene Viewer**: Timeline visualization with chapter metadata

### Settings Page
- **Runtime Flags**: Visibility into Retrieval Contracts and Corpus Kill Switch status
- **Ops Controls**: Crawl refresh, subset refresh, freshness metrics, recent run summaries
- **Compliance Controls**: Load compliance snapshots, generate compliance reports

---

## Data Flow: News Navigator

```
[22 Raw Articles] → ArticleIngestor [Flash] → [Structured Metadata]
        → EntityExtractor [Flash] → [Entity-Article Index]
        → AngleClustering [Pro] → [5-7 Non-overlapping Angles]
        → SynthesisEngine [Pro] → [Dense Synthesis per Angle]
        → QueryResponder [Pro] ← [User Questions + Full History]
        → [Non-overlapping, Source-cited Answers]
        → EngagementTracker ← [Click/Query/Dwell Signals]
```

## Data Flow: Vernacular Video

```
[Breaking Article] → BreakingIngestor [Flash] → [5W1H Facts + Key Numbers]
        → ScriptWriter [Pro] → [Language-aware Script]
        → FactChecker [Flash] → [Claim-by-claim Verification]
        → ScenePlanner [Flash] → [6-10 Chaptered Scenes + Story Arc]
        → LanguageValidator [Flash, conditional] → [Clean Target-language Output]
        → AudioGenerator [edge-tts] → [Per-scene Audio + Merged Narration]
        → VideoComposer [PIL+ffmpeg] → [Chaptered MP4 with A/V Sync]
```
