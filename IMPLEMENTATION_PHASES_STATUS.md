# NewsAgents Corpus and Retrieval Change Log

Last updated: 2026-03-29

## 1) Goal and Scope
This document is the consolidated change log for corpus and retrieval evolution across Phases 0-5. It tracks:
- What was built in each phase
- What is production-ready now
- What can be validated through current UI
- What still needs UI or ops expansion

Scope covered:
- Corpus ingestion/retrieval foundation
- Hybrid relevance and subset materialization
- Retrieval contracts and compatibility
- Freshness operations and observability
- Compliance/safety hardening

## 2) Phase Status Snapshot

| Phase | Goal | Status |
|------|------|--------|
| Phase 0 | Governance and crawl-policy guardrails | Partially complete |
| Phase 1 | Corpus ingestion foundation | Completed |
| Phase 2 | Hybrid relevance and materialized subsets | Completed |
| Phase 3 | Retrieval contracts and full pipeline integration | Completed (Navigator) |
| Phase 4 | Freshness operations and quality monitoring | Completed |
| Phase 5 | Compliance hardening and safety controls | Completed |

## 3) What Was Added and Improved (Chronological)

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

#### Settings-Based Ops/Compliance Controls (Top-Right)
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
- `ui/app.py` (top-right Settings panel for ops/compliance controls)

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
