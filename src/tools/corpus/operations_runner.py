"""CLI entrypoint for scheduled corpus operations."""

from __future__ import annotations

import argparse
import json

from src.tools.corpus.operations import (
    compute_freshness_metrics,
    run_crawl_refresh,
    run_subset_refresh,
)
from src.tools.corpus.compliance import generate_compliance_report, load_compliance_snapshots


def main() -> int:
    parser = argparse.ArgumentParser(description="NewsAgents corpus operations runner")
    sub = parser.add_subparsers(dest="command", required=True)

    crawl = sub.add_parser("crawl-refresh", help="Run crawl/ingestion refresh")
    crawl.add_argument("--topic", required=True, help="Topic to crawl")
    crawl.add_argument("--max-pages", type=int, default=60)
    crawl.add_argument("--max-depth", type=int, default=2)
    crawl.add_argument("--no-bootstrap-if-empty", action="store_true")

    subset = sub.add_parser("subset-refresh", help="Refresh topic and persona subsets")
    subset.add_argument(
        "--topics",
        nargs="+",
        default=["Union Budget 2026"],
        help="One or more topics to refresh",
    )
    subset.add_argument(
        "--profiles",
        nargs="+",
        default=["cfo_profile", "young_investor_profile"],
        help="Profile names under data/user_profiles (without .json)",
    )
    subset.add_argument("--max-items", type=int, default=40)

    metrics = sub.add_parser("freshness-metrics", help="Compute freshness metrics")
    metrics.add_argument("--topic-stale-after", type=int, default=120)
    metrics.add_argument("--persona-stale-after", type=int, default=180)

    compliance = sub.add_parser("compliance-report", help="Generate compliance report")
    compliance.add_argument("--limit", type=int, default=500)
    compliance.add_argument("--no-persist", action="store_true")

    snapshots = sub.add_parser("compliance-snapshots", help="Show compliance snapshots")
    snapshots.add_argument("--limit", type=int, default=100)

    args = parser.parse_args()

    if args.command == "crawl-refresh":
        result = run_crawl_refresh(
            topic=args.topic,
            max_pages=args.max_pages,
            max_depth=args.max_depth,
            bootstrap_if_empty=not args.no_bootstrap_if_empty,
        )
    elif args.command == "subset-refresh":
        result = run_subset_refresh(
            topics=args.topics,
            profile_names=args.profiles,
            max_items=args.max_items,
        )
    elif args.command == "compliance-report":
        result = generate_compliance_report(limit=args.limit, persist=not args.no_persist)
    elif args.command == "compliance-snapshots":
        result = {"snapshots": load_compliance_snapshots(limit=args.limit)}
    else:
        result = compute_freshness_metrics(
            topic_stale_after_minutes=args.topic_stale_after,
            persona_stale_after_minutes=args.persona_stale_after,
        )

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
