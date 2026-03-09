"""
FHIR R4 Resource Models — Pydantic models for healthcare data exchange.

Typed representations of key FHIR resources used in clinical AI processing.
"""

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel


class FHIRCoding(BaseModel):
    system: str = ""
    code: str = ""
    display: str = ""


class FHIRCodeableConcept(BaseModel):
    coding: list[FHIRCoding] = []
    text: str = ""


class PatientResource(BaseModel):
    id: str
    name: str
    birth_date: Optional[date] = None
    gender: Optional[str] = None
    mrn: Optional[str] = None  # Medical Record Number


class ConditionResource(BaseModel):
    id: str
    code: FHIRCodeableConcept
    clinical_status: str = "active"
    onset_date: Optional[datetime] = None
    severity: Optional[str] = None


class MedicationResource(BaseModel):
    id: str
    code: FHIRCodeableConcept
    dosage: str = ""
    frequency: str = ""
    route: str = ""
    status: str = "active"


class ObservationResource(BaseModel):
    id: str
    code: FHIRCodeableConcept
    value: Optional[float] = None
    unit: str = ""
    effective_date: Optional[datetime] = None
    status: str = "final"
    reference_range_low: Optional[float] = None
    reference_range_high: Optional[float] = None


class EncounterResource(BaseModel):
    id: str
    encounter_type: str = ""
    status: str = ""
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None
    encounter_class: str = ""  # ambulatory, emergency, inpatient
    provider_id: Optional[str] = None


class AllergyResource(BaseModel):
    id: str
    code: FHIRCodeableConcept
    criticality: str = ""  # low, high, unable-to-assess
    reactions: list[str] = []


class PriorAuthRequest(BaseModel):
    """FHIR-based prior authorization request structure."""
    patient_id: str
    encounter_id: Optional[str] = None
    service_code: FHIRCodeableConcept  # CPT code for requested service
    diagnosis_codes: list[FHIRCodeableConcept] = []  # ICD-10 codes
    provider_id: str
    payer_id: str
    urgency: str = "routine"  # routine, urgent, emergent
    clinical_justification: str = ""
    supporting_documents: list[str] = []  # Document reference IDs


class PriorAuthResponse(BaseModel):
    """FHIR-based prior authorization response."""
    request_id: str
    status: str  # approved, denied, pended, cancelled
    decision_date: Optional[datetime] = None
    auth_number: Optional[str] = None
    denial_reason: Optional[str] = None
    valid_from: Optional[date] = None
    valid_to: Optional[date] = None
    approved_units: Optional[int] = None
