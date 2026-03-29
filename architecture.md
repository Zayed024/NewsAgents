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
| 1 | BreakingIngestor | Flash | 5W1H extraction + heuristic enrichment for sparse LLM output |
| 2 | ScriptWriter | Pro | Language-aware script with cultural analogies, localized fallbacks for 7 languages |
| 3 | FactChecker | Flash | Claim-by-claim verification against source, accuracy score |
| 4 | ScenePlanner | Flash | Chaptered scene plan (6-10 scenes) with story arc, sentiment shifts, contrarian view, watch-next |
| 5 | LanguageValidator | Flash | Conditional — detects and corrects English leakage in non-English scripts |
| 6 | AudioGenerator | edge-tts | Per-scene TTS with concurrent generation, duration-aware padding, voice fallback chains |
| 7 | VideoComposer | PIL+ffmpeg | Chapter frames with progress bars, article image backgrounds, timeline scenes, A/V sync |
| — | ArticleVisualFetcher | httpx | Scrapes og:image/twitter:image from source URL for video backgrounds |

**Supported languages**: Hindi, Marathi, Tamil, Telugu, Kannada, Bhojpuri, Punjabi — each with dedicated TTS voice, font, writing hints, and localized fallback templates.

**Story arc metadata**: Each video includes story arc summary, key players, sentiment shifts, contrarian perspective, and "what to watch next" signals — fulfilling the Track 8 requirement for narrative depth.

---

## Engagement Tracking (Extra Credit)

The EngagementTracker is a cross-session learning module that:

1. **Logs signals**: Which angles users click, which questions they ask, dwell time per synthesis, feed items clicked
2. **Builds preferences**: Per-user interest vector that evolves across sessions
3. **Retunes delivery**: Adjusts angle ordering in Navigator, article ranking in Feed, content depth dynamically
4. **Zero LLM cost**: Purely local computation — no API calls, no latency impact

This directly addresses the Track 8 extra credit: *"agents that track user engagement signals and retune content delivery in subsequent sessions."*

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
| TTS | edge-tts 7.2.8 | Free multilingual voices (Hindi, Marathi, Tamil, Telugu, Kannada) |
| Video | Pillow + ffmpeg 8.0 | Frame generation + chapter composition with A/V sync |
| Vector Store | ChromaDB 1.0.11 | Article embeddings for semantic search in Q&A |
| Engagement | Local JSON store | Cross-session user preference learning |

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
