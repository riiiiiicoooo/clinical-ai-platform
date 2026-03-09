"""
Audit Middleware — Logs every API request for HIPAA compliance.
"""

import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

logger = logging.getLogger(__name__)


class AuditMiddleware(BaseHTTPMiddleware):
    """Logs all API requests with timing and user context for HIPAA audit trail."""

    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())[:12]
        start = time.time()

        # Add request ID to state for downstream logging
        request.state.request_id = request_id

        response = await call_next(request)

        duration_ms = (time.time() - start) * 1000
        logger.info(
            "API: %s %s | %d | %.0fms | req=%s",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
            request_id,
        )

        response.headers["X-Request-ID"] = request_id
        return response
