"""
Redis Session Store — Fast session and FHIR token caching.

Stores active session context, FHIR OAuth tokens, and
temporary processing state with automatic TTL expiry.
"""

import json
import logging
from typing import Optional

import redis.asyncio as redis

logger = logging.getLogger(__name__)


class RedisSessionStore:
    """Redis-backed session store with HIPAA-compliant TTL."""

    def __init__(self, redis_url: str, default_ttl: int = 1800):
        self._redis = redis.from_url(redis_url, decode_responses=True)
        self._ttl = default_ttl  # 30 minutes (HIPAA auto-logoff)

    async def get_session(self, session_id: str) -> Optional[dict]:
        data = await self._redis.get(f"session:{session_id}")
        return json.loads(data) if data else None

    async def set_session(self, session_id: str, data: dict, ttl: int = None):
        await self._redis.setex(
            f"session:{session_id}",
            ttl or self._ttl,
            json.dumps(data),
        )

    async def extend_session(self, session_id: str):
        """Extend session TTL on activity (HIPAA: reset inactivity timer)."""
        await self._redis.expire(f"session:{session_id}", self._ttl)

    async def delete_session(self, session_id: str):
        await self._redis.delete(f"session:{session_id}")

    async def store_fhir_token(self, user_id: str, token_data: dict, ttl: int = 3600):
        """Cache FHIR OAuth token for EHR API calls."""
        await self._redis.setex(
            f"fhir_token:{user_id}",
            ttl,
            json.dumps(token_data),
        )

    async def get_fhir_token(self, user_id: str) -> Optional[dict]:
        data = await self._redis.get(f"fhir_token:{user_id}")
        return json.loads(data) if data else None

    async def cache_patient_context(self, patient_id: str, context: dict, ttl: int = 900):
        """Cache patient context to avoid repeated FHIR lookups (15 min TTL)."""
        await self._redis.setex(
            f"patient_ctx:{patient_id}",
            ttl,
            json.dumps(context),
        )

    async def get_patient_context(self, patient_id: str) -> Optional[dict]:
        data = await self._redis.get(f"patient_ctx:{patient_id}")
        return json.loads(data) if data else None

    async def close(self):
        await self._redis.close()
