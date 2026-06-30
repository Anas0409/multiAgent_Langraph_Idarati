"""RAG FAQ — recherche full-text dans les tables juridique, politique, divorce."""

from database.db import get_db
from utils.state import GraphState, RAGResult
import time


def rag_faq(state: GraphState) -> dict:
    terms = state.get("demande_brute", "")[:100]
    with get_db() as conn:
        rows = conn.execute("""
            SELECT title, content FROM (
                SELECT title, content, 'juridique' as src FROM juridique
                UNION ALL
                SELECT title, content, 'politique' as src FROM politique
                UNION ALL
                SELECT title, content, 'divorce' as src FROM divorce
            ) WHERE content LIKE ?
            LIMIT 5
        """, (f"%{terms}%",)).fetchall()
        if not rows:
            rows = conn.execute(
                "SELECT title, content FROM rag_chunks WHERE category IN ('juridique','politique','divorce') AND content LIKE ? LIMIT 5",
                (f"%{terms[:50]}%",),
            ).fetchall()
    docs = [f"[FAQ] {r['title']}: {r['content'][:300]}" for r in rows] if rows else [
        "Aucune information trouvée dans la FAQ."
    ]
    result = RAGResult(source="faq", documents=docs, score_pertinence=0.82 if rows else 0.3)
    return {
        "rag_results": [result],
        "documents_retrieved": result.documents,
        "audit_log": [{"node": "rag_faq", "ts": time.time()}],
    }
