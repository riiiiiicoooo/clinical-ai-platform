"""
Database and Redis Connection Management — Central persistence layer for Clinical AI Platform.

Provides:
- SQLAlchemy connection pooling with QueuePool for PostgreSQL
- Redis connection management with automatic reconnection
- Context manager for session management with automatic cleanup
- Health check utilities for both database backends
"""

import os
import logging
from contextlib import contextmanager
from typing import Optional

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool
import redis

logger = logging.getLogger(__name__)

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://localhost:5432/clinical_ai")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# SQLAlchemy engine with connection pooling
# QueuePool: threads wait for an available connection from a pool
# pool_size=20: maintain 20 idle connections
# max_overflow=10: allow up to 10 additional connections beyond pool_size
# pool_timeout=30: wait 30 seconds for a connection before raising timeout error
# pool_recycle=1800: recycle connections after 30 minutes (prevents stale connections)
# pool_pre_ping=True: test connections before using them (PING command)
engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=20,
    max_overflow=10,
    pool_timeout=30,
    pool_recycle=1800,
    pool_pre_ping=True,
    echo=False,  # Set to True for SQL debugging
)

SessionFactory = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)

# Redis client with connection pooling (built-in)
# decode_responses=True: automatically decode bytes to strings
try:
    redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True, socket_connect_timeout=5)
    redis_client.ping()  # Test connection on module load
    logger.info("Redis connection successful: %s", REDIS_URL)
except Exception as e:
    logger.warning("Redis connection failed during initialization: %s", str(e))
    redis_client = None


@contextmanager
def get_session():
    """
    Context manager for database sessions.

    Usage:
        with get_session() as session:
            result = session.execute(...)
            # Auto-commits on success, rolls back on exception
    """
    session = SessionFactory()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error("Database transaction failed: %s", str(e))
        raise
    finally:
        session.close()


def check_postgres() -> bool:
    """Check PostgreSQL connectivity."""
    try:
        with get_session() as session:
            session.execute(text("SELECT 1"))
        logger.debug("PostgreSQL health check passed")
        return True
    except Exception as e:
        logger.error("PostgreSQL health check failed: %s", str(e))
        return False


def check_redis() -> bool:
    """Check Redis connectivity."""
    try:
        if redis_client is None:
            logger.warning("Redis client not initialized")
            return False
        result = redis_client.ping()
        logger.debug("Redis health check passed")
        return bool(result)
    except Exception as e:
        logger.error("Redis health check failed: %s", str(e))
        return False


def get_redis_client() -> Optional[redis.Redis]:
    """
    Get Redis client instance (may be None if connection failed).

    Callers should check for None and handle gracefully.
    """
    return redis_client


async def shutdown():
    """Shutdown database and Redis connections."""
    try:
        engine.dispose()
        logger.info("PostgreSQL connection pool disposed")
    except Exception as e:
        logger.error("Error disposing PostgreSQL pool: %s", str(e))

    try:
        if redis_client:
            redis_client.close()
            logger.info("Redis connection closed")
    except Exception as e:
        logger.error("Error closing Redis connection: %s", str(e))
