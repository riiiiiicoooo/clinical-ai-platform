"""
Patient Context Store — Aggregates patient data for clinical AI processing.

Combines FHIR data, NLP extractions, PA history, and coding history
into unified patient context for AI agents.
"""

import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


class PatientContextStore:
    """
    PostgreSQL-backed patient context aggregation.

    Stores enriched patient context including:
    - FHIR-sourced clinical data
    - NLP extraction history
    - Prior auth request history
    - Coding suggestion history
    - Denial/appeal outcomes
    """

    def __init__(self, database_url: str):
        self._database_url = database_url

    async def get_pa_history(self, patient_id: str) -> list[dict]:
        """Get patient's prior authorization history."""
        # In production: query pa_requests table
        return []

    async def get_denial_history(self, patient_id: str) -> list[dict]:
        """Get patient's claim denial history."""
        return []

    async def get_coding_history(self, patient_id: str, limit: int = 10) -> list[dict]:
        """Get recent coding suggestions for this patient."""
        return []

    async def build_context(
        self,
        patient_id: str,
        fhir_data: dict,
        include_pa_history: bool = True,
        include_denial_history: bool = True,
    ) -> dict:
        """Build comprehensive patient context for AI processing."""
        context = {
            "patient": fhir_data.get("patient", {}),
            "conditions": fhir_data.get("conditions", []),
            "medications": fhir_data.get("medications", []),
            "lab_results": fhir_data.get("lab_results", []),
            "allergies": fhir_data.get("allergies", []),
            "recent_encounters": fhir_data.get("recent_encounters", []),
        }

        if include_pa_history:
            context["pa_history"] = await self.get_pa_history(patient_id)
        if include_denial_history:
            context["denial_history"] = await self.get_denial_history(patient_id)

        return context
