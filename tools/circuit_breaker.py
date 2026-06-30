"""Circuit Breaker — Mode dégradé pour le système Idarati"""
import time
from langchain_core.messages import AIMessage

from utils.state import GraphState
from config.settings import settings


def circuit_breaker(state: GraphState) -> dict:
    error_count = state.get("error_count", 0)
    reponse_fallback = (
        "Votre demande a bien été reçue. En raison d'une charge élevée, "
        "elle sera traitée sous 24h par notre équipe. "
        "Référence : " + state.get("session_id", "N/A")
    )
    return {
        "reponse_finale": reponse_fallback,
        "circuit_breaker_open": True,
        "format_sortie": "sms",
        "audit_log": [{
            "node": "circuit_breaker",
            "ts": time.time(),
            "error_count": error_count,
            "action": "degradation_gracieuse",
        }],
        "messages": [AIMessage(content=f"[CircuitBreaker] Mode dégradé activé après {error_count} erreurs")],
    }
