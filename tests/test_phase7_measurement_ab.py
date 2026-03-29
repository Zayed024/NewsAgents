"""Phase 7: Measurement + A/B tests smoke validation."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.agents.ab_measurement import (
    log_feed_ab_test_run,
    list_ab_test_runs,
    get_ab_test_summary,
)


def test_phase7_measurement_ab():
    """Validate Phase 7 measurement primitives."""

    print("\n=== Phase 7 Measurement + A/B Test ===\n")

    # Seed multiple comparison results.
    for i in range(3):
        run = log_feed_ab_test_run(
            user_id="phase7-user-001",
            session_id=f"phase7_session_{i}",
            delta_metrics={
                "articles_in_common": 2 + i,
                "unique_to_personalized": 1 + i,
                "personalized_avg_relevance": 0.70 + i * 0.02,
                "baseline_avg_relevance": 0.60 + i * 0.01,
                "personalization_delta": "seeded",
            },
            total_cost_usd=0.005 + i * 0.001,
        )
        assert run.get("run_id"), "run_id missing"

    # Validate listing and filtering.
    recent = list_ab_test_runs(limit=5)
    user_runs = list_ab_test_runs(limit=5, user_id="phase7-user-001")

    assert len(recent) >= 3, "Expected at least 3 recent runs"
    assert len(user_runs) >= 3, "Expected at least 3 user-specific runs"

    # Validate summary shape and key fields.
    summary = get_ab_test_summary(days=365)
    print(f"Total runs: {summary['total_runs']}")
    print(f"Win rate: {summary['personalized_win_rate']}")
    print(f"Avg lift: {summary['avg_relevance_lift']}")
    print(f"Avg unique: {summary['avg_unique_to_personalized']}")
    print(f"Avg cost: {summary['avg_cost_per_run']}")

    assert summary["total_runs"] >= 3
    assert summary["personalized_win_rate"] >= 0
    assert isinstance(summary["daily_trend"], list)

    print("\n=== Phase 7 Tests Passed ===\n")


if __name__ == "__main__":
    test_phase7_measurement_ab()
