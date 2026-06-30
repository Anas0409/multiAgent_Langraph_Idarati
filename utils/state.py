# utils/state.py
"""
État global partagé entre tous les agents — GraphState Idarati v2
Inspiré du pattern Clean Architecture + LangGraph 2026 best practices.
Chaque nœud lit le state complet et retourne uniquement les clés modifiées.
"""

from __future__ import annotations
from typing import Annotated, Literal, Any
from typing_extensions import TypedDict
from operator import add
from langgraph.graph.message import add_messages
from langchain_core.messages import AnyMessage
from pydantic import BaseModel, Field
import time


# ─────────────────────────────────────────────
# Sous-types structurés
# ─────────────────────────────────────────────

class SourceChannel(BaseModel):
    """Canal d'entrée de la demande (Zone 0)"""
    type: Literal["chat_bot", "api_rest", "formulaire", "whatsapp", "webhook_cron"]
    raw_payload: dict[str, Any] = Field(default_factory=dict)
    timestamp: float = Field(default_factory=time.time)
    trace_id: str = ""


class NLUResult(BaseModel):
    """Résultat du N1 — Agent NLU"""
    langue_detectee: str = "fr"
    entites: list[dict] = Field(default_factory=list)
    contexte_conversationnel: str = ""
    store_urgence: float = 0.0
    sous_classification: str = ""
    sentiment: str = "neutre"
    flags_sensibles: list[str] = Field(default_factory=list)


class CompletitudeScore(BaseModel):
    """Score de complétude calculé par N2"""
    score: float = 0.0  # 0.0 → 1.0
    manques: list[str] = Field(default_factory=list)  # champs manquants
    decision: Literal["continue", "hitl", "auto_clarif"] = "continue"


class RAGResult(BaseModel):
    """Résultat d'un appel RAG (Zone B)"""
    source: Literal["reclamation", "procedures", "faq", "externe"]
    documents: list[str] = Field(default_factory=list)
    score_pertinence: float = 0.0
    cache_hit: bool = False


class QualityGateResult(BaseModel):
    """Résultat du N8 — QualityGate"""
    score: float = 0.0
    passed: bool = False
    issues: list[str] = Field(default_factory=list)
    action: Literal["valide", "regenerer", "hitl", "degrader"] = "valide"
    iterations: int = 0


class DispatchStatus(BaseModel):
    """Statut d'envoi (Zone F — Diffusion)"""
    canal: Literal["whatsapp", "email", "sms", "portal", "push", "chat"]
    success: bool = False
    error: str = ""
    message_id: str = ""


# ─────────────────────────────────────────────
# GraphState Principal — partagé entre les 7 agents
# ─────────────────────────────────────────────

class GraphState(TypedDict):
    """
    État global du graphe Idarati v2.

    Conventions:
    - Annotated[list, add_messages] → accumulation sans écrasement (messages)
    - Annotated[list, add]          → accumulation simple (logs, docs)
    - type simple                   → écrasement par le dernier nœud
    """

    # ── Zone 0 : Entrée ──────────────────────────────────────────
    source: SourceChannel | None
    demande_brute: str                          # Texte original de l'utilisateur
    user_id: str                                # Identifiant utilisateur (thread mémoire)
    session_id: str                             # Session courante
    priorite: Literal["basse", "normale", "haute", "urgente"]

    # ── Zone A : Compréhension & Analyse ─────────────────────────
    messages: Annotated[list[AnyMessage], add_messages]   # Historique conversationnel
    nlu_result: NLUResult | None
    completitude: CompletitudeScore | None
    clarification_needed: bool
    clarification_question: str
    clarification_response: str                 # Réponse de l'humain (HITL)
    analyse_complete: bool

    # ── Zone B : RAG Spécialisés ──────────────────────────────────
    intent: Literal["reclamation", "procedure", "info", "renvoi", "inconnu"]
    rag_results: Annotated[list[RAGResult], add]           # Accumulation multi-RAG
    documents_retrieved: Annotated[list[str], add]         # Tous les docs récupérés
    cache_updated: bool

    # ── Zone C : Profil & Mémoire ─────────────────────────────────
    profil_utilisateur: dict[str, Any]
    historique_demandes: Annotated[list[str], add]         # Demandes passées
    preferences_canal: str
    niveau_numerique: str

    # ── Zone D : Orchestration & Agents Spécialisés ──────────────
    contexte_struct: dict[str, Any]            # Résumé structuré du RAG (N6 Context Builder)
    orchestrateur_plan: list[str]              # Agents à activer
    synthese_agents: dict[str, str]            # {agent_id: résultat_partiel}
    legal_output: str
    procedure_output: str
    redaction_output: str
    traduction_output: str

    # ── Zone E : Génération & Qualité ─────────────────────────────
    reponse_brute: str                         # Draft N7
    quality_gate: QualityGateResult | None
    reponse_finale: str                        # Validée par N8
    format_sortie: Literal["json", "markdown", "pdf", "html", "sms", "audio"]

    # ── Zone F : Diffusion ────────────────────────────────────────
    dispatch_status: DispatchStatus | None
    canal_cible: str

    # ── Zone G : Traçabilité ──────────────────────────────────────
    audit_log: Annotated[list[dict], add]      # Chaque étape tracée
    rlhf_feedback: str
    ab_test_variant: str
    error_count: Annotated[int, add]
    circuit_breaker_open: bool
    retry_count: int
