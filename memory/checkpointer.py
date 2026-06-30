"""Checkpointer — Factory pour MemorySaver (dev) et PostgresSaver (prod)"""
from langgraph.checkpoint.memory import MemorySaver
from config.settings import settings


def create_checkpointer(use_postgres: bool = False):
    if use_postgres:
        # TODO: décommenter quand PostgreSQL est disponible
        # from langgraph.checkpoint.postgres import PostgresSaver
        # return PostgresSaver.from_conn_string(settings.postgres_dsn)
        raise NotImplementedError("PostgresSaver pas encore configuré")
    return MemorySaver()
