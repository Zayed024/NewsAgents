# NewsAgents Implementation Phases

Last updated: 2026-03-29 21:05 UTC

---

## Track A: My ET — Personalized Feed Feature Roadmap

This tracks the implementation of **Phase 1–7** for the "My ET" personalized feed feature, which enables users to create profiles, receive tailored feeds, and continuously improve recommendations.

### Phase Status Summary

| Phase | Feature | Status | Validation |
|-------|---------|--------|-----------|
| **Phase 1** | User Creation + Onboarding UI | ✅ **COMPLETE** | 5/5 tests passing; 3 profiles in system |
| **Phase 2** | Profile-Aware Corpus Personalization | ✅ **COMPLETE** | 8/8 tests passing; segment caching working |
| **Phase 3** | Single-User Feed API + Streamlit UI | ✅ **COMPLETE** | 6/6 structural tests passing; A/B comparison ready |
| **Phase 4** | Card Feedback Loop (Interested/Not) | ✅ **COMPLETE** | 8/8 tests passing; feedback UI integrated in Tab 3 |
| **Phase 5** | Adaptive Learning + Cold Start | ✅ **COMPLETE** | 8/8 tests passing; feedback signals integrated into ranker |
| **Phase 6** | Experience Quality UX Upgrades | ✅ **COMPLETE** | 8/8 Phase 6 tests passing; sectioned + metadata-rich Tab 3 |
| **Phase 7** | Measurement + A/B Tests | ✅ **COMPLETE** | A/B persistence, summary metrics, settings dashboard, runbook |

---

### Phase 1: ✅ User Creation & Onboarding (COMPLETE)

**Delivered:**
- `src/agents/onboarding.py` with question framework
  - QUICK_START_QUESTIONS (4 q's): role, experience, interests, content preference
  - DEEP_SETUP_QUESTIONS (6 q's): age, risk, portfolio, frequency, learning goal, languages
- Answer-to-preference-vector conversion (deterministic, no LLM cost)
- Answer-to-UserProfile conversion with sensible defaults
- User profile persistence to `data/user_profiles/*.json`
- API endpoints:
  - `GET /api/v1/onboarding/questions` – returns question set
  - `POST /api/v1/users/create` – saves new profile
  - `GET /api/v1/users` – list all users
  - `GET /api/v1/users/{user_id}` – fetch one user
- Streamlit UI: Tab 2 "My ET — Create Your Profile"
  - Step 1: Mode selection (quick/deep)
  - Step 2: Guided questionnaire with validation
  - Step 3: Success page + profile summary

**Test Coverage:**
- Questions structure (quick + deep)
- Preference vector generation
- Answer-to-profile conversion
- Save/load cycle
- List operation
- 3 test profiles created (including test-user-001)

**Acceptance Criteria Met:**
- ✅ No manual JSON editing required
- ✅ Saved users reappear in selectable profile list
- ✅ Preference vectors stored alongside profiles
- ✅ Quick start ~2 minutes, deep setup ~5 minutes

**Still Open (for Phase 2+):**
- Answers don't yet drive corpus crawl intents
- Feed not yet personalized (still comparison demo)
- No engagement tracking yet for new users

---

### Phase 2: ✅ Profile-Aware Corpus Personalization (COMPLETE)

**Delivered:**
- `src/agents/corpus_personalizer.py`: Deterministic profile→corpus mapping
  - `profile_to_crawl_queries()`: UserProfile → keywords, sectors, intent_types
  - `profile_to_subset_tags()`: UserProfile → relevance_topic, audience_level, intent_type, content_filter
  - Interest-to-keyword mappings: 8 categories → 200+ ET-specific keywords
  - Role-to-intent mappings: 5 roles → specialized intent types (explainer, market_move, portfolio_action, etc.)
  - Experience-to-sector mappings: depth guidance per investing experience level
  - Risk-to-content filtering: conservative/moderate/aggressive content preferences
- `src/agents/profile_subset_builder.py`: Profile-specific corpus subsetting
  - `build_profile_specific_subset()`: Filter + tag articles for user
  - `save_profile_subset()` / `load_profile_subset()`: Per-user subset persistence
  - `save_segment_subset()` / `load_segment_subset()`: Segment-level cache (2-hour freshness)
  - `get_articles_for_user()`: Integrated fallback logic (user → segment → fresh)
- API endpoint:
  - `POST /api/v1/feed/personalized` – fetch user's personalized articles + intents + tags
- All conversions deterministic + rule-based (no LLM cost)

**Architecture Highlights:**
- **Segment-Based Caching:** Users grouped by role_segment + reading_level
  - Example: "student_beginner", "professional_expert", "entrepreneur_advanced"
  - N users in same segment = N × cost savings from shared crawl results
- **Article Tagging Pipeline:** Every article tagged with
  - `audience:{beginner|intermediate|expert}`
  - `intent:{explainer|market_move|portfolio_action|...}`
  - `relevance:{high|medium|low}` (based on keyword overlap)
- **Two-Level Filtering:**
  1. Keyword filter: include if ≥1 user keyword matches article
  2. Relevance sort: high-relevance articles ranked first

**Test Coverage:**
- ✅ 8/8 unit + integration tests passing
- ✅ Profile→crawl_queries conversion validated
- ✅ Article filtering by user interests verified
- ✅ Segment caching & reuse confirmed
- ✅ Save/load persistence tested
- ✅ Cache fallback logic (user → segment → fresh) tested

**Acceptance Criteria Met:**
- ✅ Onboarding answers now drive deterministic corpus queries
- ✅ Crawler returns segment-specific subsets (2+ users = shared results)
- ✅ Articles tagged with profile relevance, audience, intent
- ✅ Feed can now use personalized subset instead of generic homepage
- ✅ Cost optimized through 2-level caching

**Segment Mapping Examples:**
- **Student + Beginner** → SIP, ELSS, mutual fund basics
- **Professional + Intermediate** → market moves, portfolio actions, broad sectors
- **Entrepreneur + Expert** → competitor tracking, funding news, startup trends
- **Retiree + Expert** → bond yields, dividend stocks, income-focused content

**Known Limitations (for Phase 3+):**
- Articles filtered but not yet adapted (ranking returned, not synthesis)
- No engagement-based dynamic retagging
- Segment boundaries fixed (no clustering updates)
- Tags don't update as user provides feedback

---

### Phase 3: ✅ Single-User Personalized Feed Pipeline (COMPLETE)

**Delivered:**
- `src/agents/personalized_feed_pipeline.py`: Full integration of Phase 2 subsets with existing agents
  - `generate_personalized_user_feed()`: Async pipeline combining profiler → ranker → adapter
    - Input: Phase 2 personalized subset (interest-filtered articles)
    - Step 1: Analyze profile with profiler agent (extract preferences)
    - Step 2: Rank articles with ranker agent (calculate relevance scores)
    - Step 3: Adapt articles with adapter agent (rewrite for depth + format)
    - Step 4: Build explanations (why shown, relevance, confidence, matched tags)
    - Output: PersonaFeed with adapted FeedItems + explanations + audit trail
  - `compare_personalized_vs_baseline()`: A/B test comparison
    - Generates both personalized (Phase 2 aware) and baseline (generic) feeds
    - Returns delta_metrics: articles in common, unique counts, relevance comparison
    - Enables measurement of personalization impact on ranking quality
- API endpoints:
  - `POST /api/v1/feed/personalized-full` – full pipeline with explanations (replaces Phase 2 endpoint)
  - `POST /api/v1/feed/comparison-test` – A/B test comparison with delta metrics
- Streamlit UI: Enhanced Tab 3 "Personalised Feed"
  - User selector: dropdown to choose profile created in Phase 1
  - Profile summary: role, reading level, top interests
  - Feed generation: "Generate My Feed" button triggers full pipeline
  - Feed display: article cards with:
    - Adapted title + content (from adapter agent)
    - Why shown explanation
    - Relevance score (color-coded: 🟢 high, 🟡 medium, 🔴 low)
    - Confidence level (high/medium/low)
    - Matched tags from profile
  - Feedback buttons: 👍 interested / 👎 not interested (Phase 4 hook)
  - A/B comparison: "Show A/B Comparison" button reveals delta metrics

**Architecture Highlights:**
- **Pipeline Integration:** Phase 1 (profiler) + Phase 2 (ranker) + existing agents (adapter)
  - Avoids re-implementation; reuses proven agent pipelines
  - Data flow: user_profile → Phase2_subset → profiler → ranker → adapter → explained_feed
- **Explanation Structure:** Each article includes
  - `why_shown`: Narrative reason from ranker
  - `relevance_score`: Quantitative 0-1 score
  - `confidence`: high/medium/low based on score
  - `format_applied`: Content depth/format from adapter
  - `matched_tags`: Intersection of article tags + profile interests
- **A/B Test Delta Metrics:**
  - Articles in common: How many same articles shown
  - Unique to personalized: Articles only in personalized feed
  - Unique to baseline: Articles only in baseline feed
  - Avg relevance comparison: Quantify personalization impact

**Test Coverage:**
- ✅ 6/6 structural tests passing
  - Module imports verified
  - Profile and article structures validated
  - Component availability (profiler, ranker, adapter)
  - Async function signatures verified
  - A/B comparison function structure validated
- (Note: Full async pipeline testing deferred to Phase 4 runtime validation)

**Acceptance Criteria Met:**
- ✅ Phase 2 personalized subsets flow through existing agent pipeline
- ✅ Full feed generation with explanations for why each article shown
- ✅ A/B comparison reveals personalization delta vs. baseline
- ✅ Streamlit UI allows any user to see their personalized feed
- ✅ Feedback buttons (👍/👎) positioned for Phase 4 integration
- ✅ API endpoints ready for mobile/third-party clients

**Segment Mapping Examples (from Phase 3 Feed Adaptation):**
- **Student + Beginner:** Articles adapted to explain_concepts tone, brief_summary format
- **Professional + Intermediate:** Articles adapted to analytical tone, standard_detail format
- **Entrepreneur + Expert:** Articles adapted to actionable_insights tone, deep_dive format
- **Retiree + Expert:** Articles adapted to cautious tone, comprehensive format

**Historical Limitations (resolved in Phases 4-7):**
- Feedback buttons integration into engagement tracking
- Feedback-aware re-ranking path in adaptive ranker
- Session-level A/B persistence and measurement dashboard

---

### Phase 6: ✅ Experience Quality UX Upgrades (COMPLETE)

**Delivered:**
- `src/agents/feed_organizer.py`
  - Interest-aware feed sectioning with robust fallback section templates
  - Dynamic per-section article counting and section summary helpers
  - In-section search filtering helper
- `src/agents/metadata_enricher.py`
  - Deterministic enrichment for sentiment, urgency, freshness, credibility, and content quality
  - UI format helpers: urgency badges, sentiment emoji, credibility stars, freshness formatter
  - Metadata summary aggregation across feed items
- `ui/app.py` (Tab 3: Personalised Feed)
  - Added sectioned feed rendering using organizer output
  - Added headline picks area from top-ranked section articles
  - Added per-article metadata strip (urgency/sentiment/credibility/freshness)
  - Added section-aware search filtering and section-level metrics
  - Preserved existing feedback loop and A/B comparison controls

**Test Coverage:**
- ✅ `tests/test_phase6_ux_upgrades.py`: 8/8 tests passing
  - section organization
  - section filtering and section statistics
  - sentiment/urgency/credibility/freshness inference
  - full metadata enrichment summary

**Acceptance Criteria Met:**
- ✅ Personalized feed grouped into thematic sections
- ✅ Metadata enrichment visible in feed cards for better scanning
- ✅ Search/filter experience across sectioned feed
- ✅ Existing Phase 5 feedback/comparison behavior retained

---

### Phase 7: ✅ Measurement + A/B Tests (COMPLETE)

**Delivered:**
- `src/agents/ab_measurement.py`
  - A/B run persistence to `output/ab_test_runs.json`
  - Run logging utility: `log_feed_ab_test_run()`
  - Aggregation utilities: `list_ab_test_runs()` and `get_ab_test_summary()`
  - Rolling metrics: win rate, relevance lift, unique-to-personalized, average cost
- `ui/app.py` (Settings + Tab 3 integration)
  - Automatically logs an A/B run whenever "Show A/B Comparison" is executed
  - Adds **Measurement + A/B** controls in Settings:
    - Load A/B summary
    - Load recent A/B runs
    - View daily trend JSON
- `PHASE7_AB_RUNBOOK.md`
  - Run procedure, target metrics, and success heuristics

**Test Coverage:**
- ✅ `tests/test_phase7_measurement_ab.py`: validates run logging, listing/filtering, and summary aggregation

**Acceptance Criteria Met:**
- ✅ A/B comparisons are now persisted and queryable
- ✅ Dashboard-style summary metrics are available in-app
- ✅ Runbook exists for repeatable measurement workflow

---

## Track B: Corpus and Retrieval (Phases 0–5) — Completed

---

## Track C: Experience Intelligence Layer (5 Steps) — Completed

This tracks the newly delivered user-facing intelligence features that make briefings and feeds more actionable and balanced.

### Step Status Summary

| Step | Feature | Status | Validation |
|------|---------|--------|------------|
| **Step 1** | Shared contracts + helper modules | ✅ **COMPLETE** | `tests/test_phase8_signal_layers.py` added (3 tests) |
| **Step 2** | "So what for me?" + contrarian in Personalised Feed | ✅ **COMPLETE** | Manual UI validation + no editor errors |
| **Step 3** | Contrarian toggle in News Navigator | ✅ **COMPLETE** | Manual UI validation + no editor errors |
| **Step 4** | Live Sentiment Pulse in sectioned feed | ✅ **COMPLETE** | Sentiment-focused regression tests passing |
| **Step 5** | Live Sentiment Pulse in Story Arc (video chapters) | ✅ **COMPLETE** | Sentiment/organization regressions passing |

### Delivered Artifacts

- New models in `src/models.py`
  - `PersonalImpactSummary`
  - `ContrarianSummary`
  - `SentimentPulse`
- New agent helpers
  - `src/agents/personal_impact.py`
  - `src/agents/contrarian_view.py`
  - `src/agents/sentiment_pulse.py`
- Streamlit integration
  - `ui/app.py`
    - Tab 3 Personalised Feed: "So what for me?", "Hear the other side", section-level pulse
    - Tab 1 News Navigator: angle-level "Hear the other side"
    - Tab 4 Vernacular Video: Story Arc live sentiment pulse in chapter view

### Validation Snapshot

- `c:/Users/ayush/Documents/NewsAgents/.venv/Scripts/python.exe -m pytest -q tests/test_phase8_signal_layers.py`
- `c:/Users/ayush/Documents/NewsAgents/.venv/Scripts/python.exe -m pytest -q tests/test_phase8_signal_layers.py tests/test_phase6_ux_upgrades.py -k "sentiment or organization"`

---

Previous documentation continues below...

# NewsAgents Corpus and Retrieval Change Log

Last updated: 2026-03-29

## Scope
- Corpus ingestion/retrieval foundation
- Hybrid relevance and subset materialization
- Retrieval contracts and compatibility
- Freshness operations and observability
- Compliance/safety hardening

## Phase Status Snapshot

| Phase | Goal | Status |
|-------|------|--------|
| Phase 0 | Governance and crawl-policy guardrails | Partially complete |
| Phase 1 | Corpus ingestion foundation | Completed |
| Phase 2 | Hybrid relevance and materialized subsets | Completed |
| Phase 3 | Retrieval contracts and full pipeline integration | Completed (Navigator) |
| Phase 4 | Freshness operations and quality monitoring | Completed |
| Phase 5 | Compliance hardening and safety controls | Completed |

## What Was Added and Improved (Chronological)

### Phase 0: Governance and Crawl Boundary Baseline
Delivered:
- Conservative ET crawler scaffolding with bounded depth/page limits.
- Domain gating and reduced-noise URL discovery.

Still open:
- Explicit robots/terms policy gate.
- Policy-first approval runbook.

### Phase 1: Corpus Ingestion Foundation
Delivered:
- Provider abstraction (static/store modes).
- Discovery, queue, crawler, store modules.
- Canonical URL + hash + near-dup controls.
- Document version lineage metadata.
- Phase 1 tests and validation coverage.

### Phase 2: Hybrid Relevance and Subset Materialization
Delivered:
- BM25 + embedding hybrid scoring pipeline.
- Top-k LLM rerank with deterministic fallback path.
- Topic subset persistence with explainability metadata.
- Fresh-subset reuse shortcut to avoid recomputation.
- Persona-general and persona-specific subset strategies.
- Retrieval quality benchmark suite (precision/recall/coverage/explainability).

Notable improvements:
- Fresh subset cache-hit behavior for repeated topic runs.
- Persona interest-match weighting and diversity-aware selection.

### Phase 3: Typed Retrieval Contracts
Delivered:
- Typed contract models (`TopicRetrievalContract`, `RetrievalFreshness`).
- Navigator migration to typed contract while preserving legacy response fields.
- Feature-flagged rollout (`RETRIEVAL_CONTRACTS_ENABLED`).
- Contract compatibility and schema stability tests.

Still open:
- Extend contracts to additional non-navigator consumers.

### Phase 4: Freshness Operations and Monitoring
Delivered:
- Operations orchestration for crawl refresh and subset refresh.
- Runner CLI (`crawl-refresh`, `subset-refresh`, `freshness-metrics`).
- Freshness metrics (article age distribution, topic/persona stale rates).
- Run summaries persistence (`data/corpus/ops/run_summaries.jsonl`).
- Alert threshold hooks for stale subset rates.
- FastAPI ops endpoints for refresh/metrics/summaries.

Still open:
- Deployment scheduler wiring (Task Scheduler/cron).
- External notification integration for warnings.

### Phase 5: Compliance Hardening and Safety Controls
Delivered:
- Compliance preflight validators (deny-by-default).
- Central kill switch (`CORPUS_KILL_SWITCH`) for ingestion/retrieval safety.
- Compliance evidence snapshots (`data/corpus/compliance/snapshots.jsonl`).
- Compliance report generation and review APIs/CLI.
- Retrieval fallback behavior under compliance block/kill-switch paths.

Still open:
- Optional external notification channel for denied-policy events.

## 4) Current Architecture Outcomes

### Retrieval and Relevance
- Explainable topic filtering with inclusion/exclusion reasoning.
- Cache-aware freshness shortcut for repeated topics.
- Backward-compatible response surface with typed contracts under the hood.

### Operations and Observability
- Scheduled-run ready entrypoints via CLI and API.
- Persisted run summaries and freshness metrics for trend tracking.
- Stale-rate alert hooks for operational monitoring integration.

### Safety and Compliance
- Policy preflight checks in refresh/retrieval flows.
- Evidence-grade compliance snapshots and aggregate reports.
- Emergency kill switch for safe fallback behavior.

## 5) UI Testability (Current State)

### Directly Testable in Current UI

#### Core Experience
- News Navigator generation and coverage report.
- Personalised Feed side-by-side adaptation flow.
- Vernacular Video generation flow.

#### Phase 2 + 3 Behavior
- Topic coverage explainability output in Navigator.
- Fresh-subset reuse behavior via repeated topic runs.
- Legacy retrieval field compatibility while typed contracts are active.

#### Settings Page for Ops/Compliance Controls (Top-Right Entry)
- Run crawl refresh and subset refresh actions.
- View freshness metrics and recent run summaries.
- Load compliance snapshots and generate compliance report.
- View current runtime flags (`RETRIEVAL_CONTRACTS_ENABLED`, `CORPUS_KILL_SWITCH`).

### Implemented but Not Fully Surfaced in UI
- Typed `retrieval_contract` internals rendered as structured diagnostics in Navigator.
- Persona subset inspector with interest-match scoring breakdown.
- Benchmark scorecard viewer for precision/recall trends.
- Rich tabular/chart visualization for ops/compliance outputs (currently mostly JSON views).

## 6) Module-Level Change Map

### Corpus and Retrieval
- `src/tools/corpus/relevance.py`
- `src/tools/corpus/subsets.py`
- `src/agents/navigator/topic_relevance.py`
- `src/agents/navigator/pipeline.py`
- `src/models.py`

### Operations and Monitoring
- `src/tools/corpus/operations.py`
- `src/tools/corpus/operations_runner.py`
- `src/api/main.py` (ops endpoints)

### Compliance and Safety
- `src/tools/corpus/compliance.py`
- `src/tools/corpus/bootstrap.py` (preflight enforcement)
- `src/agents/navigator/topic_relevance.py` (retrieval safety handling)

### UI
- `ui/app.py` (top-right Settings button that opens dedicated ops/compliance page)

## 6b) UI Feature Wiring Phases (Streamlit Frontend)

### Phase 1: Entity Graph and Explorer
**Delivered**:
- Interactive Plotly network graph showing entity-angle relationships
- Hoverable entity nodes (left arc) with metadata: name, type, article count, related angles
- Hoverable angle nodes (right lane) with connection details
- Entity Explorer dropdown selectors for drilling into specific entities
- Automatic Plotly→Graphviz fallback for robustness
- Added Plotly 5.0.0 to dependencies

**Key Feature**: Entity graph now interactive and responsive to hover, replacing static Graphviz-only rendering.

### Phase 2: Navigator Topic Coverage Controls
**Delivered**:
- Topic input field on Navigator tab
- Topic coverage enforcement checkbox
- Both parameters wired into briefing pipeline
- Enhanced briefing with topic-specific retrieval

### Phase 3: Settings Page Shell
**Delivered**:
- Dedicated Settings page opened via top-right button
- Navigation buttons (Settings → Back to Navigator)
- Display of runtime flags (Retrieval Contracts, Corpus Kill Switch)

### Phase 4: Ops Actions
**Delivered**:
- Crawl refresh action with topic/depth/page controls
- Subset refresh action
- Freshness metrics viewer (JSON expander)
- Recent run summaries viewer (JSON expander)

### Phase 5: Compliance Actions
**Delivered**:
- Load compliance snapshots viewer (JSON expander)
- Generate compliance report action (JSON expander)

**All Phases Status**: ✅ Complete and tested

## 7) Validation and Test Coverage

Key suites implemented and passing:
- `tests/test_corpus_phase2.py`
- `tests/test_corpus_phase2_benchmarks.py`
- `tests/test_retrieval_contracts_phase3.py`
- `tests/test_corpus_phase4_ops.py`
- `tests/test_corpus_phase5_compliance.py`

Coverage highlights:
- Relevance ranking behavior and fallbacks.
- Contract compatibility/stability.
- Freshness metrics + run summary persistence.
- Compliance preflight denial, kill-switch fallback, and report aggregation.

## 8) Known Gaps and Remaining Work

### Phase 0 Governance Completion
1. Add explicit robots/terms enforcement gate.
2. Add policy-first crawl approvals runbook and artifacts.

### Expansion Work
1. Extend typed retrieval contracts beyond navigator consumers.
2. Add external notifications for ops/compliance warnings.
3. Wire deployment scheduler jobs in target environment.

### UI Maturity Upgrades
1. Structured tables/charts for settings outputs.
2. Retrieval diagnostics panel for typed contract internals.
3. Persona subset and benchmark result inspectors.

## 9) Recommended Next Delivery Sequence
1. Close remaining Phase 0 governance items (robots/terms policy gate + runbook).
2. Expand retrieval contract adoption to feed/other consumers.
3. Add notification and scheduler integrations for production operations.
4. Upgrade settings UI from JSON views to operator-grade dashboards.
