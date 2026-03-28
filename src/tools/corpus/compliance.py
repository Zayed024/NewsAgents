"""Phase 5 compliance controls for corpus ingestion and retrieval."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

from src.config import DATA_DIR


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    value = str(raw).strip().lower()
    return value in {"1", "true", "yes", "on"}


def is_corpus_kill_switch_enabled() -> bool:
    """Central emergency stop for corpus ingestion/retrieval."""
    return _env_bool("CORPUS_KILL_SWITCH", default=False)


def _compliance_dir() -> str:
    path = os.path.join(DATA_DIR, "corpus", "compliance")
    os.makedirs(path, exist_ok=True)
    return path


def _snapshots_path() -> str:
    return os.path.join(_compliance_dir(), "snapshots.jsonl")


def _reports_dir() -> str:
    path = os.path.join(_compliance_dir(), "reports")
    os.makedirs(path, exist_ok=True)
    return path


def validate_crawl_preflight(topic: str, max_pages: int, max_depth: int) -> dict[str, Any]:
    """Deny-by-default validator for crawl refresh runs."""
    reasons: list[str] = []
    checks: dict[str, bool] = {}

    topic_ok = bool(topic.strip()) and len(topic.strip()) <= 120
    checks["topic_present_and_bounded"] = topic_ok
    if not topic_ok:
        reasons.append("invalid_topic")

    pages_ok = 1 <= int(max_pages) <= 120
    checks["max_pages_bounded_1_120"] = pages_ok
    if not pages_ok:
        reasons.append("max_pages_out_of_policy")

    depth_ok = 1 <= int(max_depth) <= 4
    checks["max_depth_bounded_1_4"] = depth_ok
    if not depth_ok:
        reasons.append("max_depth_out_of_policy")

    kill_switch = is_corpus_kill_switch_enabled()
    checks["kill_switch_off"] = not kill_switch
    if kill_switch:
        reasons.append("kill_switch_enabled")

    allowed = all(checks.values())
    return {
        "allowed": allowed,
        "checks": checks,
        "reasons": reasons if reasons else ["policy_pass"],
        "policy": "crawl_refresh_v1",
    }


def validate_subset_preflight(topics: list[str], profile_names: list[str], max_items: int) -> dict[str, Any]:
    """Deny-by-default validator for subset refresh runs."""
    reasons: list[str] = []
    checks: dict[str, bool] = {}

    topics_ok = bool(topics) and all(bool(str(t).strip()) for t in topics) and len(topics) <= 20
    checks["topics_present_and_bounded"] = topics_ok
    if not topics_ok:
        reasons.append("invalid_topics")

    profiles_ok = bool(profile_names) and len(profile_names) <= 20
    checks["profiles_present_and_bounded"] = profiles_ok
    if not profiles_ok:
        reasons.append("invalid_profiles")

    max_items_ok = 1 <= int(max_items) <= 200
    checks["max_items_bounded_1_200"] = max_items_ok
    if not max_items_ok:
        reasons.append("max_items_out_of_policy")

    kill_switch = is_corpus_kill_switch_enabled()
    checks["kill_switch_off"] = not kill_switch
    if kill_switch:
        reasons.append("kill_switch_enabled")

    allowed = all(checks.values())
    return {
        "allowed": allowed,
        "checks": checks,
        "reasons": reasons if reasons else ["policy_pass"],
        "policy": "subset_refresh_v1",
    }


def validate_retrieval_preflight(topic: str) -> dict[str, Any]:
    """Validator for retrieval path guardrails."""
    reasons: list[str] = []
    checks: dict[str, bool] = {}

    topic_ok = len(topic.strip()) <= 120
    checks["topic_bounded"] = topic_ok
    if not topic_ok:
        reasons.append("topic_too_long")

    kill_switch = is_corpus_kill_switch_enabled()
    checks["kill_switch_off"] = not kill_switch
    if kill_switch:
        reasons.append("kill_switch_enabled")

    allowed = all(checks.values())
    return {
        "allowed": allowed,
        "checks": checks,
        "reasons": reasons if reasons else ["policy_pass"],
        "policy": "retrieval_v1",
    }


def write_compliance_snapshot(
    operation: str,
    preflight: dict[str, Any],
    decision: str,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Persist compliance evidence snapshot for audits."""
    row = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "operation": operation,
        "decision": decision,
        "preflight": preflight,
        "metadata": metadata or {},
    }
    with open(_snapshots_path(), "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


def load_compliance_snapshots(limit: int = 100) -> list[dict[str, Any]]:
    path = _snapshots_path()
    if not os.path.exists(path):
        return []

    rows: list[dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                continue

    if limit <= 0:
        return rows
    return rows[-limit:]


def generate_compliance_report(limit: int = 500, persist: bool = True) -> dict[str, Any]:
    """Generate aggregate compliance report and optionally persist it."""
    rows = load_compliance_snapshots(limit=limit)

    decision_counts: dict[str, int] = {}
    operation_counts: dict[str, int] = {}
    denied_by_reason: dict[str, int] = {}

    for row in rows:
        decision = str(row.get("decision", "unknown"))
        operation = str(row.get("operation", "unknown"))
        decision_counts[decision] = decision_counts.get(decision, 0) + 1
        operation_counts[operation] = operation_counts.get(operation, 0) + 1

        preflight = row.get("preflight", {}) or {}
        reasons = preflight.get("reasons", []) or []
        if decision.startswith("denied") or decision.startswith("blocked"):
            for reason in reasons:
                key = str(reason)
                denied_by_reason[key] = denied_by_reason.get(key, 0) + 1

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "rows_analyzed": len(rows),
        "decision_counts": decision_counts,
        "operation_counts": operation_counts,
        "denied_by_reason": denied_by_reason,
        "latest_entries": rows[-20:],
    }

    if persist:
        filename = f"compliance-report-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}.json"
        path = os.path.join(_reports_dir(), filename)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        report["report_path"] = path

    return report
