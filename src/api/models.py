"""
API Models — Pydantic request/response models for the Clinical AI Platform.
"""

from typing import Optional
from pydantic import BaseModel


# --- Prior Authorization ---

class PAGenerateRequest(BaseModel):
    patient_id: str
    cpt_code: str
    payer_id: str
    provider_id: str
    urgency: str = "routine"
    additional_context: str = ""


class PAGenerateResponse(BaseModel):
    pa_id: str
    status: str
    clinical_summary: str
    missing_docs: list[str] = []
    generation_time_ms: float = 0


class PAAppealRequest(BaseModel):
    pa_id: str
    denial_reason: str = ""


# --- Medical Coding ---

class CodingAnalysisRequest(BaseModel):
    patient_id: str
    encounter_note: str
    encounter_type: str = "office_visit"


class CodingAnalysisResponse(BaseModel):
    analysis: str
    agent: str = ""
    cost: float = 0
    latency_ms: float = 0


# --- Analytics ---

class DenialPredictionRequest(BaseModel):
    cpt_code: str
    icd10_codes: list[str] = []
    payer_name: str = ""
    plan_type: str = ""
    billed_amount: float = 0
    specialty: str = ""
    historical_denial_rate: Optional[float] = None
    provider_denial_rate: Optional[float] = None
    doc_completeness: Optional[float] = None
    flags: list[str] = []


class DenialPredictionResponse(BaseModel):
    analysis: str
    risk_score: int = 0
    cost: float = 0


# --- System ---

class AgentStatusResponse(BaseModel):
    name: str
    model: str
    status: str
    tasks_completed: int = 0
    tasks_failed: int = 0
    total_cost: float = 0
    avg_latency_ms: float = 0
    budget_remaining: float = 0
    last_active: Optional[str] = None


class HealthResponse(BaseModel):
    status: str
    version: str
    fhir_connected: bool = False
    database_connected: bool = False
