# Architecture Document — ET AI News Navigator

## Track 8: AI-Native News Experience | ET AI Hackathon 2026

---

## System Overview

The ET AI News Navigator is a multi-agent system that transforms how business news is consumed. It processes raw news articles through autonomous agent pipelines to deliver three distinct experiences:

1. **News Navigator** — Synthesises 22+ articles into an interactive, angle-based intelligence briefing
2. **Personalised Feed** — Generates meaningfully different content surfaces for different user personas
3. **Vernacular Video** — Converts breaking news into a Hindi explainer video in under 60 seconds

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
               +-------------------------+-------------------------+
               |                         |                         |
     Scenario 1: Navigator      Scenario 2: Feed         Scenario 3: Video
     (SequentialAgent)           (Parallel)               (SequentialAgent)
               |                         |                         |
    +----------+----------+    +---------+---------+    +----------+----------+
    |                     |    |                   |    |                     |
    v                     v    v                   v    v                     v
 ArticleIngestor      SynthesisEngine  UserProfiler(x2) BreakingIngestor  AudioGenerator
 [Flash]              [Pro]            [Flash]           [Flash]           [edge-tts]
    |                     |              |                   |                |
    v                     v              v                   v                v
 EntityExtractor      QueryResponder  ContentRanker(x2)  ScriptWriter     VideoComposer
 [Flash]              [Pro]           [Flash]            [Pro]            [PIL+ffmpeg]
    |                                    |                   |
    v                                    v                   v
 AngleClustering                   ContentAdapter(x2)    FactChecker
 [Pro]                             [Pro]                 [Flash]
```

---

## Smart Model Routing (Cost Efficiency)

A deterministic routing table assigns each task type to the optimal model:

| Task Type | Model | Cost | Rationale |
|-----------|-------|------|-----------|
| Extraction, NER, classification | Gemini 2.0 Flash | $0.10/M tokens | Fast, structured output |
| Ranking, fact-checking | Gemini 2.0 Flash | $0.10/M tokens | Comparison tasks |
| Multi-article synthesis | Gemini 2.0 Pro | $1.25/M tokens | Requires editorial judgment |
| Creative writing (Hindi) | Gemini 2.0 Pro | $1.25/M tokens | Nuance, cultural adaptation |
| Fallback / degradation | Ollama qwen2.5vl:3b | $0.00 (local) | Enterprise resilience |

**Estimated cost per full pipeline run**: ~$0.08 (vs $0.35 if all tasks used Pro)
**Cost reduction**: 77% through smart routing

---

## Agent Roles & Communication

### Scenario 1: News Navigator (12 agents total across system, 5 here)

| # | Agent | Model | Input | Output | Key Behaviour |
|---|-------|-------|-------|--------|---------------|
| 1 | ArticleIngestor | Flash | 22 raw articles | Structured metadata + summaries | Extracts entities, categories, sentiment |
| 2 | EntityExtractor | Flash | Article metadata | Entity-to-article index | Normalises entity names, builds lookup |
| 3 | AngleClustering | Pro | Metadata + entities | 5-7 angle clusters | Editorial judgment on angle separation |
| 4 | SynthesisEngine | Pro | Angle clusters + full articles | Dense synthesis per angle | Non-overlapping, source-cited |
| 5 | QueryResponder | Pro | User question + history | Targeted answer | Receives full history, ensures no repetition |

**Inter-agent communication**: Pipeline state flows sequentially. Each agent reads from and writes to a shared state object. The QueryResponder receives the complete synthesis history and all previous Q&A to guarantee non-overlapping answers.

### Scenario 2: Personalised Feed (3 agent types, 6 instances)

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
                                                    → (if Ollama down) → Graceful degradation
```

### Graceful Degradation by Scenario

| Component Failure | Degraded Output | User Experience |
|-------------------|-----------------|-----------------|
| Gemini API down | Ollama handles extraction; synthesis uses cached/basic output | Warning banner, partial results |
| TTS fails | Script text displayed without audio | Script readable, no video |
| ffmpeg fails | Audio + frames returned separately | Audio playable, frames viewable |
| Timeout (>90s) | Return whatever completed | Partial results with status |

### Audit Trail

Every agent step logs:
- Agent name, action, model used
- Input/output summaries (truncated to 200 chars)
- Latency in milliseconds
- Status (success/fallback/error)
- Error details if applicable

Audit trails are returned with every API response and displayed in the UI.

---

## Technology Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| Agent Framework | Google ADK 1.18.0 | Native Gemini integration, SequentialAgent/ParallelAgent patterns |
| LLMs | Gemini 2.0 Pro + Flash | Smart routing for cost efficiency |
| Local Fallback | Ollama + qwen2.5vl:3b | Zero-cost degradation, enterprise resilience |
| Backend | FastAPI 0.115.9 | Async-native, OpenAPI docs |
| Frontend | Streamlit 1.48.1 | Rapid prototyping, 3-tab interface |
| TTS | edge-tts 7.2.8 | Free Hindi voices, natural prosody |
| Video | Pillow + ffmpeg 8.0 | Frame generation + composition |
| Vector Store | ChromaDB 1.0.11 | Article embeddings (available for extension) |

---

## Data Flow Summary

```
[Raw Articles JSON]
        |
        v
  ArticleIngestor ──> [Structured Metadata]
        |
        v
  EntityExtractor ──> [Entity Index]
        |
        v
  AngleClustering ──> [5-7 Angle Clusters]
        |
        v
  SynthesisEngine ──> [Dense Synthesis per Angle]
        |
        v
  QueryResponder  <── [User Questions]
        |
        v
  [Non-overlapping, Source-cited Answers]
```
