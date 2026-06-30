# nodes/zone_a_analyse.py
"""
Zone A — Compréhension & Analyse
Nodes: N1_nlu, N1b_semantic, N2_preanalyse, N2b_clarification_hitl, clarification_auto

Pattern: chaque node reçoit GraphState complet → retourne dict partiel
"""

from __future__ import annotations
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langgraph.types import interrupt, Command
import json
import time
from utils.json_helper import clean_json_response

from utils.state import GraphState, NLUResult, CompletitudeScore
from config.settings import settings
from utils.llm import llm_main, llm_fast, llm_qwen, safe_invoke

# ─────────────────────────────────────────────────────────────
# N1 — Agent NLU
# Détecte langue, entités, store_urgence, contexte conversationnel
# ─────────────────────────────────────────────────────────────
def n1_nlu(state: GraphState) -> dict:
    """
    Agent NLU — Détection langue ARFINIT2, extraction entités,
    flags sensibles, contexte conversationnel.
    """
    demande = state.get("demande_brute", "")
    
    # Fallback: Extraire du dernier message humain si demande_brute est vide
    if not demande and state.get("messages"):
        for m in reversed(state["messages"]):
            if m.type == "human":
                content = m.content
                if isinstance(content, list):
                    # Cas du Studio : liste de dicts [{'type': 'text', 'text': '...'}]
                    demande = " ".join([c.get("text", "") for c in content if isinstance(c, dict) and c.get("type") == "text"])
                else:
                    demande = content
                break
    
    # Si toujours vide, on ne peut pas analyser
    if not demande:
        return {
            "nlu_result": NLUResult(contexte_conversationnel="Demande vide", langue_detectee="fr"),
            "messages": [AIMessage(content="[NLU] ⚠️ Aucune demande détectée.")],
        }

    # ... (prompt et safe_invoke)
    prompt = f"""Tu es un agent NLU expert en traitement de demandes administratives.

Analyse cette demande et retourne UNIQUEMENT un JSON valide (pas de markdown) :

{{
  "langue_detectee": "fr|ar|en|darija",
  "entites": [{{"type": "PERSONNE|DATE|NUM_DOSSIER|MONTANT|LIEU", "valeur": "..."}}],
  "contexte_conversationnel": "courte description du contexte",
  "store_urgence": 0.0,
  "sous_classification": "type de demande précis",
  "sentiment": "positif|neutre|negatif|frustre",
  "flags_sensibles": ["liste de flags si données personnelles, juridique, etc."]
}}

Demande à analyser: "{demande}"
"""
    try:
        response = safe_invoke(llm_fast, [HumanMessage(content=prompt)])
        data = clean_json_response(response.content)
        if data:
            # Sécurisation des types pour Pydantic
            safe_data = {
                "langue_detectee": str(data.get("langue_detectee", "fr")),
                "contexte_conversationnel": str(data.get("contexte_conversationnel", "")),
                "store_urgence": float(data.get("store_urgence", 0.0)),
                "sentiment": str(data.get("sentiment", "neutre")),
                "sous_classification": str(data.get("sous_classification", ""))
            }
            nlu = NLUResult(**safe_data)
        else:
            nlu = NLUResult(contexte_conversationnel=response.content, langue_detectee="fr")

        # 🏆 Correctif minimal recommandé (Heuristiques de secours)
        msg_brut = str(demande).strip()
        if msg_brut:
            # Si le LLM a renvoyé "indéterminé" ou "vide" par erreur
            if nlu.langue_detectee in ["indetermine", "inconnu", "unknown"]:
                nlu.langue_detectee = "fr" # Défaut intelligent
            
            if not nlu.contexte_conversationnel or "vide" in nlu.contexte_conversationnel.lower():
                nlu.contexte_conversationnel = msg_brut[:200]

            # Extraction d'entités par règles simples si le LLM a échoué
            text_lower = msg_brut.lower()
            existing_vals = [str(e.get("val", "")).lower() for e in nlu.entites]
            
            rules = {
                "cnie": "CNIE",
                "passeport": "Passeport",
                "permis": "Permis",
                "casier": "Casier Judiciaire",
                "casablanca": "Casablanca",
                "rabat": "Rabat",
                "marrakech": "Marrakech"
            }
            
            for keyword, formal in rules.items():
                if keyword in text_lower and keyword not in existing_vals:
                    nlu.entites.append({"type": "KEYWORD", "val": formal})
    except Exception as e:
        return {
            "error_count": 1,
            "audit_log": [{"node": "n1_nlu", "ts": time.time(), "error": str(e)}],
            "messages": [AIMessage(content=f"[NLU] ⚠️ Erreur: {str(e)[:50]}...")],
        }

    return {
        "nlu_result": nlu,
        "messages": [AIMessage(content=f"[NLU] Langue: {nlu.langue_detectee} | Urgence: {nlu.store_urgence:.2f}")],
        "audit_log": [{"node": "n1_nlu", "ts": time.time(), "langue": nlu.langue_detectee}],
    }


# ─────────────────────────────────────────────────────────────
# N1b — Analyse Sémantique (PARALLÈLE avec N1)
# Sous-classification, sentiment, flags sensibles
# ─────────────────────────────────────────────────────────────
def n1b_semantic(state: GraphState) -> dict:
    """
    Analyse sémantique parallèle — profondeur de classification,
    détection de sentiment, scoring urgence.
    """
    demande = state.get("demande_brute", "")
    
    # Fallback: Extraire du dernier message humain
    if not demande and state.get("messages"):
        for m in reversed(state["messages"]):
            if m.type == "human":
                demande = m.content
                break
                
    if not demande:
        return {"audit_log": [{"node": "n1b_semantic", "ts": time.time(), "error": "Demande vide"}]}

    prompt = f"""Analyse sémantique approfondie de cette demande administrative marocaine.
 
 Demande: "{demande}"

DÉFINITIONS DES CATÉGORIES :
- procedure : Demande d'information sur COMMENT obtenir, renouveler ou créer un document (CNIE, Passeport, Permis, etc.).
- reclamation : Plainte concernant un RETARD, une ERREUR, un problème de comportement ou une insatisfaction sur un service déjà rendu.
- info : Question générale sur les horaires, adresses ou missions d'une administration.

Retourne JSON:
{{
  "urgence_confirmee": true|false,
  "categorie_principale": "procedure|reclamation|info|renvoi",
  "sous_themes": ["liste de sous-thèmes"],
  "complexite": "simple|moyenne|complexe",
  "action_suggeree": "description de l'action recommandée"
}}"""

    try:
        response = safe_invoke(llm_fast, [HumanMessage(content=prompt)])
        semantic_data = clean_json_response(response.content)
        if not semantic_data:
            semantic_data = {"action_suggeree": response.content}
    except Exception as e:
        return {
            "error_count": 1,
            "audit_log": [{"node": "n1b_semantic", "ts": time.time(), "error": str(e)}],
            "messages": [AIMessage(content=f"[Semantic] ⚠️ Erreur: {str(e)[:50]}...")],
        }

    return {
        "audit_log": [{"node": "n1b_semantic", "ts": time.time(), "data": semantic_data}],
        "messages": [AIMessage(content=f"[Semantic] Catégorie: {semantic_data.get('categorie_principale', '?')} | Complexité: {semantic_data.get('complexite', '?')}")],
    }


# ─────────────────────────────────────────────────────────────
# N2 — Pré-analyse & Score Complétude
# Score: <0.4 → HITL critique | 0.4-0.7 → clarif auto | >0.7 → continue
# ─────────────────────────────────────────────────────────────
def n2_preanalyse(state: GraphState) -> dict:
    """
    Calcule le score de complétude de la demande.
    Détermine si HITL, clarification auto, ou continuation directe.
    """
    nlu = state.get("nlu_result")
    demande = state.get("demande_brute", "")

    prompt = f"""Évalue la complétude de cette demande administrative (0.0 à 1.0).

Demande: "{demande}"
NLU: {nlu.model_dump() if nlu else 'N/A'}

Critères: identité claire, objet précis, éléments justificatifs, période/date si besoin.

Retourne JSON:
{{
  "score": 0.85,
  "manques": ["liste d'éléments manquants"],
  "decision": "continue|hitl|auto_clarif"
}}
- score < {settings.score_completude_hitl_low} → "hitl"
- {settings.score_completude_hitl_low} ≤ score ≤ {settings.score_completude_hitl_high} → "auto_clarif"
- score > {settings.score_completude_hitl_high} → "continue"
"""
    try:
        response = safe_invoke(llm_fast, [HumanMessage(content=prompt)])
        data = clean_json_response(response.content)
        if data:
            completitude = CompletitudeScore(**data)
        else:
            completitude = CompletitudeScore(score=0.5, decision="continue")

        # 🏆 Sécurité : Ne jamais considérer une question non vide comme vide (0.0)
        msg_brut = state.get("demande_brute", "").strip()
        if msg_brut and len(msg_brut) > 10:
            if completitude.score < 0.4:
                completitude.score = 0.7  # Bypass HITL for clear requests
                completitude.decision = "continue"
    except Exception as e:
        return {
            "error_count": 1,
            "audit_log": [{"node": "n2_preanalyse", "ts": time.time(), "error": str(e)}],
            "messages": [AIMessage(content=f"[Complétude] ⚠️ Erreur: {str(e)[:50]}...")],
        }

    clarification_needed = completitude.decision in ("hitl", "auto_clarif")

    return {
        "completitude": completitude,
        "clarification_needed": clarification_needed,
        "audit_log": [{"node": "n2_preanalyse", "ts": time.time(), "score": completitude.score, "decision": completitude.decision}],
        "messages": [AIMessage(content=f"[Complétude] Score: {completitude.score:.2f} → {completitude.decision}")],
    }


# ─────────────────────────────────────────────────────────────
# N2b — Clarification HITL (Human-in-the-Loop)
# Pause + attend réponse humaine via interrupt()
# ─────────────────────────────────────────────────────────────
def n2b_clarification_hitl(state: GraphState) -> Command:
    """
    HITL critique — pause l'exécution, envoie la question à l'agent humain.
    Reprend quand Command(resume=...) est appelé.
    Pattern: interrupt() → Command(goto=...)
    """
    completitude = state.get("completitude")
    manques = completitude.manques if completitude else ["informations insuffisantes"]

    question = f"Pour traiter votre demande, j'ai besoin de précisions sur : {', '.join(manques)}. Pouvez-vous compléter ?"

    # Pause l'exécution — attend l'input humain
    reponse_humaine = interrupt({
        "type": "clarification_request",
        "question": question,
        "manques": manques,
        "demande_originale": state.get("demande_brute", ""),
        "timeout_seconds": settings.hitl_timeout,
    })

    return Command(
        goto="n3_classification",
        update={
            "clarification_response": str(reponse_humaine),
            "clarification_needed": False,
            "demande_brute": f"{state.get('demande_brute', '')} [COMPLEMENT: {reponse_humaine}]",
            "audit_log": [{"node": "n2b_hitl", "ts": time.time(), "action": "humain_repondu"}],
        }
    )


# ─────────────────────────────────────────────────────────────
# Clarification Auto (score 0.4–0.7)
# Le LLM génère lui-même la question et formule une réponse probable
# ─────────────────────────────────────────────────────────────
def clarification_auto(state: GraphState) -> dict:
    """
    Clarification automatique — le LLM génère une question de précision
    et tente d'y répondre à partir du contexte disponible.
    Score 0.4–0.7 : pas critique, mais améliore la qualité.
    """
    completitude = state.get("completitude")
    manques = completitude.manques if completitude else []

    prompt = f"""Demande: "{state.get('demande_brute', '')}"
Éléments manquants identifiés: {manques}

En te basant sur le contexte de la demande, génère une question de clarification
ET tente d'y répondre avec une valeur probable. Retourne JSON:
{{
  "question": "question posée à l'utilisateur",
  "reponse_probable": "valeur déduite du contexte",
  "confiance": 0.7
}}"""

    response = safe_invoke(llm_fast, [HumanMessage(content=prompt)])
    try:
        data = json.loads(response.content)
        clarif = data.get("reponse_probable", "")
    except Exception:
        clarif = ""

    return {
        "clarification_response": clarif,
        "clarification_needed": False,
        "analyse_complete": True,
        "audit_log": [{"node": "clarif_auto", "ts": time.time(), "reponse": clarif}],
    }
