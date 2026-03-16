"""
Rate Limiting Middleware — Prevents API abuse using Redis-backed sliding window.

Uses Redis sorted sets to maintain request timestamps per IP in a sliding 60-second window.
Ensures rate limits persist across application restarts and are shared across load-balanced instances.
"""

import time
import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from src.db import get_redis_client

logger = logging.getLogger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Redis-backed rate limiter using sliding window (sorted sets)."""

    def __init__(self, app, requests_per_minute: int = 120):
        super().__init__(app)
        self.rpm = requests_per_minute
        self.window_seconds = 60
        self.redis_client = get_redis_client()

    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host if request.client else "unknown"
        now = time.time()
        window_start = now - self.window_seconds

        # Redis key for this IP's request timestamps
        redis_key = f"rate_limit:{client_ip}"

        if self.redis_client is None:
            # Fallback: if Redis is unavailable, allow request but log warning
            logger.warning("Redis unavailable for rate limiting, allowing request from %s", client_ip)
            return await call_next(request)

        try:
            # Remove timestamps outside the sliding window
            self.redis_client.zremrangebyscore(redis_key, "-inf", window_start)

            # Count requests in current window
            request_count = self.redis_client.zcard(redis_key)

            if request_count >= self.rpm:
                logger.info("Rate limit exceeded for IP %s: %d requests in %ds",
                           client_ip, request_count, self.window_seconds)
                return JSONResponse({"error": "Rate limit exceeded"}, status_code=429)

            # Add current request timestamp to sorted set
            self.redis_client.zadd(redis_key, {str(now): now})

            # Set expiration to clean up old keys automatically
            self.redis_client.expire(redis_key, self.window_seconds + 10)

            return await call_next(request)

        except Exception as e:
            # If Redis operation fails, log and allow request (fail-open for availability)
            logger.error("Rate limit check failed: %s, allowing request", str(e))
            return await call_next(request)
