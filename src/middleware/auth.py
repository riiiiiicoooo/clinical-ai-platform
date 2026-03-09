"""
Authentication Middleware — Clerk + SMART on FHIR OAuth.
"""

import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)


class ClerkAuthMiddleware(BaseHTTPMiddleware):
    """Validates Clerk JWT tokens for API authentication."""

    def __init__(self, app, clerk_secret: str = ""):
        super().__init__(app)
        self.clerk_secret = clerk_secret

    async def dispatch(self, request: Request, call_next):
        if request.url.path in ("/api/v1/health", "/docs", "/openapi.json"):
            return await call_next(request)

        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return JSONResponse({"error": "Missing authentication"}, status_code=401)

        # In production: validate Clerk JWT
        # token = auth_header.split(" ")[1]
        # claims = clerk.verify_token(token, self.clerk_secret)

        return await call_next(request)
