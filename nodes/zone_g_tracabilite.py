"""Zone G — Traçabilité & Amélioration Continue : N11 Audit, N12 Feedback/AutoTuning"""

import time
from utils.state import GraphState
from database.db import get_db


def n11_audit(state: GraphState) -> dict:
    audit_summary = {
        "node": "n11_audit", "ts": time.time(),
        "session_id": state.get("session_id", ""),
        "intent": state.get("intent", ""),
        "quality_score": state.get("quality_gate").score if state.get("quality_gate") else None,
        "dispatch_canal": state.get("dispatch_status").canal if state.get("dispatch_status") else None,
        "total_nodes": len(state.get("audit_log", [])),
    }
    # Insert audit log into SQLite
    try:
        with get_db() as conn:
            for entry in state.get("audit_log", []):
                conn.execute(
                    "INSERT INTO audit_feedback (trace_id, node, latency_ms, score_qualite) VALUES (?, ?, ?, ?)",
                    (
                        state.get("session_id", ""),
                        entry.get("node", "unknown"),
                        entry.get("ts", 0),
                        entry.get("score", 0) if isinstance(entry.get("score"), (int, float)) else 0,
                    ),
                )
    except Exception:
        pass
    return {"audit_log": [audit_summary]}


def n12_feedback(state: GraphState) -> dict:
    try:
        with get_db() as conn:
            conn.execute(
                "UPDATE audit_feedback SET rating_user=?, comment=? WHERE trace_id=?",
                (0, "pending", state.get("session_id", "")),
            )
    except Exception:
        pass
    return {
        "ab_test_variant": state.get("ab_test_variant", "A"),
        "audit_log": [{"node": "n12_feedback", "ts": time.time(), "rlhf": "pending"}],
    }
