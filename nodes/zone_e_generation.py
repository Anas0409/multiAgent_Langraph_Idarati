# nodes/zone_e_generation.py
"""
Zone E — Génération & Qualité
Nodes: N7_generation, N8_qualitygate, N9_formatage

Patterns:
- ReAct cycle: N8 peut renvoyer vers N7 pour régénération
- Multi-format: N9 supporte JSON, PDF, HTML, SMS, etc.
- Quality Gate: scoring multi-critères avant validation
"""

from __future__ import annotations
from langchain_core.messages import HumanMessage, AIMessage
import json
import time
from utils.json_helper import clean_json_response

from utils.state import GraphState, QualityGateResult
from config.settings import settings
from utils.llm import llm_fast, llm_qwen, safe_invoke


# ─────────────────────────────────────────────────────────────
# N7 — Génération (Fast response)
# Streaming token (stream_mode="messages") compatible
# ─────────────────────────────────────────────────────────────
def n7_generation(state: GraphState) -> dict:
    """
    Passthrough node (Problème n°5). 
    La réponse est déjà générée par agent_redaction.
    """
    reponse_brute = state.get("reponse_brute", "")
    traduction = state.get("traduction_output", "")
    
    # Priorité à la traduction si elle existe
    final_text = traduction if (traduction and traduction != reponse_brute) else reponse_brute

    return {
        "reponse_brute": final_text,
        "audit_log": [{"node": "n7_generation", "ts": time.time(), "action": "passthrough"}],
        "messages": [AIMessage(content=f"[N7] Passthrough: {len(final_text)} caractères")],
    }


# ─────────────────────────────────────────────────────────────
# N8 — Quality Gate (Évaluation multi-critères)
# ─────────────────────────────────────────────────────────────
def n8_qualitygate(state: GraphState) -> dict:
    """
    Évalue la qualité de reponse_brute.
    Décide si la réponse est validée ou doit être régénérée.
    """
    reponse = state.get("reponse_brute", "")
    intent = state.get("intent", "inconnu")
    iterations = state.get("quality_gate").iterations + 1 if state.get("quality_gate") else 1

    prompt = f"""Évalue cette réponse administrative marocaine.
Intention: {intent}
Réponse:
{reponse}

Retourne JSON:
{{
  "scores": {{
    "pertinence": 0.9,
    "conformite": 0.85,
    "clarte": 0.88,
    "completude": 0.82,
    "ton": 0.95
  }},
  "score_global": 0.88,
  "issues": ["liste de problèmes si score < 0.85"],
  "action": "valide|regenerer|hitl|degrader"
}}
- score > {settings.score_qualitygate} → "valide"
- 0.5 ≤ score ≤ {settings.score_qualitygate} → "regenerer" (si itérations < {settings.max_quality_iterations})
- score < 0.5 → "hitl"
- itérations >= {settings.max_quality_iterations} → "degrader" """

    try:
        response = safe_invoke(llm_fast, [HumanMessage(content=prompt)])
        data = clean_json_response(response.content)
        
        try:
            score = data.get("score_global", 0.0)
            issues = data.get("issues", [])
            action = data.get("action", "regenerer")

            if iterations >= settings.max_quality_iterations and action == "regenerer":
                action = "degrader"

            passed = score >= settings.score_qualitygate and action == "valide"
            qg = QualityGateResult(score=score, passed=passed, issues=issues, action=action, iterations=iterations)
        except Exception:
            action = "degrader" if iterations >= settings.max_quality_iterations else "regenerer"
            qg = QualityGateResult(score=0.0, passed=False, issues=["Erreur parsing évaluation"], action=action, iterations=iterations)
    except Exception as e:
        action = "degrader" if iterations >= settings.max_quality_iterations else "regenerer"
        qg = QualityGateResult(score=0.0, passed=False, issues=[f"QualityGate indisponible: {str(e)}"], action=action, iterations=iterations)
        return {
            "quality_gate": qg,
            "error_count": 1,
            "audit_log": [{"node": "n8_qualitygate", "ts": time.time(), "error": str(e)}],
        }

    return {
        "quality_gate": qg,
        "audit_log": [{"node": "n8_qualitygate", "ts": time.time(), "score": qg.score, "action": qg.action, "iter": iterations}],
        "messages": [AIMessage(content=f"[QualityGate] Score: {qg.score:.0%} → {qg.action} (iter {iterations})")],
    }


# ─────────────────────────────────────────────────────────────
# Routage post-QualityGate
# ─────────────────────────────────────────────────────────────
def route_after_qualitygate(state: GraphState) -> str:
    qg = state.get("quality_gate")
    if not qg: return "n9_formatage"
    
    if qg.passed or qg.action == "valide":
        return "n9_formatage"
    elif qg.action == "regenerer":
        return "n7_generation"
    elif qg.action == "hitl":
        return "n2b_clarification_hitl"
    else:
        return "circuit_breaker"


# ─────────────────────────────────────────────────────────────
# N9 — Formatage Multi-format
# ─────────────────────────────────────────────────────────────
def n9_formatage(state: GraphState) -> dict:
    reponse = state.get("reponse_brute", "")
    format_cible = state.get("format_sortie", "markdown")
    canal = state.get("canal_cible", "chat")

    formatters = {
        "sms": _format_sms,
        "json": _format_json,
        "html": _format_html,
        "markdown": _format_markdown,
        "pdf": _format_pdf_ready,
        "audio": _format_audio_ssml,
    }

    formatter = formatters.get(format_cible, _format_markdown)
    reponse_formatee = formatter(reponse, state)

    return {
        "reponse_finale": reponse_formatee,
        "audit_log": [{"node": "n9_formatage", "ts": time.time(), "format": format_cible, "canal": canal}],
        "messages": [AIMessage(content=f"[N9] Formaté en {format_cible} pour {canal}")],
    }


def _format_sms(text: str, state: GraphState) -> str:
    clean = text.replace("#", "").replace("*", "").replace("\n\n", " ").replace("\n", " ")
    return clean[:297] + "..." if len(clean) > 300 else clean


def _format_json(text: str, state: GraphState) -> str:
    return json.dumps({
        "reponse": text,
        "session_id": state.get("session_id", ""),
        "intent": state.get("intent", ""),
        "qualite": state.get("quality_gate", {}).score if state.get("quality_gate") else None,
        "ts": time.time(),
    }, ensure_ascii=False, indent=2)


def _format_html(text: str, state: GraphState) -> str:
    import re
    html = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    html = re.sub(r"^# (.+)$", r"<h1>\1</h1>", html, flags=re.MULTILINE)
    html = re.sub(r"^## (.+)$", r"<h2>\1</h2>", html, flags=re.MULTILINE)
    html = re.sub(r"^\* (.+)$", r"<li>\1</li>", html, flags=re.MULTILINE)
    html = html.replace("\n\n", "</p><p>")
    return f"<div class='idarati-response'><p>{html}</p></div>"


def _format_markdown(text: str, state: GraphState) -> str:
    return text


def _format_pdf_ready(text: str, state: GraphState) -> str:
    return f"""---
title: Réponse Idarati
date: {time.strftime('%d/%m/%Y')}
session: {state.get('session_id', 'N/A')}
---

{text}"""


def _format_audio_ssml(text: str, state: GraphState) -> str:
    clean = text.replace("#", "").replace("*", "").replace("|", "")
    return f"""<speak>
  <lang xml:lang="fr-MA">
    <prosody rate="medium" pitch="medium">
      {clean}
    </prosody>
  </lang>
</speak>"""
