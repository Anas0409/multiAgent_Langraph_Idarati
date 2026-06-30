# config/settings.py
"""
Configuration globale — chargée depuis .env via pydantic-settings.
Un seul objet `settings` importé partout dans le projet.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
import os


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    huggingfacehub_api_token: str = ""
    
    llm_model: str = "deepseek-ai/DeepSeek-R1-Distill-Qwen-32B"
    llm_model_fast: str = "deepseek-ai/DeepSeek-R1-Distill-Qwen-32B"
    llm_model_qwen: str = "deepseek-ai/DeepSeek-R1-Distill-Qwen-32B"
    
    google_api_key: str = "" # Placeholder

    # ── LangSmith ────────────────────────────────────────────────
    langchain_api_key: str = ""
    langchain_tracing_v2: bool = True
    langchain_project: str = "idarati-v2"

    # ── Database (SQLite) ─────────────────────────────────────────
    db_path: str = os.path.join(os.path.dirname(os.path.dirname(__file__)), "database", "idarati.db")

    # ── Mémoire / Cache (optionnel — SQLite fait tout) ────────────
    redis_cache_ttl: int = 86400  # 24h (ignoré sans Redis)

    # ── Seuils ───────────────────────────────────────────────────
    score_completude_min: float = 0.4
    score_completude_hitl_low: float = 0.4
    score_completude_hitl_high: float = 0.7
    score_qualitygate: float = 0.85
    max_quality_iterations: int = 3
    recursion_limit: int = 30

    # ── Circuit Breaker ───────────────────────────────────────────
    circuit_breaker_threshold: int = 5
    circuit_breaker_timeout: int = 60

    # ── HITL ─────────────────────────────────────────────────────
    hitl_timeout: int = 300  # 5 min
    hitl_agent_email: str = "agent@idarati.ma"

    # ── Diffusion ─────────────────────────────────────────────────
    whatsapp_token: str = ""
    whatsapp_phone_id: str = ""
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_pass: str = ""
    twilio_sid: str = ""
    twilio_token: str = ""
    twilio_from: str = ""


settings = Settings()
