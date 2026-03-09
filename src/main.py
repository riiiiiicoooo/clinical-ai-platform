"""
Clinical AI Platform — FastAPI Application Entry Point.

HIPAA-compliant AI platform for prior authorization automation,
medical coding intelligence, and revenue cycle analytics.
Built for Meridian Health Partners (38-provider multi-specialty group).
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.config.settings import Settings
from src.middleware.auth import ClerkAuthMiddleware
from src.middleware.audit import AuditMiddleware
from src.middleware.rate_limit import RateLimitMiddleware
from src.api.routes import router as api_router
from src.api.websocket import router as ws_router
from src.memory.session import RedisSessionStore
from src.memory.patient_context import PatientContextStore
from src.memory.knowledge import MedicalKnowledgeStore
from src.providers.router import ModelRouter
from src.compliance.audit_logger import AuditLogger
from src.fhir.client import FHIRClient

logger = logging.getLogger(__name__)
settings = Settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and teardown application resources."""
    logger.info("Starting Clinical AI Platform...")

    # Initialize HIPAA-compliant data stores
    app.state.session_store = RedisSessionStore(settings.redis_url)
    app.state.patient_store = PatientContextStore(settings.database_url)
    app.state.knowledge_store = MedicalKnowledgeStore(settings.database_url)

    # Initialize audit logger (HIPAA requirement)
    app.state.audit_logger = AuditLogger(settings.database_url)
    await app.state.audit_logger.initialize()

    # Initialize FHIR client for EHR integration
    app.state.fhir_client = FHIRClient(
        base_url=settings.fhir_base_url,
        client_id=settings.fhir_client_id,
        client_secret=settings.fhir_client_secret,
    )

    # Initialize LLM model router
    app.state.model_router = ModelRouter(settings)

    logger.info(
        "Clinical AI Platform initialized — FHIR: %s, Audit: enabled",
        settings.fhir_base_url,
    )

    yield

    # Cleanup
    await app.state.session_store.close()
    await app.state.audit_logger.flush()
    logger.info("Clinical AI Platform shutdown complete.")


app = FastAPI(
    title="Clinical AI Platform",
    description="Prior Authorization & Revenue Cycle Intelligence",
    version="1.0.0",
    lifespan=lifespan,
)

# Middleware stack (order matters — outermost first)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(AuditMiddleware)
app.add_middleware(RateLimitMiddleware, requests_per_minute=120)
app.add_middleware(ClerkAuthMiddleware, clerk_secret=settings.clerk_secret_key)

# Routes
app.include_router(api_router, prefix="/api/v1")
app.include_router(ws_router, prefix="/ws")
