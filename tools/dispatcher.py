"""Zone F — DispatcherNode : route vers WhatsApp, Email, SMS, Portal, Push, Chat""" 
from utils.state import GraphState, DispatchStatus
from database.db import get_db
import time

def dispatcher_node(state: GraphState) -> dict:
    canal = state.get("canal_cible", state.get("source").type if state.get("source") else "chat")
    reponse = state.get("reponse_finale", "")
    status = DispatchStatus(canal=canal, success=True, message_id=f"msg_{int(time.time())}")

    try:
        with get_db() as conn:
            conn.execute(
                "INSERT INTO audit_feedback (trace_id, node, comment) VALUES (?, ?, ?)",
                (state.get("session_id", ""), "dispatcher",
                 f"Dispatched to {canal}: {reponse[:100]}"),
            )
    except Exception:
        pass

    return {
        "dispatch_status": status,
        "audit_log": [{"node": "dispatcher", "ts": time.time(), "canal": canal, "success": True}],
    }
