"""RAG Réclamation — recherche full-text dans la table reclamations via SQLite."""

from database.db import get_db
from utils.state import GraphState, RAGResult
import time


def rag_reclamation(state: GraphState) -> dict:
    terms = state.get("demande_brute", "")[:100]
    with get_db() as conn:
        rows = conn.execute(
            "SELECT title, content FROM reclamations WHERE content LIKE ? LIMIT 5",
            (f"%{terms}%",),
        ).fetchall()
        if not rows:
            rows = conn.execute(
                "SELECT title, content FROM rag_chunks WHERE category='reclamations' AND content LIKE ? LIMIT 5",
                (f"%{terms[:50]}%",),
            ).fetchall()
    docs = [f"[{r['title']}] {r['content'][:300]}" for r in rows] if rows else [
        "Aucun document trouvé pour cette réclamation."
    ]
    result = RAGResult(source="reclamation", documents=docs, score_pertinence=0.85 if rows else 0.3)
    return {
        "rag_results": [result],
        "documents_retrieved": result.documents,
        "audit_log": [{"node": "rag_reclamation", "ts": time.time(), "docs": len(docs)}],
    }
