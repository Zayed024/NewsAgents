"""Audit trail logging for enterprise readiness."""

import time
from datetime import datetime
from src.models import AuditEntry

# In-memory audit store (per session)
_audit_store: dict[str, list[AuditEntry]] = {}


def get_audit_trail(session_id: str = "default") -> list[AuditEntry]:
    """Get all audit entries for a session."""
    return _audit_store.get(session_id, [])


def clear_audit_trail(session_id: str = "default"):
    """Clear audit trail for a session."""
    _audit_store[session_id] = []


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
    """Log a single agent step to the audit trail."""
    entry = AuditEntry(
        timestamp=datetime.now().isoformat(),
        session_id=session_id,
        agent_name=agent_name,
        action=action,
        model_used=model_used,
        input_summary=input_summary[:200],
        output_summary=output_summary[:200],
        latency_ms=latency_ms,
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
