"""N5 — Profil & Contexte : charge/sauvegarde depuis SQLite."""

from database.db import get_db
from utils.state import GraphState
import time


def n5_profil(state: GraphState) -> dict:
    user_id = state.get("user_id", "anonymous")
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM profiles WHERE user_id = ?", (user_id,)
        ).fetchone()
    if row:
        import json
        profil = {
            "user_id": row["user_id"],
            "langue_preferee": row["langue_pref"],
            "niveau_numerique": row["niveau_numerique"],
            "preferences_canal": json.loads(row["preferences_json"]).get("canal", "chat"),
            "historique_count": len(state.get("historique_demandes", [])),
        }
    else:
        profil = {
            "user_id": user_id,
            "langue_preferee": state.get("nlu_result").langue_detectee if state.get("nlu_result") else "fr",
            "niveau_numerique": "moyen",
            "preferences_canal": "chat",
            "historique_count": 0,
        }
    return {
        "profil_utilisateur": profil,
        "audit_log": [{"node": "n5_profil", "ts": time.time(), "user": user_id}],
    }
