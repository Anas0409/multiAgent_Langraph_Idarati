# auth.py
"""
Authentification Bearer Token pour l'API LangGraph (port 2024).

Usage:
  Ajouter le header dans chaque requête :
    Authorization: Bearer <API_SECRET_KEY>

Configuration :
  Définir API_SECRET_KEY dans .env
  Plusieurs tokens possibles via API_SECRET_KEYS (séparés par virgule)
"""

import os
from langgraph_sdk import Auth

auth = Auth()

# Chargement des tokens autorisés depuis l'environnement
_raw = os.environ.get("API_SECRET_KEYS", os.environ.get("API_SECRET_KEY", ""))
VALID_TOKENS: set[str] = {t.strip() for t in _raw.split(",") if t.strip()}


@auth.authenticate
async def authenticate(authorization: str | None) -> Auth.types.MinimalUserDict:
    """
    Valide le Bearer Token dans le header Authorization.
    Retourne l'identité de l'appelant ou lève une HTTPException.
    """
    if not VALID_TOKENS:
        # Aucun token configuré → accès ouvert (mode dev sans clé)
        return {"identity": "anonymous"}

    if not authorization:
        raise auth.exceptions.HTTPException(
            status_code=401,
            detail="Header Authorization manquant. Format attendu : Bearer <token>",
        )

    scheme, _, token = authorization.partition(" ")

    if scheme.lower() != "bearer":
        raise auth.exceptions.HTTPException(
            status_code=401,
            detail=f"Schéma invalide '{scheme}'. Utiliser : Bearer <token>",
        )

    if token not in VALID_TOKENS:
        raise auth.exceptions.HTTPException(
            status_code=403,
            detail="Token invalide ou expiré.",
        )

    return {"identity": f"api-client-{token[:8]}"}
