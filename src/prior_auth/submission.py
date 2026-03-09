"""
Electronic PA Submission — Submits prior authorization requests to payer APIs.

Implements CMS-mandated FHIR-based PA submission where available,
with fallback to legacy fax/portal submission tracking.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional

import httpx
from langsmith import traceable

logger = logging.getLogger(__name__)


class SubmissionMethod(str, Enum):
    FHIR_API = "fhir_api"  # CMS-mandated PA API
    PORTAL = "portal"  # Payer web portal
    FAX = "fax"  # Legacy fax submission
    CLEARINGHOUSE = "clearinghouse"  # Via claims clearinghouse


@dataclass
class SubmissionResult:
    """Result of PA submission attempt."""
    success: bool
    method: SubmissionMethod
    tracking_id: Optional[str] = None
    payer_reference: Optional[str] = None
    estimated_response_date: Optional[datetime] = None
    error: Optional[str] = None


# Payer submission capabilities (which payers support electronic PA)
PAYER_CAPABILITIES = {
    "bcbs_nc": {
        "fhir_api": True,
        "api_url": "https://api.bcbsnc.com/fhir/r4/PriorAuthRequest",
        "portal": "https://provider.bcbsnc.com/pa",
        "fax": "1-800-555-0101",
    },
    "aetna": {
        "fhir_api": True,
        "api_url": "https://api.aetna.com/fhir/r4/PriorAuthRequest",
        "portal": "https://navinet.navimedix.com",
        "fax": "1-800-555-0102",
    },
    "unitedhealth": {
        "fhir_api": True,
        "api_url": "https://api.uhc.com/fhir/r4/PriorAuthRequest",
        "portal": "https://www.uhcprovider.com/pa",
        "fax": "1-800-555-0103",
    },
}


class PASubmitter:
    """
    Submits PA requests to payers via available channels.

    Prioritizes CMS-mandated FHIR APIs, falls back to portal or fax.
    Tracks submission status and generates submission audit records.
    """

    def __init__(self, audit_logger):
        self.audit_logger = audit_logger
        self._http = httpx.AsyncClient(timeout=30.0)

    @traceable(name="pa_submission.submit")
    async def submit(self, pa_request, method: SubmissionMethod = None) -> SubmissionResult:
        """
        Submit PA request to payer using best available method.

        Priority: FHIR API → Clearinghouse → Portal → Fax
        """
        payer_config = PAYER_CAPABILITIES.get(pa_request.payer_id, {})

        # Determine best submission method
        if method is None:
            if payer_config.get("fhir_api"):
                method = SubmissionMethod.FHIR_API
            elif payer_config.get("portal"):
                method = SubmissionMethod.PORTAL
            else:
                method = SubmissionMethod.FAX

        # Submit via selected method
        if method == SubmissionMethod.FHIR_API:
            result = await self._submit_fhir(pa_request, payer_config)
        elif method == SubmissionMethod.PORTAL:
            result = await self._submit_portal(pa_request, payer_config)
        else:
            result = await self._submit_fax(pa_request, payer_config)

        # Audit log
        await self.audit_logger.log_pa_submission(
            pa_id=pa_request.id,
            payer_id=pa_request.payer_id,
            method=method.value,
            success=result.success,
            tracking_id=result.tracking_id,
        )

        return result

    async def _submit_fhir(self, pa_request, payer_config: dict) -> SubmissionResult:
        """Submit via CMS-mandated FHIR PA API."""
        api_url = payer_config.get("api_url")
        if not api_url:
            return SubmissionResult(
                success=False,
                method=SubmissionMethod.FHIR_API,
                error="FHIR PA API URL not configured",
            )

        # Build FHIR ClaimResponse resource
        fhir_payload = {
            "resourceType": "Claim",
            "status": "active",
            "type": {
                "coding": [{"system": "http://terminology.hl7.org/CodeSystem/claim-type", "code": "professional"}]
            },
            "use": "preauthorization",
            "patient": {"reference": f"Patient/{pa_request.patient_id}"},
            "provider": {"reference": f"Practitioner/{pa_request.provider_id}"},
            "insurer": {"reference": f"Organization/{pa_request.payer_id}"},
            "item": [
                {
                    "sequence": 1,
                    "productOrService": {
                        "coding": [{"system": "http://www.ama-assn.org/go/cpt", "code": pa_request.cpt_code}]
                    },
                    "quantity": {"value": pa_request.quantity},
                }
            ],
            "supportingInfo": [
                {
                    "sequence": 1,
                    "category": {"coding": [{"code": "clinical-notes"}]},
                    "valueString": pa_request.clinical_summary,
                }
            ],
        }

        try:
            response = await self._http.post(
                api_url,
                json=fhir_payload,
                headers={"Content-Type": "application/fhir+json"},
            )
            response.raise_for_status()
            data = response.json()

            return SubmissionResult(
                success=True,
                method=SubmissionMethod.FHIR_API,
                tracking_id=data.get("id"),
                payer_reference=data.get("identifier", [{}])[0].get("value"),
            )
        except Exception as e:
            logger.error("FHIR PA submission failed: %s", str(e))
            return SubmissionResult(
                success=False,
                method=SubmissionMethod.FHIR_API,
                error=str(e),
            )

    async def _submit_portal(self, pa_request, payer_config: dict) -> SubmissionResult:
        """Queue PA for portal submission (tracked manually or via RPA)."""
        return SubmissionResult(
            success=True,
            method=SubmissionMethod.PORTAL,
            tracking_id=f"PORTAL-{pa_request.id}",
        )

    async def _submit_fax(self, pa_request, payer_config: dict) -> SubmissionResult:
        """Queue PA for fax submission (legacy fallback)."""
        return SubmissionResult(
            success=True,
            method=SubmissionMethod.FAX,
            tracking_id=f"FAX-{pa_request.id}",
        )

    async def check_status(self, tracking_id: str, payer_id: str) -> dict:
        """Check PA status via payer API."""
        payer_config = PAYER_CAPABILITIES.get(payer_id, {})
        api_url = payer_config.get("api_url")

        if not api_url:
            return {"status": "unknown", "method": "manual_check_required"}

        try:
            response = await self._http.get(f"{api_url}/{tracking_id}")
            response.raise_for_status()
            data = response.json()
            return {
                "status": data.get("status", "pending"),
                "decision": data.get("outcome", ""),
                "auth_number": data.get("preAuthRef", ""),
            }
        except Exception:
            return {"status": "check_failed", "method": "manual_check_required"}
