"""Zone C — Profil & Mémoire : charge le profil utilisateur"""
from utils.state import GraphState
from memory.profile_memory import n5_profil


def zone_c_profil(state: GraphState) -> dict:
    return n5_profil(state)
