"""
Rate Limiting Middleware — Prevents API abuse.
"""

import time
from collections import defaultdict

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple in-memory rate limiter (production: use Redis)."""

    def __init__(self, app, requests_per_minute: int = 120):
        super().__init__(app)
        self.rpm = requests_per_minute
        self._requests: dict[str, list[float]] = defaultdict(list)

    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host if request.client else "unknown"
        now = time.time()

        # Clean old entries
        self._requests[client_ip] = [t for t in self._requests[client_ip] if now - t < 60]

        if len(self._requests[client_ip]) >= self.rpm:
            return JSONResponse({"error": "Rate limit exceeded"}, status_code=429)

        self._requests[client_ip].append(now)
        return await call_next(request)
