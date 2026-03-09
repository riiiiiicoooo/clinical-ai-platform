"""
PA Appeals Engine — Generates evidence-based appeal letters for denied PAs.

Analyzes denial reasons, identifies supporting clinical evidence,
references clinical guidelines, and drafts professional appeal letters.
"""

import logging
from dataclasses import dataclass
from typing import Optional

from langsmith import traceable

logger = logging.getLogger(__name__)


@dataclass
class AppealData:
    """Data needed to generate a PA appeal."""
    pa_id: str
    patient_id: str
    service_code: str
    service_description: str
    payer_name: str
    denial_reason: str
    denial_code: Optional[str] = None
    original_submission_date: Optional[str] = None
    auth_number: Optional[str] = None


# Common denial reasons and appeal strategies
DENIAL_STRATEGIES = {
    "medical_necessity": {
        "approach": "Provide additional clinical evidence supporting medical necessity",
        "key_elements": [
            "Reference specific clinical guidelines (ACC/AHA, AAOS, etc.)",
            "Document failed conservative treatments with dates and outcomes",
            "Include objective clinical measurements (ROM, VAS scores, imaging findings)",
            "Cite peer-reviewed literature supporting treatment effectiveness",
        ],
    },
    "documentation_insufficient": {
        "approach": "Submit additional supporting documentation",
        "key_elements": [
            "Identify specifically what documentation was missing",
            "Gather and attach missing documents",
            "Provide cover letter explaining additions",
            "Include chronological clinical summary",
        ],
    },
    "experimental_investigational": {
        "approach": "Demonstrate treatment is standard of care",
        "key_elements": [
            "Cite FDA approval status",
            "Reference clinical practice guidelines recommending treatment",
            "Provide published clinical trial results",
            "Note major medical society endorsements",
        ],
    },
    "not_covered": {
        "approach": "Review plan documents and argue coverage applies",
        "key_elements": [
            "Review specific plan language regarding coverage",
            "Identify applicable benefit categories",
            "Reference state mandates if applicable",
            "Consider external review rights",
        ],
    },
}


class AppealsEngine:
    """
    Generates structured appeal data for the PA Agent to draft appeal letters.

    Analyzes denial reasons, identifies relevant appeal strategies,
    gathers supporting clinical evidence, and provides framework
    for the LLM-powered appeal letter generation.
    """

    def __init__(self, knowledge_store=None):
        self.knowledge_store = knowledge_store

    @traceable(name="appeals.prepare_appeal")
    async def prepare_appeal(self, appeal_data: AppealData, clinical_evidence: dict) -> dict:
        """
        Prepare appeal context for the PA Agent.

        Returns structured data the agent uses to generate the appeal letter.
        """
        # Identify denial category and strategy
        denial_category = self._categorize_denial(appeal_data.denial_reason)
        strategy = DENIAL_STRATEGIES.get(denial_category, DENIAL_STRATEGIES["medical_necessity"])

        # Find relevant clinical guidelines
        guidelines = await self._find_guidelines(appeal_data.service_code)

        # Find similar successful appeals
        similar_appeals = await self._find_similar_appeals(
            appeal_data.service_code,
            appeal_data.payer_name,
            denial_category,
        )

        return {
            "denial_category": denial_category,
            "strategy": strategy,
            "clinical_guidelines": guidelines,
            "similar_appeals": similar_appeals,
            "clinical_evidence": clinical_evidence,
            "appeal_data": {
                "pa_id": appeal_data.pa_id,
                "service": f"CPT {appeal_data.service_code} — {appeal_data.service_description}",
                "payer": appeal_data.payer_name,
                "denial_reason": appeal_data.denial_reason,
                "denial_code": appeal_data.denial_code,
                "original_date": appeal_data.original_submission_date,
            },
        }

    def _categorize_denial(self, denial_reason: str) -> str:
        """Categorize denial reason into appeal strategy bucket."""
        reason_lower = denial_reason.lower()

        if any(kw in reason_lower for kw in ["medical necessity", "not medically necessary", "necessity"]):
            return "medical_necessity"
        elif any(kw in reason_lower for kw in ["documentation", "insufficient", "missing", "incomplete"]):
            return "documentation_insufficient"
        elif any(kw in reason_lower for kw in ["experimental", "investigational", "not proven"]):
            return "experimental_investigational"
        elif any(kw in reason_lower for kw in ["not covered", "excluded", "not a benefit"]):
            return "not_covered"
        else:
            return "medical_necessity"  # Default

    async def _find_guidelines(self, service_code: str) -> list[dict]:
        """Find relevant clinical practice guidelines for the service."""
        # In production: search medical knowledge base
        GUIDELINE_MAP = {
            "27447": [
                {"source": "AAOS", "title": "Management of Osteoarthritis of the Knee (3rd Ed.)", "year": 2021},
                {"source": "ACR/AF", "title": "Guideline for Management of OA of the Hand, Hip, and Knee", "year": 2020},
            ],
            "27130": [
                {"source": "AAOS", "title": "Management of Osteoarthritis of the Hip", "year": 2017},
                {"source": "NICE", "title": "Joint Replacement (Primary): Hip, Knee and Shoulder", "year": 2020},
            ],
            "93306": [
                {"source": "ACC/AHA", "title": "Guideline for Management of Heart Failure", "year": 2022},
                {"source": "ASE", "title": "Recommendations for Cardiac Chamber Quantification", "year": 2015},
            ],
        }
        return GUIDELINE_MAP.get(service_code, [])

    async def _find_similar_appeals(self, service_code: str, payer: str, category: str) -> list[dict]:
        """Find similar past appeals and their outcomes."""
        # In production: query historical appeal database
        return [
            {
                "service": service_code,
                "payer": payer,
                "outcome": "overturned",
                "key_factor": "Additional imaging evidence provided",
            }
        ]
