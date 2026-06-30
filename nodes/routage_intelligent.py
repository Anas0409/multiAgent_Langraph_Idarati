# nodes/routage_intelligent.py
"""
Routage Intelligent — N3 Classification & Intent, N4 Switch Multi-critères
Ces nodes déterminent quel RAG activer et quel chemin prendre.
Circuit Breaker déplacé vers tools/circuit_breaker.py
"""

from __future__ import annotations
from typing import Literal
from langchain_core.messages import HumanMessage, AIMessage
import json
import time
from utils.json_helper import clean_json_response

from utils.state import GraphState
from config.settings import settings
from utils.llm import llm_fast, safe_invoke


# ─────────────────────────────────────────────────────────────
# N3 — Classification & Intent
# Export: intent_score pour N4
# ─────────────────────────────────────────────────────────────
def n3_classification(state: GraphState) -> dict:
    demande = state.get("demande_brute", "")
    clarif = state.get("clarification_response", "")
    nlu = state.get("nlu_result")

    prompt = f"""Classifie cette demande administrative marocaine.

Demande: "{demande}"
Clarification: "{clarif}"
NLU: {nlu.model_dump() if nlu else 'N/A'}

DÉFINITIONS DES INTENTS :
- procedure : Demande d'information sur COMMENT obtenir, renouveler ou créer un document (CNIE, Passeport, Permis, etc.).
- reclamation : Plainte concernant un RETARD, une ERREUR ou une insatisfaction sur un service déjà rendu.
- info : Question générale sur les horaires, adresses ou missions d'une administration.
- renvoi : Demande hors périmètre.

Retourne JSON:
{{
  "intent": "reclamation|procedure|info|renvoi|inconnu",
  "confidence": 0.92,
  "sous_intent": "description précise",
  "urgence": "basse|normale|haute|urgente",
  "langue_reponse": "fr|ar|en"
}}"""

    try:
        response = safe_invoke(llm_fast, [HumanMessage(content=prompt)])
        data = clean_json_response(response.content)
        intent = data.get("intent", "inconnu")
        confidence = data.get("confidence", 0.5)
        urgence = data.get("urgence", "normale")
    except Exception as e:
        return {
            "intent": "inconnu",
            "error_count": 1,
            "audit_log": [{"node": "n3_classification", "ts": time.time(), "error": str(e)}],
            "messages": [AIMessage(content=f"[Routage] ⚠️ Erreur: {str(e)[:50]}...")],
        }

    return {
        "intent": intent,
        "priorite": urgence,
        "audit_log": [{"node": "n3_classification", "ts": time.time(), "intent": intent, "confidence": confidence}],
        "messages": [AIMessage(content=f"[Routage] Intent: {intent} | Confiance: {confidence:.0%} | Urgence: {urgence}")],
    }


# ─────────────────────────────────────────────────────────────
# N4 — Switch Multi-critères
# Retourne le prochain nœud selon intent + confiance + urgence + profil
# Fonction de routage (pas un node — utilisée dans add_conditional_edges)
# ─────────────────────────────────────────────────────────────
def n4_router(state: GraphState) -> Literal[
    "zone_b_rag", "circuit_breaker", "zone_c_profil"
]:
    if state.get("circuit_breaker_open", False):
        return "circuit_breaker"

    if state.get("error_count", 0) >= settings.circuit_breaker_threshold:
        return "circuit_breaker"

    intent = state.get("intent", "inconnu")

    if intent in ("reclamation", "procedure", "info", "faq"):
        return "zone_b_rag"
    else:
        return "zone_c_profil"


# ─────────────────────────────────────────────────────────────
# Fonction de routage post-analyse (après N2)
# Décide si clarification est nécessaire avant de continuer
# ─────────────────────────────────────────────────────────────
def route_after_analyse(state: GraphState) -> Literal[
    "n2b_clarification_hitl", "clarification_auto", "n3_classification"
]:
    completitude = state.get("completitude")
    if not completitude:
        return "n3_classification"

    score = completitude.score
    low = settings.score_completude_hitl_low
    high = settings.score_completude_hitl_high

    if score < low:
        return "n2b_clarification_hitl"
    elif score <= high:
        return "clarification_auto"
    else:
        return "n3_classification"
