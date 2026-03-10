"""
Prior Authorization Agent — Automates PA request generation and submission.

Handles the complete PA lifecycle: clinical data extraction, payer criteria
matching, PA package generation, electronic submission, and appeal drafting.
"""

import logging
from typing import Any

from langsmith import traceable

from src.agents.base import BaseClinicalAgent, AgentConfig

logger = logging.getLogger(__name__)

PA_SYSTEM_PROMPT = """You are a Prior Authorization Specialist AI working within a HIPAA-compliant
clinical operations platform for Meridian Health Partners, a 38-provider multi-specialty group.

Your responsibilities:
1. EXTRACT relevant clinical information from patient records to support prior authorization requests
2. MATCH clinical findings against payer-specific coverage criteria
3. GENERATE complete PA request packages with medical necessity justification
4. DRAFT appeal letters when PA requests are denied

CRITICAL RULES:
- Never fabricate clinical information. Only cite data present in the patient record.
- Always include ICD-10 diagnosis codes and CPT procedure codes.
- Medical necessity justification must reference specific clinical findings and evidence-based guidelines.
- Flag any missing documentation that could cause denial.
- If clinical evidence is insufficient for approval, recommend what additional documentation is needed.
- Follow payer-specific formatting requirements when known.

OUTPUT FORMAT for PA Request:
```
PRIOR AUTHORIZATION REQUEST
===========================
Patient: [Name, DOB, MRN, Insurance ID]
Provider: [Requesting provider name, NPI]
Payer: [Insurance company, plan type]
Date of Service: [Requested date]

REQUESTED SERVICE:
- CPT Code: [code] — [description]
- ICD-10 Diagnosis: [code] — [description]
- Quantity/Duration: [units, sessions, days]

CLINICAL SUMMARY:
[Concise summary of relevant clinical history, exam findings, lab results]

MEDICAL NECESSITY JUSTIFICATION:
[Evidence-based reasoning why this service is medically necessary]
[Reference clinical guidelines, failed conservative treatments, clinical progression]

SUPPORTING DOCUMENTATION:
- [List of attached clinical documents]
- [Lab results, imaging reports, specialist notes]

MISSING DOCUMENTATION (if any):
- [Items that should be added before submission]
```

OUTPUT FORMAT for Appeal Letter:
```
APPEAL LETTER
=============
Re: Prior Authorization Denial — [Auth #]
Patient: [Name, DOB]
Service: [CPT] — [Description]
Denial Reason: [Payer's stated reason]

Dear Medical Director,

[Professional appeal letter with:]
1. Summary of clinical situation
2. Point-by-point rebuttal of denial reason
3. Additional clinical evidence supporting medical necessity
4. Reference to applicable clinical guidelines
5. Similar approved cases or precedent (if available)
6. Request for expedited review if clinically urgent

[Closing with provider signature block]
```"""


class PriorAuthAgent(BaseClinicalAgent):
    """
    Agent for prior authorization automation.

    Capabilities:
    - Generate PA requests from patient clinical data
    - Match clinical evidence against payer criteria
    - Identify documentation gaps before submission
    - Draft appeal letters for denied requests
    - Track PA status and turnaround metrics
    """

    def __init__(self, model_router, audit_logger):
        config = AgentConfig(
            name="prior_auth",
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            temperature=0.1,
            daily_budget=80.0,
            per_request_limit=0.50,
            tools=["fhir_patient_lookup", "payer_criteria_search", "pa_submission", "document_search"],
            requires_phi_access=True,
            audit_level="full",
        )
        super().__init__(config, model_router, audit_logger)

    def get_system_prompt(self) -> str:
        return PA_SYSTEM_PROMPT

    @traceable(name="prior_auth.build_context")
    async def build_context(self, request: dict, patient_data: dict) -> str:
        """Build PA-specific prompt with patient clinical data."""
        patient = patient_data.get("patient", {})
        conditions = patient_data.get("conditions", [])
        medications = patient_data.get("medications", [])
        labs = patient_data.get("lab_results", [])
        encounters = patient_data.get("recent_encounters", [])

        # Build clinical summary
        conditions_text = "\n".join(
            f"  - {c['display']} (code: {c.get('code', 'N/A')})" for c in conditions
        ) or "  None documented"

        medications_text = "\n".join(
            f"  - {m['display']} {m.get('dosage', '')}" for m in medications
        ) or "  None documented"

        labs_text = "\n".join(
            f"  - {lab['display']}: {lab.get('value', 'N/A')} {lab.get('unit', '')} ({lab.get('effective_date', 'N/A')})"
            for lab in labs
        ) or "  None documented"

        encounters_text = "\n".join(
            f"  - {e.get('type', 'Unknown')} ({e.get('period_start', 'N/A')})" for e in encounters
        ) or "  None documented"

        task_type = request.get("task_type", "generate_pa")
        service_description = request.get("service_description", "")
        payer_name = request.get("payer_name", "Unknown Payer")
        denial_reason = request.get("denial_reason", "")

        if task_type == "generate_pa":
            instruction = f"""Generate a complete Prior Authorization request for the following:

REQUESTED SERVICE: {service_description}
PAYER: {payer_name}"""
        elif task_type == "appeal":
            instruction = f"""Draft an appeal letter for a denied Prior Authorization:

DENIED SERVICE: {service_description}
PAYER: {payer_name}
DENIAL REASON: {denial_reason}"""
        else:
            instruction = f"""Analyze the clinical documentation and provide a PA readiness assessment for: {service_description}"""

        return f"""{instruction}

PATIENT CLINICAL DATA:
=======================
Patient: {patient.get('name', 'Unknown')}, DOB: {patient.get('dob', 'Unknown')}
Patient ID: {patient.get('id', 'Unknown')}

Active Conditions:
{conditions_text}

Current Medications:
{medications_text}

Recent Lab Results:
{labs_text}

Recent Encounters:
{encounters_text}

ADDITIONAL CONTEXT:
{request.get('additional_context', 'None provided')}
"""
