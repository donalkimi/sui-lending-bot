"""
Database utilities for SQLAlchemy engine management.
Provides centralized engine creation and lifecycle management.
"""
from sqlalchemy import create_engine, Engine
from typing import Optional
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import settings

# Singleton engines
_sqlite_engine: Optional[Engine] = None
_postgres_engine: Optional[Engine] = None


def get_db_engine() -> Engine:
    """
    Get SQLAlchemy engine for pandas operations (SQLite or PostgreSQL based on settings).

    Engines are cached as singletons for connection pooling efficiency.
    Use this for pd.read_sql_query() operations.

    Returns:
        SQLAlchemy Engine object
    """
    global _sqlite_engine, _postgres_engine

    if settings.USE_CLOUD_DB:
        if _postgres_engine is None:
            _postgres_engine = create_engine(
                settings.SUPABASE_URL,
                pool_size=5,
                max_overflow=10,
                pool_pre_ping=True,  # Verify connections before using
                echo=False
            )
        return _postgres_engine
    else:
        if _sqlite_engine is None:
            _sqlite_engine = create_engine(
                f"sqlite:///{settings.SQLITE_PATH}",
                connect_args={"check_same_thread": False},
                echo=False
            )
        return _sqlite_engine


def dispose_engines():
    """
    Dispose of all engine connections.
    Call this on application shutdown or when switching database configurations.
    """
    global _sqlite_engine, _postgres_engine

    if _sqlite_engine is not None:
        _sqlite_engine.dispose()
        _sqlite_engine = None

    if _postgres_engine is not None:
        _postgres_engine.dispose()
        _postgres_engine = None
