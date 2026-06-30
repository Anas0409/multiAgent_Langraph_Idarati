# graphs/main_graph.py
"""
Graphe Principal Idarati v2 — Assemblage complet des 7 zones
Prêt pour LangGraph Studio (langgraph.json pointe ici)

Structure:
  Zone 0 → Zone A → Routage → Zone B → Zone C → Zone D → Zone E → Zone F → Zone G

Patterns utilisés:
  - Supervisor (N6 → agents parallèles via Send())
  - ReAct cycles (N8 QualityGate → N7 reboucle)
  - HITL avec interrupt() (N2b, N8 si score < 0.5)
  - Circuit Breaker (fallback gracieux)
  - Parallel subgraphs (RAG en parallèle)
  - Checkpointing PostgreSQL (Checkpoint 1 et 2)
"""

from __future__ import annotations
from langgraph.graph import StateGraph, START, END

# Note: ne pas importer MemorySaver/PostgresSaver ici.
# LangGraph Studio (langgraph dev) gère la persistance automatiquement.
# Pour utilisation directe en Python, voir memory/checkpointer.py

from utils.state import GraphState

# ── Imports Zone A ────────────────────────────────────────────
from nodes.zone_a_analyse import (
    n1_nlu,
    n1b_semantic,
    n2_preanalyse,
    n2b_clarification_hitl,
    clarification_auto,
)

# ── Imports Routage ───────────────────────────────────────────
from nodes.routage_intelligent import (
    n3_classification,
    n4_router,
    route_after_analyse,
)

# ── Imports Zone B — RAG ──────────────────────────────────────
from nodes.zone_b_rag import zone_b_rag

# ── Imports Zone C — Profil ───────────────────────────────────
from nodes.zone_c_profil import zone_c_profil

# ── Imports Zone D — Orchestration ───────────────────────────
from nodes.zone_d_orchestration import (
    n6_context_builder,
    n6_orchestrateur,
    agent_legal,
    agent_procedure,
    agent_redaction,
    agent_traduction,
    route_agents_parallel,
)

# ── Imports Zone E — Génération ───────────────────────────────
from nodes.zone_e_generation import (
    n7_generation,
    n8_qualitygate,
    n9_formatage,
    route_after_qualitygate,
)

# ── Imports Zone F — Diffusion ────────────────────────────────
from tools.dispatcher import dispatcher_node

# ── Imports Zone G — Traçabilité ─────────────────────────────
from nodes.zone_g_tracabilite import n11_audit, n12_feedback

# ── Imports Circuit Breaker & Checkpointer ────────────────────
from tools.circuit_breaker import circuit_breaker


def build_graph() -> StateGraph:
    """
    Construit et compile le graphe complet Idarati v2.
    Sans checkpointer — LangGraph gère la persistance automatiquement
    (MemorySaver en local, PostgresSaver via langgraph.json).
    """
    g = StateGraph(GraphState)

    # ═══════════════════════════════════════════════════════════
    # ZONE 0 — Entrée (géré par l'appelant via invoke())
    # ═══════════════════════════════════════════════════════════

    # ═══════════════════════════════════════════════════════════
    # ZONE A — Compréhension & Analyse
    # ═══════════════════════════════════════════════════════════
    g.add_node("n1_nlu", n1_nlu)
    g.add_node("n1b_semantic", n1b_semantic)      # Parallèle avec N1
    g.add_node("n2_preanalyse", n2_preanalyse)
    g.add_node("n2b_clarification_hitl", n2b_clarification_hitl)
    g.add_node("clarification_auto", clarification_auto)

    # ═══════════════════════════════════════════════════════════
    # ROUTAGE INTELLIGENT
    # ═══════════════════════════════════════════════════════════
    g.add_node("n3_classification", n3_classification)
    g.add_node("circuit_breaker", circuit_breaker)

    # ═══════════════════════════════════════════════════════════
    # ZONE B — RAG Spécialisés
    # ═══════════════════════════════════════════════════════════
    g.add_node("zone_b_rag", zone_b_rag)

    # ═══════════════════════════════════════════════════════════
    # ZONE C — Profil & Mémoire
    # ═══════════════════════════════════════════════════════════
    g.add_node("zone_c_profil", zone_c_profil)

    # ═══════════════════════════════════════════════════════════
    # ZONE D — Orchestration & Agents Spécialisés
    # ═══════════════════════════════════════════════════════════
    g.add_node("n6_context_builder", n6_context_builder)
    g.add_node("n6_orchestrateur", n6_orchestrateur)
    g.add_node("agent_legal", agent_legal)
    g.add_node("agent_procedure", agent_procedure)
    g.add_node("agent_redaction", agent_redaction)
    g.add_node("agent_traduction", agent_traduction)

    # ═══════════════════════════════════════════════════════════
    # ZONE E — Génération & Qualité
    # ═══════════════════════════════════════════════════════════
    g.add_node("n7_generation", n7_generation)
    g.add_node("n8_qualitygate", n8_qualitygate)
    g.add_node("n9_formatage", n9_formatage)

    # ═══════════════════════════════════════════════════════════
    # ZONE F — Diffusion
    # ═══════════════════════════════════════════════════════════
    g.add_node("dispatcher", dispatcher_node)

    # ═══════════════════════════════════════════════════════════
    # ZONE G — Traçabilité & Amélioration
    # ═══════════════════════════════════════════════════════════
    g.add_node("n11_audit", n11_audit)
    g.add_node("n12_feedback", n12_feedback)

    # ═══════════════════════════════════════════════════════════
    # EDGES — Connexions entre zones
    # ═══════════════════════════════════════════════════════════

    # START → Zone A (Séquentiel pour réduire la pression API/429)
    g.add_edge(START, "n1_nlu")
    g.add_edge("n1_nlu", "n1b_semantic")         # Séquentiel au lieu de parallèle
    g.add_edge("n1b_semantic", "n2_preanalyse")

    # N2 → Routage selon score complétude
    g.add_conditional_edges(
        "n2_preanalyse",
        route_after_analyse,
        {
            "n2b_clarification_hitl": "n2b_clarification_hitl",
            "clarification_auto": "clarification_auto",
            "n3_classification": "n3_classification",
        }
    )

    # Clarification → N3
    g.add_edge("n2b_clarification_hitl", "n3_classification")
    g.add_edge("clarification_auto", "n3_classification")

    # N3 → N4 Router → Zone B / Circuit Breaker / Zone C
    g.add_conditional_edges(
        "n3_classification",
        n4_router,
        {
            "zone_b_rag": "zone_b_rag",
            "circuit_breaker": "circuit_breaker",
            "zone_c_profil": "zone_c_profil",
        }
    )

    # Zone B → Zone C
    g.add_edge("zone_b_rag", "zone_c_profil")

    # Zone C → N6 Context Builder
    g.add_edge("zone_c_profil", "n6_context_builder")

    # N6 Context Builder → N6 Orchestrateur
    g.add_edge("n6_context_builder", "n6_orchestrateur")

    # N6 → Agents parallèles (via Send() dans route_agents_parallel)
    g.add_conditional_edges(
        "n6_orchestrateur",
        route_agents_parallel,  # Retourne [Send(agent, state), ...]
        ["agent_legal", "agent_procedure", "agent_redaction", "agent_traduction"]
    )

    # Agents → N7 (tous convergent vers la génération)
    g.add_edge("agent_legal", "n7_generation")
    g.add_edge("agent_procedure", "n7_generation")
    g.add_edge("agent_redaction", "n7_generation")
    g.add_edge("agent_traduction", "n7_generation")

    # N7 → N8 QualityGate
    g.add_edge("n7_generation", "n8_qualitygate")

    # N8 → Routing (cycle ReAct ou validation)
    g.add_conditional_edges(
        "n8_qualitygate",
        route_after_qualitygate,
        {
            "n9_formatage": "n9_formatage",
            "n7_generation": "n7_generation",        # ← CYCLE reboucle
            "n2b_clarification_hitl": "n2b_clarification_hitl",
            "circuit_breaker": "circuit_breaker",
        }
    )

    # N9 → Dispatcher
    g.add_edge("n9_formatage", "dispatcher")

    # Dispatcher → N11 Audit
    g.add_edge("dispatcher", "n11_audit")

    # N11 → N12 Feedback
    g.add_edge("n11_audit", "n12_feedback")

    # N12 / Circuit Breaker → END
    g.add_edge("n12_feedback", END)
    g.add_edge("circuit_breaker", "n11_audit")

    # ── Compilation ───────────────────────────────────────────
    # Note: Pas de checkpointer ici. LangGraph Studio (langgraph dev)
    # injecte la persistance automatiquement.
    # En production, configurer via langgraph.json.
    return g.compile(
        interrupt_before=["n2b_clarification_hitl"],  # Pause HITL avant exécution
    )


# ── Objet exporté pour LangGraph Studio ───────────────────────
# langgraph.json pointe sur : ./graphs/main_graph.py:graph
graph = build_graph()
