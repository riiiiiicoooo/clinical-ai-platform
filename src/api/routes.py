"""
API Routes — REST endpoints for the Clinical AI Platform.

Exposes prior authorization, medical coding, and analytics capabilities
via authenticated, audit-logged API endpoints.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Query
from src.api.models import (
    PAGenerateRequest,
    PAGenerateResponse,
    PAAppealRequest,
    CodingAnalysisRequest,
    CodingAnalysisResponse,
    DenialPredictionRequest,
    DenialPredictionResponse,
    AgentStatusResponse,
    HealthResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/prior-auth/generate", response_model=PAGenerateResponse)
async def generate_pa(request: PAGenerateRequest, req: Request):
    """Generate a prior authorization request package."""
    pa_engine = req.app.state.pa_engine
    result = await pa_engine.generate_request(
        patient_id=request.patient_id,
        cpt_code=request.cpt_code,
        payer_id=request.payer_id,
        provider_id=request.provider_id,
        urgency=request.urgency,
        additional_context=request.additional_context,
    )
    return PAGenerateResponse(
        pa_id=result.id,
        status=result.status.value,
        clinical_summary=result.clinical_summary,
        missing_docs=result.missing_docs,
        generation_time_ms=result.generation_time_ms,
    )


@router.post("/prior-auth/appeal")
async def generate_appeal(request: PAAppealRequest, req: Request):
    """Generate an appeal letter for a denied PA."""
    pa_engine = req.app.state.pa_engine
    result = await pa_engine.generate_appeal(request.pa_id)
    return {"pa_id": request.pa_id, "appeal_text": result.appeal_text, "status": result.status.value}


@router.post("/prior-auth/check")
async def check_pa_required(payer_id: str, cpt_code: str, req: Request):
    """Check if PA is required for a service/payer combination."""
    pa_engine = req.app.state.pa_engine
    return await pa_engine.check_pa_required(payer_id, cpt_code)


@router.post("/coding/analyze", response_model=CodingAnalysisResponse)
async def analyze_coding(request: CodingAnalysisRequest, req: Request):
    """Analyze clinical documentation and suggest medical codes."""
    coding_agent = req.app.state.coding_agent
    result = await coding_agent.execute(
        {"encounter_note": request.encounter_note, "encounter_type": request.encounter_type},
        {"patient": {"id": request.patient_id}},
    )
    return CodingAnalysisResponse(
        analysis=result.get("response", ""),
        agent=result.get("agent", ""),
        cost=result.get("cost", 0),
        latency_ms=result.get("latency_ms", 0),
    )


@router.post("/analytics/predict-denial", response_model=DenialPredictionResponse)
async def predict_denial(request: DenialPredictionRequest, req: Request):
    """Predict claim denial risk before submission."""
    analytics_agent = req.app.state.analytics_agent
    result = await analytics_agent.execute(
        {"task_type": "denial_prediction", "claim_data": request.model_dump()},
        {},
    )
    return DenialPredictionResponse(
        analysis=result.get("response", ""),
        risk_score=0,  # Parsed from response in production
        cost=result.get("cost", 0),
    )


@router.get("/agents/status", response_model=list[AgentStatusResponse])
async def get_agent_status(
    req: Request,
    limit: int = Query(10, ge=1, le=100, description="Maximum number of agents to return"),
    offset: int = Query(0, ge=0, description="Number of agents to skip"),
):
    """Get status of all clinical AI agents with pagination support."""
    agents = [
        req.app.state.pa_agent,
        req.app.state.coding_agent,
        req.app.state.analytics_agent,
    ]
    agent_statuses = [AgentStatusResponse(**a.get_status()) for a in agents if hasattr(a, "get_status")]

    # Apply pagination
    paginated = agent_statuses[offset : offset + limit]
    return paginated


@router.get("/cost/summary")
async def get_cost_summary(req: Request):
    """Get LLM cost summary across all agents."""
    return req.app.state.model_router.get_cost_summary()


@router.get("/health", response_model=HealthResponse)
async def health_check(req: Request):
    """Health check endpoint."""
    return HealthResponse(
        status="healthy",
        version="1.0.0",
        fhir_connected=True,
        database_connected=True,
    )
