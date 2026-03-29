"""Audit trail logging for enterprise readiness with cost tracking."""

import time
from datetime import datetime
from src.models import AuditEntry

# In-memory audit store (per session)
_audit_store: dict[str, list[AuditEntry]] = {}

# Cost table (USD per 1M tokens)
COST_TABLE = {
    "gemini-2.0-flash": {"input": 0.10, "output": 0.40},
    "gemini-2.0-pro": {"input": 1.25, "output": 5.00},
    "qwen2.5vl:3b": {"input": 0.00, "output": 0.00},
    "local (no LLM)": {"input": 0.00, "output": 0.00},
}


def estimate_tokens(text: str) -> int:
    """Rough token estimate (~4 chars per token for English, ~2 for Devanagari)."""
    if not text:
        return 0
    return max(1, len(text) // 3)


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Estimate cost in USD for a given model and token count."""
    costs = COST_TABLE.get(model, COST_TABLE.get("gemini-2.0-flash"))
    if not costs:
        return 0.0
    input_cost = (input_tokens / 1_000_000) * costs["input"]
    output_cost = (output_tokens / 1_000_000) * costs["output"]
    return round(input_cost + output_cost, 6)


def get_audit_trail(session_id: str = "default") -> list[AuditEntry]:
    """Get all audit entries for a session."""
    return _audit_store.get(session_id, [])


def clear_audit_trail(session_id: str = "default"):
    """Clear audit trail for a session."""
    _audit_store[session_id] = []


def get_session_cost_summary(session_id: str = "default") -> dict:
    """Get cost summary for a session."""
    trail = get_audit_trail(session_id)
    total_cost = sum(e.estimated_cost_usd for e in trail)
    total_input = sum(e.estimated_input_tokens for e in trail)
    total_output = sum(e.estimated_output_tokens for e in trail)
    by_model: dict[str, float] = {}
    for e in trail:
        if e.model_used:
            by_model[e.model_used] = by_model.get(e.model_used, 0) + e.estimated_cost_usd
    return {
        "total_cost_usd": round(total_cost, 6),
        "total_input_tokens": total_input,
        "total_output_tokens": total_output,
        "cost_by_model": by_model,
        "steps": len(trail),
    }


def log_agent_step(
    agent_name: str,
    action: str,
    model_used: str,
    input_summary: str,
    output_summary: str,
    latency_ms: int,
    status: str = "success",
    error_detail: str = "",
    session_id: str = "default",
) -> AuditEntry:
    """Log a single agent step to the audit trail with cost estimation."""
    input_tokens = estimate_tokens(input_summary)
    output_tokens = estimate_tokens(output_summary)
    cost = estimate_cost(model_used, input_tokens, output_tokens)

    entry = AuditEntry(
        timestamp=datetime.now().isoformat(),
        session_id=session_id,
        agent_name=agent_name,
        action=action,
        model_used=model_used,
        input_summary=input_summary[:200],
        output_summary=output_summary[:200],
        latency_ms=latency_ms,
        estimated_input_tokens=input_tokens,
        estimated_output_tokens=output_tokens,
        estimated_cost_usd=cost,
        status=status,
        error_detail=error_detail,
    )
    if session_id not in _audit_store:
        _audit_store[session_id] = []
    _audit_store[session_id].append(entry)
    return entry


class AuditTimer:
    """Context manager for timing agent steps."""

    def __init__(self):
        self.start_time = 0.0
        self.elapsed_ms = 0

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, *args):
        self.elapsed_ms = int((time.time() - self.start_time) * 1000)
