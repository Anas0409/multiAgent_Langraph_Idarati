# nodes/zone_d_orchestration.py
"""
Zone D — Orchestration & Agents Spécialisés

N6 Orchestrateur (Supervisor Pattern) coordonne 4 agents parallèles :
- Agent Légal   → Réglementation, Droits, Délais légaux
- Agent Procédure → Étapes admin, Checklist, Personnalisation
- Agent Rédaction → Génération texte, Mise en forme, Fusion outputs
- Agent Traduction → AR/FR/EN Fastagpt, Termes admin

Basé sur le Supervisor Pattern LangGraph 2026 :
"A supervisor agent coordinates multiple specialized agents.
Each agent maintains its own scratchpad while the supervisor orchestrates."
"""

from __future__ import annotations
from langchain_core.messages import HumanMessage, AIMessage
from langgraph.types import Send
import json
import time
from utils.json_helper import clean_json_response

from utils.state import GraphState
from config.settings import settings
from utils.llm import llm_main, llm_fast, llm_qwen, safe_invoke


# ─────────────────────────────────────────────────────────────
# N6 Context Builder — Normalisation du contexte (Problème n°6)
# ─────────────────────────────────────────────────────────────
def n6_context_builder(state: GraphState) -> dict:
    """
    Analyse les résultats RAG et construit un résumé structuré
    pour nourrir les agents spécialisés.
    """
    docs = state.get("documents_retrieved", [])
    demande = state.get("demande_brute", "")
    
    prompt = f"""Tu es un analyste de données administratives. 
Analyse ces documents RAG et la demande pour extraire un résumé structuré.

Demande: "{demande}"
Documents RAG: {"\n".join(docs[:5]) if docs else "Aucun"}

Retourne UNIQUEMENT un JSON valide avec cette structure:
{{
  "procedure": "Nom de la procédure",
  "administration": "Administration responsable",
  "documents_requis": ["doc1", "doc2"],
  "conditions": ["cond1", "cond2"],
  "frais": "frais exacts",
  "delai_estime": "délai",
  "etapes": ["étape 1", "étape 2"],
  "recours": ["recours possible"],
  "sources": ["urls"]
}}"""

    try:
        response = safe_invoke(llm_fast, [HumanMessage(content=prompt)])
        context_struct = clean_json_response(response.content)
        if not context_struct:
            context_struct = {"description": response.content}
    except Exception as e:
        context_struct = {}
        
    return {
        "contexte_struct": context_struct,
        "audit_log": [{"node": "n6_context_builder", "ts": time.time()}]
    }


# ─────────────────────────────────────────────────────────────
# N6 — Orchestrateur (Supervisor Pattern)
# Planification → Délégation → Supervision → Synthèse
# ─────────────────────────────────────────────────────────────
def n6_orchestrateur(state: GraphState) -> dict:
    intent = state.get("intent", "inconnu")
    rag_results = state.get("rag_results", [])
    profil = state.get("profil_utilisateur", {})
    nlu = state.get("nlu_result")

    prompt = f"""Tu es le superviseur d'un système multi-agent de traitement de demandes administratives.

Contexte:
- Intent: {intent}
- Langue: {nlu.langue_detectee if nlu else 'fr'}
- Profil utilisateur: {json.dumps(profil, ensure_ascii=False)}
- Résumé structuré: {json.dumps(state.get('contexte_struct', {}), ensure_ascii=False)}
- Urgence: {state.get('priorite', 'normale')}

Décide quels agents activer et dans quel ordre. Retourne JSON:
{{
  "plan": ["agent_legal", "agent_procedure", "agent_redaction", "agent_traduction"],
  "prioritaire": "agent_redaction",
  "parallele": true,
  "instructions_specifiques": {{
    "agent_legal": "Se concentrer sur les délais légaux applicables",
    "agent_procedure": "Détailler les étapes pour le profil de cet utilisateur",
    "agent_redaction": "Ton formel, réponse structurée en sections",
    "agent_traduction": "Traduire en arabe si langue_detectee = ar"
  }}
}}

N'active que les agents nécessaires. Pour une info simple: juste agent_redaction."""

    try:
        response = safe_invoke(llm_qwen, [HumanMessage(content=prompt)])
        data = clean_json_response(response.content)
        plan = data.get("plan", ["agent_redaction"])
        instructions = data.get("instructions_specifiques", {})
    except Exception as e:
        plan = ["agent_redaction"]
        instructions = {}
        return {
            "orchestrateur_plan": plan,
            "error_count": 1,
            "audit_log": [{"node": "n6_orchestrateur", "ts": time.time(), "error": str(e)}],
            "messages": [AIMessage(content=f"[Orchestrateur] ⚠️ Erreur: {str(e)[:50]}...")],
        }

    return {
        "orchestrateur_plan": plan,
        "synthese_agents": {"_instructions": json.dumps(instructions)},
        "audit_log": [{"node": "n6_orchestrateur", "ts": time.time(), "plan": plan}],
        "messages": [AIMessage(content=f"[Orchestrateur] Plan: {' → '.join(plan)}")],
    }


# ─────────────────────────────────────────────────────────────
# Agent Légal — Réglementation, Droits, Délais légaux
# ─────────────────────────────────────────────────────────────
def agent_legal(state: GraphState) -> dict:
    docs = state.get("documents_retrieved", [])
    demande = state.get("demande_brute", "")
    instructions = json.loads(state.get("synthese_agents", {}).get("_instructions", "{}"))
    instruction_spec = instructions.get("agent_legal", "Analyser le cadre légal applicable.")
    context_docs = "\n".join(docs[:3]) if docs else "Aucun document RAG disponible."
    prompt = f"""Tu es un expert juridique spécialisé en droit administratif marocain.

Instruction: {instruction_spec}

Demande: "{demande}"

Contexte structuré (RAG):
{json.dumps(state.get('contexte_struct', {}), ensure_ascii=False, indent=2)}

Fournis:
1. Cadre légal applicable (textes de loi, décrets)
2. Droits de l'usager dans ce cas
3. Délais légaux à respecter
4. Recours possibles si refus

Sois précis et cite les références légales exactes."""

    try:
        response = safe_invoke(llm_qwen, [HumanMessage(content=prompt)])
        output = response.content
    except Exception as e:
        output = f"⚠️ [Erreur Agent Légal] {str(e)}"
        return {
            "legal_output": output,
            "error_count": 1,
            "audit_log": [{"node": "agent_legal", "ts": time.time(), "error": str(e)}],
        }

    return {
        "legal_output": output,
        "audit_log": [{"node": "agent_legal", "ts": time.time(), "chars": len(output)}],
    }


# ─────────────────────────────────────────────────────────────
# Agent Procédure — Étapes admin, Checklist, Personnalisation
# ─────────────────────────────────────────────────────────────
def agent_procedure(state: GraphState) -> dict:
    docs = state.get("documents_retrieved", [])
    profil = state.get("profil_utilisateur", {})
    demande = state.get("demande_brute", "")
    niveau_numerique = state.get("niveau_numerique", "moyen")
    context_docs = "\n".join(docs[:3]) if docs else ""
    prompt = f"""Tu es un conseiller administratif expert.

Profil utilisateur: {json.dumps(profil, ensure_ascii=False)}
Niveau numérique: {niveau_numerique}

Demande: "{demande}"

Contexte structuré (RAG):
{json.dumps(state.get('contexte_struct', {}), ensure_ascii=False, indent=2)}

Génère une procédure personnalisée:
1. Liste des documents requis (checklist)
2. Étapes dans l'ordre chronologique
3. Délais estimés par étape
4. Points d'attention spécifiques au profil
5. Alternatives numériques disponibles

Adapte la complexité au niveau numérique: {niveau_numerique}"""

    try:
        response = safe_invoke(llm_qwen, [HumanMessage(content=prompt)])
        output = response.content
    except Exception as e:
        output = f"⚠️ [Erreur Agent Procédure] {str(e)}"
        return {
            "procedure_output": output,
            "error_count": 1,
            "audit_log": [{"node": "agent_procedure", "ts": time.time(), "error": str(e)}],
        }

    return {
        "procedure_output": output,
        "audit_log": [{"node": "agent_procedure", "ts": time.time(), "chars": len(output)}],
    }


# ─────────────────────────────────────────────────────────────
# Agent Rédaction — Génération texte, Mise en forme, Fusion outputs
# ─────────────────────────────────────────────────────────────
def agent_redaction(state: GraphState) -> dict:
    legal = state.get("legal_output", "")
    procedure = state.get("procedure_output", "")
    rag_docs = state.get("documents_retrieved", [])
    profil = state.get("profil_utilisateur", {})
    format_cible = state.get("format_sortie", "markdown")
    canal = state.get("canal_cible", "chat")
    nlu = state.get("nlu_result")

    synthese_inputs = []
    if legal:
        synthese_inputs.append(f"=== CADRE LÉGAL ===\n{legal}")
    if procedure:
        synthese_inputs.append(f"=== PROCÉDURE ===\n{procedure}")
    if rag_docs or state.get("contexte_struct"):
        ctx = json.dumps(state.get("contexte_struct", {}), ensure_ascii=False)
        synthese_inputs.append(f"=== RÉFÉRENCES (CONTEXTE) ===\n{ctx}")

    prompt = f"""Tu es un rédacteur expert en communication administrative.

Demande originale: "{state.get('demande_brute', '')}"
Canal de sortie: {canal}
Format demandé: {format_cible}
Langue: {nlu.langue_detectee if nlu else 'fr'}

Inputs des agents spécialisés:
{''.join(synthese_inputs) or 'Génère une réponse complète basée sur tes connaissances.'}

Rédige une réponse finale:
- Claire, structurée, professionnelle
- Adaptée au canal ({canal}) et au format ({format_cible})
- Personnalisée selon le profil: {json.dumps(profil, ensure_ascii=False)}
- Avec citations RAG si disponibles

Si SMS/WhatsApp: max 300 caractères, direct
Si email/portal: structuré avec sections et sous-titres
Si JSON: structure de données propre"""

    try:
        response = safe_invoke(llm_qwen, [HumanMessage(content=prompt)])
        output = response.content
    except Exception as e:
        output = f"⚠️ [Erreur Agent Rédaction] {str(e)}"
        return {
            "redaction_output": output,
            "reponse_brute": output,
            "error_count": 1,
            "audit_log": [{"node": "agent_redaction", "ts": time.time(), "error": str(e)}],
        }

    return {
        "redaction_output": output,
        "reponse_brute": output,
        "audit_log": [{"node": "agent_redaction", "ts": time.time(), "format": format_cible}],
        "messages": [AIMessage(content=f"[Rédaction] Draft généré ({len(output)} chars)")],
    }


# ─────────────────────────────────────────────────────────────
# Agent Traduction — AR/FR/FR Fastagpt, Termes admin
# ─────────────────────────────────────────────────────────────
def agent_traduction(state: GraphState) -> dict:
    nlu = state.get("nlu_result")
    langue = nlu.langue_detectee if nlu else "fr"
    redaction = state.get("redaction_output", state.get("reponse_brute", ""))

    if langue == "fr" and not state.get("traduction_forcee", False):
        return {
            "traduction_output": redaction,
            "audit_log": [{"node": "agent_traduction", "ts": time.time(), "action": "skip_fr"}],
        }

    cible = "arabe" if langue == "ar" else ("anglais" if langue == "en" else "français")
    prompt = f"""Tu es un traducteur expert spécialisé en terminologie administrative marocaine.

Traduis ce texte en {cible}, en conservant:
- Le ton formel et professionnel
- Les termes administratifs corrects (ex: "مديرية" pour Direction, "طلب" pour demande)
- La structure et le formatage

Texte source:
{redaction}

Retourne UNIQUEMENT la traduction, sans commentaire."""

    try:
        response = safe_invoke(llm_fast, [HumanMessage(content=prompt)])
        output = response.content
    except Exception as e:
        output = redaction
        return {
            "traduction_output": output,
            "error_count": 1,
            "audit_log": [{"node": "agent_traduction", "ts": time.time(), "error": str(e)}],
        }

    return {
        "traduction_output": output,
        "reponse_brute": output,
        "audit_log": [{"node": "agent_traduction", "ts": time.time(), "langue_cible": cible}],
    }


# ─────────────────────────────────────────────────────────────
# Routage post-orchestrateur — envoie vers agents en parallèle
# Utilise le pattern Send() de LangGraph pour parallélisation
# ─────────────────────────────────────────────────────────────
def route_agents_parallel(state: GraphState) -> list:
    """
    Envoie les tâches aux agents spécialisés en parallèle via Send().
    LangGraph exécute tous les Send() simultanément et fusionne via reducers.
    """
    plan = state.get("orchestrateur_plan", ["agent_redaction"])
    # Send() = exécution parallèle native LangGraph
    return [Send(agent_name, state) for agent_name in plan]
