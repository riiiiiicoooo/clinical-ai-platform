"""
FHIR R4 API Client — Interfaces with Epic EHR via SMART on FHIR.

Handles OAuth 2.0 token management, resource fetching, and
FHIR resource parsing with full audit logging.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Optional

import httpx
from langsmith import traceable

logger = logging.getLogger(__name__)


class FHIRClient:
    """
    SMART on FHIR client for Epic EHR integration.

    Manages OAuth 2.0 tokens, fetches FHIR resources, and
    provides typed access to patient clinical data.
    """

    def __init__(self, base_url: str, client_id: str, client_secret: str):
        self.base_url = base_url.rstrip("/")
        self.client_id = client_id
        self.client_secret = client_secret
        self._token: Optional[str] = None
        self._token_expires: Optional[datetime] = None
        self._http = httpx.AsyncClient(
            timeout=30.0,
            headers={"Accept": "application/fhir+json"},
        )

    async def _ensure_token(self) -> str:
        """Obtain or refresh OAuth 2.0 access token."""
        if self._token and self._token_expires and datetime.utcnow() < self._token_expires:
            return self._token

        token_url = f"{self.base_url}/oauth2/token"
        response = await self._http.post(
            token_url,
            data={
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "scope": "system/*.read",
            },
        )
        response.raise_for_status()
        data = response.json()
        self._token = data["access_token"]
        self._token_expires = datetime.utcnow() + timedelta(seconds=data.get("expires_in", 3600) - 60)
        return self._token

    async def _request(self, resource_type: str, resource_id: str = None, params: dict = None) -> dict:
        """Make authenticated FHIR API request."""
        token = await self._ensure_token()
        url = f"{self.base_url}/{resource_type}"
        if resource_id:
            url = f"{url}/{resource_id}"

        response = await self._http.get(
            url,
            params=params,
            headers={"Authorization": f"Bearer {token}"},
        )
        response.raise_for_status()
        return response.json()

    @traceable(name="fhir.get_patient")
    async def get_patient(self, patient_id: str) -> dict:
        """Fetch Patient resource by ID."""
        return await self._request("Patient", patient_id)

    @traceable(name="fhir.get_conditions")
    async def get_conditions(self, patient_id: str, clinical_status: str = "active") -> list[dict]:
        """Fetch active conditions (diagnoses) for a patient."""
        bundle = await self._request(
            "Condition",
            params={"patient": patient_id, "clinical-status": clinical_status},
        )
        return [entry["resource"] for entry in bundle.get("entry", [])]

    @traceable(name="fhir.get_medications")
    async def get_medications(self, patient_id: str) -> list[dict]:
        """Fetch active medication requests for a patient."""
        bundle = await self._request(
            "MedicationRequest",
            params={"patient": patient_id, "status": "active"},
        )
        return [entry["resource"] for entry in bundle.get("entry", [])]

    @traceable(name="fhir.get_encounters")
    async def get_encounters(self, patient_id: str, count: int = 10) -> list[dict]:
        """Fetch recent encounters for a patient."""
        bundle = await self._request(
            "Encounter",
            params={"patient": patient_id, "_count": count, "_sort": "-date"},
        )
        return [entry["resource"] for entry in bundle.get("entry", [])]

    @traceable(name="fhir.get_observations")
    async def get_observations(self, patient_id: str, category: str = "laboratory") -> list[dict]:
        """Fetch observations (labs, vitals) for a patient."""
        bundle = await self._request(
            "Observation",
            params={"patient": patient_id, "category": category, "_sort": "-date", "_count": 20},
        )
        return [entry["resource"] for entry in bundle.get("entry", [])]

    @traceable(name="fhir.get_allergies")
    async def get_allergies(self, patient_id: str) -> list[dict]:
        """Fetch allergy intolerances for a patient."""
        bundle = await self._request(
            "AllergyIntolerance",
            params={"patient": patient_id, "clinical-status": "active"},
        )
        return [entry["resource"] for entry in bundle.get("entry", [])]

    @traceable(name="fhir.get_procedures")
    async def get_procedures(self, patient_id: str) -> list[dict]:
        """Fetch procedures for a patient."""
        bundle = await self._request(
            "Procedure",
            params={"patient": patient_id, "_sort": "-date", "_count": 20},
        )
        return [entry["resource"] for entry in bundle.get("entry", [])]

    async def get_patient_summary(self, patient_id: str) -> dict:
        """
        Aggregate comprehensive patient context for clinical AI processing.

        Returns unified view of patient demographics, conditions, medications,
        labs, allergies, and recent encounters.
        """
        patient = await self.get_patient(patient_id)
        conditions = await self.get_conditions(patient_id)
        medications = await self.get_medications(patient_id)
        observations = await self.get_observations(patient_id)
        allergies = await self.get_allergies(patient_id)
        encounters = await self.get_encounters(patient_id, count=5)

        return {
            "patient": {
                "id": patient_id,
                "name": _extract_name(patient),
                "dob": patient.get("birthDate"),
                "gender": patient.get("gender"),
            },
            "conditions": [_extract_condition(c) for c in conditions],
            "medications": [_extract_medication(m) for m in medications],
            "lab_results": [_extract_observation(o) for o in observations],
            "allergies": [_extract_allergy(a) for a in allergies],
            "recent_encounters": [_extract_encounter(e) for e in encounters],
        }

    async def close(self):
        await self._http.aclose()


# --- FHIR Resource Extractors ---

def _extract_name(patient: dict) -> str:
    names = patient.get("name", [])
    if names:
        official = next((n for n in names if n.get("use") == "official"), names[0])
        given = " ".join(official.get("given", []))
        family = official.get("family", "")
        return f"{given} {family}".strip()
    return "Unknown"


def _extract_condition(condition: dict) -> dict:
    code = condition.get("code", {})
    codings = code.get("coding", [{}])
    return {
        "display": code.get("text", codings[0].get("display", "Unknown")),
        "code": codings[0].get("code", ""),
        "system": codings[0].get("system", ""),
        "clinical_status": condition.get("clinicalStatus", {}).get("coding", [{}])[0].get("code", ""),
        "onset": condition.get("onsetDateTime", ""),
    }


def _extract_medication(med: dict) -> dict:
    code = med.get("medicationCodeableConcept", {})
    codings = code.get("coding", [{}])
    dosage = med.get("dosageInstruction", [{}])
    return {
        "display": code.get("text", codings[0].get("display", "Unknown")),
        "code": codings[0].get("code", ""),
        "system": codings[0].get("system", ""),
        "dosage": dosage[0].get("text", "") if dosage else "",
        "status": med.get("status", ""),
    }


def _extract_observation(obs: dict) -> dict:
    code = obs.get("code", {})
    codings = code.get("coding", [{}])
    value = obs.get("valueQuantity", {})
    return {
        "display": code.get("text", codings[0].get("display", "Unknown")),
        "code": codings[0].get("code", ""),
        "value": value.get("value"),
        "unit": value.get("unit", ""),
        "effective_date": obs.get("effectiveDateTime", ""),
        "status": obs.get("status", ""),
    }


def _extract_allergy(allergy: dict) -> dict:
    code = allergy.get("code", {})
    codings = code.get("coding", [{}])
    return {
        "display": code.get("text", codings[0].get("display", "Unknown")),
        "code": codings[0].get("code", ""),
        "severity": allergy.get("criticality", ""),
        "reactions": [r.get("description", "") for r in allergy.get("reaction", [])],
    }


def _extract_encounter(encounter: dict) -> dict:
    enc_type = encounter.get("type", [{}])
    return {
        "type": enc_type[0].get("text", "Unknown") if enc_type else "Unknown",
        "status": encounter.get("status", ""),
        "period_start": encounter.get("period", {}).get("start", ""),
        "period_end": encounter.get("period", {}).get("end", ""),
        "class": encounter.get("class", {}).get("code", ""),
    }
