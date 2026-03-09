"""
Prior Authorization Engine — Core PA request generation and lifecycle management.

Orchestrates the complete PA workflow: clinical data gathering, payer criteria
matching, request generation, submission, and status tracking.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

from langsmith import traceable

logger = logging.getLogger(__name__)


class PAStatus(str, Enum):
    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    SUBMITTED = "submitted"
    APPROVED = "approved"
    DENIED = "denied"
    APPEALED = "appealed"
    APPEAL_APPROVED = "appeal_approved"
    APPEAL_DENIED = "appeal_denied"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


@dataclass
class PARequest:
    """A prior authorization request with full lifecycle tracking."""
    id: str
    patient_id: str
    encounter_id: Optional[str] = None
    provider_id: str = ""
    payer_id: str = ""
    payer_name: str = ""

    # Service details
    cpt_code: str = ""
    cpt_description: str = ""
    icd10_codes: list[str] = field(default_factory=list)
    icd10_descriptions: list[str] = field(default_factory=list)
    quantity: int = 1
    urgency: str = "routine"

    # Generated content
    clinical_summary: str = ""
    medical_necessity: str = ""
    supporting_docs: list[str] = field(default_factory=list)
    missing_docs: list[str] = field(default_factory=list)

    # Status tracking
    status: PAStatus = PAStatus.DRAFT
    auth_number: Optional[str] = None
    denial_reason: Optional[str] = None
    appeal_text: Optional[str] = None

    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    submitted_at: Optional[datetime] = None
    decided_at: Optional[datetime] = None

    # Metrics
    generation_time_ms: float = 0
    submission_time_ms: float = 0


class PriorAuthEngine:
    """
    Core engine for prior authorization lifecycle management.

    Workflow:
    1. Receive PA request with service code and patient ID
    2. Fetch patient clinical data via FHIR
    3. Run NLP extraction on relevant clinical notes
    4. Match clinical evidence against payer criteria
    5. Generate PA request package via PA Agent
    6. Submit electronically or queue for human review
    7. Track status and handle appeals if denied
    """

    def __init__(self, fhir_client, nlp_pipeline, pa_agent, criteria_matcher):
        self.fhir_client = fhir_client
        self.nlp_pipeline = nlp_pipeline
        self.pa_agent = pa_agent
        self.criteria_matcher = criteria_matcher

    @traceable(name="pa_engine.generate_request")
    async def generate_request(
        self,
        patient_id: str,
        cpt_code: str,
        payer_id: str,
        provider_id: str,
        urgency: str = "routine",
        additional_context: str = "",
    ) -> PARequest:
        """
        Generate a complete PA request from patient data and service code.

        Returns a PARequest with clinical summary, medical necessity
        justification, supporting documentation, and any gaps identified.
        """
        import uuid
        import time

        start = time.time()
        request_id = str(uuid.uuid4())[:12]

        # Step 1: Fetch patient clinical data via FHIR
        patient_data = await self.fhir_client.get_patient_summary(patient_id)

        # Step 2: Check payer criteria for this service
        criteria = await self.criteria_matcher.get_criteria(payer_id, cpt_code)

        # Step 3: Generate PA via agent
        agent_request = {
            "task_type": "generate_pa",
            "service_description": f"CPT {cpt_code}",
            "payer_name": criteria.get("payer_name", payer_id),
            "payer_criteria": criteria.get("requirements", []),
            "additional_context": additional_context,
        }

        result = await self.pa_agent.execute(agent_request, patient_data)

        # Step 4: Build PA request object
        pa_request = PARequest(
            id=request_id,
            patient_id=patient_id,
            provider_id=provider_id,
            payer_id=payer_id,
            payer_name=criteria.get("payer_name", payer_id),
            cpt_code=cpt_code,
            urgency=urgency,
            clinical_summary=result.get("response", ""),
            status=PAStatus.PENDING_REVIEW,
            generation_time_ms=(time.time() - start) * 1000,
        )

        logger.info(
            "PA request %s generated in %.0fms — status: %s",
            request_id,
            pa_request.generation_time_ms,
            pa_request.status,
        )
        return pa_request

    @traceable(name="pa_engine.generate_appeal")
    async def generate_appeal(self, pa_request: PARequest) -> PARequest:
        """Generate an appeal letter for a denied PA request."""
        patient_data = await self.fhir_client.get_patient_summary(pa_request.patient_id)

        agent_request = {
            "task_type": "appeal",
            "service_description": f"CPT {pa_request.cpt_code} — {pa_request.cpt_description}",
            "payer_name": pa_request.payer_name,
            "denial_reason": pa_request.denial_reason or "Not specified",
            "original_justification": pa_request.medical_necessity,
        }

        result = await self.pa_agent.execute(agent_request, patient_data)

        pa_request.appeal_text = result.get("response", "")
        pa_request.status = PAStatus.APPEALED

        logger.info("Appeal generated for PA %s", pa_request.id)
        return pa_request

    async def check_pa_required(self, payer_id: str, cpt_code: str) -> dict:
        """Check if prior authorization is required for this service/payer combination."""
        criteria = await self.criteria_matcher.get_criteria(payer_id, cpt_code)
        return {
            "pa_required": criteria.get("pa_required", True),
            "criteria_available": criteria.get("criteria_available", False),
            "documentation_requirements": criteria.get("requirements", []),
            "estimated_turnaround": criteria.get("turnaround_days", 3),
        }
