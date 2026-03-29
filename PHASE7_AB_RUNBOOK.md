# Phase 7 A/B Runbook

## Objective
Measure whether personalized ranking beats baseline ranking over repeated runs, with transparent quality and cost metrics.

## Metrics Collected
- `articles_in_common`
- `unique_to_personalized`
- `personalized_avg_relevance`
- `baseline_avg_relevance`
- `relevance_lift = personalized_avg_relevance - baseline_avg_relevance`
- `total_cost_usd` per A/B run

## Data Location
- File: `output/ab_test_runs.json`
- Logging function: `src/agents/ab_measurement.py::log_feed_ab_test_run`

## How To Run
1. Open the app and generate a personalized feed.
2. Click "Show A/B Comparison" in Tab 3.
3. Repeat for multiple users/profiles.
4. Open **Settings → Measurement + A/B** to inspect aggregate metrics.

## Success Heuristic
- `personalized_win_rate >= 0.65`
- `avg_relevance_lift > 0`
- `avg_cost_per_run` stable over time

## Notes
- This is local-file analytics suitable for hackathon/demo scale.
- For production, move storage to a database and add cohort bucketing.
