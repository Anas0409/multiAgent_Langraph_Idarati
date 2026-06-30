"""Zone B — Orchestrateur RAG : dispatche vers le bon RAG selon l'intent"""
from utils.state import GraphState
from rag.rag_reclamation import rag_reclamation
from rag.rag_procedures import rag_procedures
from rag.rag_faq import rag_faq


def zone_b_rag(state: GraphState) -> dict:
    intent = state.get("intent", "inconnu")
    if intent == "reclamation":
        return rag_reclamation(state)
    elif intent == "procedure":
        return rag_procedures(state)
    elif intent in ("info", "faq"):
        return rag_faq(state)
    return {"rag_results": [], "documents_retrieved": [], "audit_log": []}
