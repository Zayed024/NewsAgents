"""Phase 7: Measurement + A/B test analytics for personalized feed."""

import json
import os
import time
from datetime import datetime
from src.config import OUTPUT_DIR

AB_RUNS_PATH = os.path.join(OUTPUT_DIR, "ab_test_runs.json")


def _load_runs() -> list[dict]:
    """Load persisted A/B run records."""
    if os.path.exists(AB_RUNS_PATH):
        try:
            with open(AB_RUNS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
        except Exception:
            pass
    return []


def _save_runs(runs: list[dict]) -> None:
    """Persist A/B runs to disk."""
    os.makedirs(os.path.dirname(AB_RUNS_PATH), exist_ok=True)
    with open(AB_RUNS_PATH, "w", encoding="utf-8") as f:
        json.dump(runs, f, indent=2, ensure_ascii=False)


def log_feed_ab_test_run(
    user_id: str,
    session_id: str,
    delta_metrics: dict,
    total_cost_usd: float = 0.0,
) -> dict:
    """Persist one personalized-vs-baseline A/B comparison run."""
    run = {
        "run_id": f"ab_{int(time.time() * 1000)}",
        "timestamp": datetime.now().isoformat(),
        "user_id": user_id,
        "session_id": session_id,
        "delta_metrics": delta_metrics,
        "total_cost_usd": round(float(total_cost_usd), 6),
        "winner": (
            "personalized"
            if delta_metrics.get("personalized_avg_relevance", 0)
            >= delta_metrics.get("baseline_avg_relevance", 0)
            else "baseline"
        ),
    }

    runs = _load_runs()
    runs.append(run)
    runs = runs[-1000:]  # Cap storage for lightweight local analytics.
    _save_runs(runs)
    return run


def list_ab_test_runs(limit: int = 50, user_id: str | None = None) -> list[dict]:
    """List recent A/B runs, optionally filtered by user."""
    runs = _load_runs()
    if user_id:
        runs = [r for r in runs if r.get("user_id") == user_id]
    runs.sort(key=lambda r: r.get("timestamp", ""), reverse=True)
    return runs[: max(1, limit)]


def get_ab_test_summary(days: int = 30) -> dict:
    """Compute aggregate metrics for A/B comparisons."""
    runs = _load_runs()
    if not runs:
        return {
            "total_runs": 0,
            "personalized_win_rate": 0.0,
            "avg_relevance_lift": 0.0,
            "avg_unique_to_personalized": 0.0,
            "avg_cost_per_run": 0.0,
            "daily_trend": [],
        }

    now_ts = time.time()
    window_seconds = max(1, days) * 86400

    filtered = []
    for run in runs:
        try:
            ts = datetime.fromisoformat(run.get("timestamp", "")).timestamp()
        except Exception:
            continue
        if now_ts - ts <= window_seconds:
            filtered.append(run)

    if not filtered:
        return {
            "total_runs": 0,
            "personalized_win_rate": 0.0,
            "avg_relevance_lift": 0.0,
            "avg_unique_to_personalized": 0.0,
            "avg_cost_per_run": 0.0,
            "daily_trend": [],
        }

    wins = 0
    lifts = []
    unique_counts = []
    costs = []
    daily = {}

    for run in filtered:
        delta = run.get("delta_metrics", {})
        p = float(delta.get("personalized_avg_relevance", 0.0))
        b = float(delta.get("baseline_avg_relevance", 0.0))
        lift = p - b

        if p >= b:
            wins += 1
        lifts.append(lift)
        unique_counts.append(float(delta.get("unique_to_personalized", 0.0)))
        costs.append(float(run.get("total_cost_usd", 0.0)))

        day = run.get("timestamp", "")[:10]
        bucket = daily.setdefault(day, {"runs": 0, "avg_lift": 0.0})
        bucket["runs"] += 1
        bucket["avg_lift"] += lift

    daily_trend = []
    for day, row in sorted(daily.items()):
        runs_count = row["runs"]
        daily_trend.append(
            {
                "day": day,
                "runs": runs_count,
                "avg_lift": row["avg_lift"] / runs_count if runs_count else 0.0,
            }
        )

    n = len(filtered)
    return {
        "total_runs": n,
        "personalized_win_rate": round(wins / n, 4),
        "avg_relevance_lift": round(sum(lifts) / n, 6),
        "avg_unique_to_personalized": round(sum(unique_counts) / n, 4),
        "avg_cost_per_run": round(sum(costs) / n, 6),
        "daily_trend": daily_trend,
    }
