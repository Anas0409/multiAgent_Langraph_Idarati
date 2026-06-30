"""RAG Procédures — recherche full-text dans les tables conduite, urbanisme, social."""

from database.db import get_db
from utils.state import GraphState, RAGResult
import time


def rag_procedures(state: GraphState) -> dict:
    terms = state.get("demande_brute", "")[:100]
    with get_db() as conn:
        # Nettoyage pour FTS5 (évite les erreurs sur caractères spéciaux)
        clean_terms = "".join([c if c.isalnum() or c.isspace() else " " for c in terms])
        search_query = " OR ".join(clean_terms.split()[:5]) 

        # Recherche prioritaire dans la table structurée 'procedures' via FTS5
        rows_struct = conn.execute("""
            SELECT p.* FROM procedures p
            JOIN procedures_fts f ON p.id = f.rowid
            WHERE procedures_fts MATCH ?
            ORDER BY rank
            LIMIT 5
        """, (search_query,)).fetchall()
        
        # Fallback LIKE si FTS ne donne rien
        if not rows_struct:
            first_word = terms.split()[0] if terms.split() else ""
            rows_struct = conn.execute("""
                SELECT * FROM procedures 
                WHERE titre LIKE ? OR category LIKE ? 
                LIMIT 3
            """, (f"%{first_word}%", f"%{first_word}%")).fetchall()
        
        # Fallback ou complément via UNION avec les anciennes tables
        rows_legacy = conn.execute("""
            SELECT title, content FROM (
                SELECT title, content FROM conduite
                UNION ALL
                SELECT title, content FROM urbanisme
                UNION ALL
                SELECT title, content FROM social
            ) WHERE content LIKE ?
            LIMIT 3
        """, (f"%{terms}%",)).fetchall()
        
    docs = []
    for r in rows_struct:
        doc_text = f"### {r['titre']} ({r['category']})\n"
        doc_text += f"**Description**: {r['description']}\n"
        doc_text += f"**Documents**: {r['documents_requis']}\n"
        doc_text += f"**Frais**: {r['frais']} | **Délais**: {r['delais']}\n"
        doc_text += f"**Étapes**: {r['etapes']}\n"
        doc_text += f"**Admin**: {r['administration_responsable']}\n"
        doc_text += f"**Source**: {r['url_source']}"
        docs.append(doc_text)
        
    for r in rows_legacy:
        docs.append(f"[{r['title']}] {r['content'][:300]}...")

    if not docs:
        docs = ["Aucune procédure administrative spécifique trouvée pour cette demande."]

    result = RAGResult(
        source="procedures", 
        documents=docs, 
        score_pertinence=0.92 if rows_struct else (0.75 if rows_legacy else 0.3)
    )
    return {
        "rag_results": [result],
        "documents_retrieved": docs,
        "audit_log": [{"node": "rag_procedures", "ts": time.time(), "matches": len(docs)}],
    }
