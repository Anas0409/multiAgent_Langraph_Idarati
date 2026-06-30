# utils/llm.py
"""
Centralisation des instances de LLM pour le projet.
Utilise DeepSeek-R1 via le Hugging Face Router API (OpenAI Compatible).
"""

from langchain_openai import ChatOpenAI
from config.settings import settings
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type
import httpx
import logging

logger = logging.getLogger(__name__)

# ── LLM instances ─────────────────────────────────────────────

# Instance principale (Hugging Face Router - Compatible OpenAI)
# On utilise ChatOpenAI car le router HF expose une API compatible OpenAI
llm_deepseek = ChatOpenAI(
    model=settings.llm_model,
    api_key=settings.huggingfacehub_api_token,
    base_url="https://router.huggingface.co/v1",
    temperature=0.3,
    timeout=60, # Augmenté car le raisonnement peut être long
    max_retries=3
)

# ── Invocation Sécurisée ──────────────────────────────────────

@retry(
    wait=wait_exponential(multiplier=2, min=4, max=20),
    stop=stop_after_attempt(5),
    retry=retry_if_exception_type((httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError)),
    reraise=True,
    before_sleep=lambda retry_state: logger.warning(f"Retrying LLM call (attempt {retry_state.attempt_number})...")
)
def safe_invoke(llm, messages, **kwargs):
    """
    Invoque le LLM avec gestion des erreurs et retries.
    """
    return llm.invoke(messages, **kwargs)

# Alias pour le projet
llm_main = llm_deepseek
llm_fast = llm_deepseek
llm_qwen = llm_deepseek
llm_reasoning = llm_deepseek
