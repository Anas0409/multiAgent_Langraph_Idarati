# main.py
"""
Point d'entrée Idarati v2 — test local et démo LangGraph Studio
Usage: python main.py
"""
import sys
import uuid
from graphs.main_graph import graph
from utils.state import SourceChannel
from langchain_core.messages import HumanMessage
from database.schema import init_db
from database.seed import seed
from database.db import set_db_path
from config.settings import settings

sys.stdout.reconfigure(encoding="utf-8")

# Init SQLite database on startup
set_db_path(settings.db_path)
init_db()
seed()

def run_demo():
    config = {
        "configurable": {"thread_id": f"demo-{uuid.uuid4().hex[:8]}"},
        "recursion_limit": 30,
    }

    initial_state = {
        "demande_brute": "Comment renouvellement CNIE ?",
        "user_id": "user_demo_001",
        "session_id": config["configurable"]["thread_id"],
        "priorite": "normale",
        "source": SourceChannel(type="chat_bot", raw_payload={}),
        "canal_cible": "chat",
        "format_sortie": "markdown",
        "messages": [HumanMessage(content="Bonjour, j'ai besoin d'aide")],
        "error_count": 0,
        "circuit_breaker_open": False,
        "retry_count": 0,
        "clarification_needed": False,
        "analyse_complete": False,
        "cache_updated": False,
        "audit_log": [],
        "rag_results": [],
        "documents_retrieved": [],
        "historique_demandes": [],
        "synthese_agents": {},
        "orchestrateur_plan": [],
    }

    print("=" * 60)
    print("[Demo] Idarati v2 — LangGraph Demo")
    print("=" * 60)

    # Stream node par node pour voir la progression
    final_state = {}
    for chunk in graph.stream(initial_state, config=config, stream_mode="updates"):
        for node_name, node_output in chunk.items():
            if node_name in ("__start__", "__end__"):
                continue
            final_state.update(node_output)
            # Affiche les messages de chaque node
            msgs = node_output.get("messages", [])
            for msg in msgs:
                print(f"  [{node_name}] {msg.content}")

    # Résultat final
    print("\n" + "=" * 60)
    print("✅ RÉPONSE FINALE:")
    print(final_state.get("reponse_finale", "Aucune réponse générée"))
    print("=" * 60)

    qg = final_state.get("quality_gate")
    if qg:
        print(f"📊 Quality Score: {qg.score:.0%} | Action: {qg.action}")

if __name__ == "__main__":
    run_demo()
