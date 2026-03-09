"""
Payer Criteria Matcher — Matches clinical evidence against payer coverage policies.

Loads payer-specific prior authorization criteria and checks whether
patient clinical data meets requirements for approval.
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class CoverageRequirement:
    """A single requirement in a payer's coverage criteria."""
    description: str
    category: str  # documentation, clinical, diagnostic, conservative_treatment
    required: bool = True
    met: bool = False
    evidence: str = ""


@dataclass
class CriteriaMatch:
    """Result of matching clinical data against payer criteria."""
    payer_name: str
    service_code: str
    pa_required: bool = True
    criteria_available: bool = True
    requirements: list[CoverageRequirement] = field(default_factory=list)
    match_score: float = 0.0  # 0-1.0
    likely_outcome: str = "unknown"  # approved, likely_approved, needs_more_info, likely_denied
    missing_requirements: list[str] = field(default_factory=list)
    turnaround_days: int = 3


# Payer-specific PA criteria (representative subset)
PAYER_CRITERIA = {
    "bcbs_nc": {
        "name": "Blue Cross Blue Shield of North Carolina",
        "criteria": {
            "27447": {  # Total Knee Replacement
                "pa_required": True,
                "requirements": [
                    {"desc": "BMI documented (ideally <40)", "category": "clinical"},
                    {"desc": "Failed 3+ months conservative treatment", "category": "conservative_treatment"},
                    {"desc": "Physical therapy documented (6+ sessions)", "category": "conservative_treatment"},
                    {"desc": "NSAID trial documented", "category": "conservative_treatment"},
                    {"desc": "Weight-bearing X-ray showing joint space narrowing", "category": "diagnostic"},
                    {"desc": "Functional limitation documented (WOMAC or similar)", "category": "clinical"},
                    {"desc": "No active infection", "category": "clinical"},
                ],
                "turnaround_days": 5,
            },
            "27130": {  # Total Hip Replacement
                "pa_required": True,
                "requirements": [
                    {"desc": "Failed conservative management 6+ weeks", "category": "conservative_treatment"},
                    {"desc": "Imaging showing hip joint deterioration", "category": "diagnostic"},
                    {"desc": "Functional limitation assessment", "category": "clinical"},
                    {"desc": "Pain documentation and VAS score", "category": "clinical"},
                ],
                "turnaround_days": 5,
            },
            "73721": {  # MRI Knee
                "pa_required": True,
                "requirements": [
                    {"desc": "X-ray performed first (unless acute injury)", "category": "diagnostic"},
                    {"desc": "Clinical indication documented", "category": "documentation"},
                    {"desc": "Conservative treatment trial if chronic", "category": "conservative_treatment"},
                ],
                "turnaround_days": 2,
            },
        },
    },
    "aetna": {
        "name": "Aetna",
        "criteria": {
            "27447": {
                "pa_required": True,
                "requirements": [
                    {"desc": "Documentation of knee osteoarthritis diagnosis", "category": "clinical"},
                    {"desc": "Failed non-surgical treatment 3+ months", "category": "conservative_treatment"},
                    {"desc": "Radiographic evidence of joint disease", "category": "diagnostic"},
                    {"desc": "Functional assessment (KOOS or similar)", "category": "clinical"},
                ],
                "turnaround_days": 3,
            },
        },
    },
    "unitedhealth": {
        "name": "UnitedHealthcare",
        "criteria": {
            "27447": {
                "pa_required": True,
                "requirements": [
                    {"desc": "Diagnosis of severe knee OA (K-L Grade 3 or 4)", "category": "clinical"},
                    {"desc": "Conservative treatment failure documented", "category": "conservative_treatment"},
                    {"desc": "Surgical candidacy assessment", "category": "clinical"},
                    {"desc": "BMI evaluation", "category": "clinical"},
                ],
                "turnaround_days": 5,
            },
        },
    },
}


class CriteriaMatcher:
    """
    Matches clinical documentation against payer coverage criteria.

    Uses loaded payer criteria to check whether patient clinical evidence
    meets requirements for PA approval. Identifies gaps and scores likelihood.
    """

    def __init__(self, custom_criteria: dict = None):
        self._criteria = {**PAYER_CRITERIA}
        if custom_criteria:
            self._criteria.update(custom_criteria)

    async def get_criteria(self, payer_id: str, cpt_code: str) -> dict:
        """Get PA criteria for a specific payer and service code."""
        payer = self._criteria.get(payer_id, {})
        if not payer:
            return {
                "payer_name": payer_id,
                "pa_required": True,
                "criteria_available": False,
                "requirements": [],
                "turnaround_days": 5,
            }

        criteria = payer.get("criteria", {}).get(cpt_code, {})
        if not criteria:
            return {
                "payer_name": payer.get("name", payer_id),
                "pa_required": True,
                "criteria_available": False,
                "requirements": [],
                "turnaround_days": 5,
            }

        return {
            "payer_name": payer.get("name", payer_id),
            "pa_required": criteria.get("pa_required", True),
            "criteria_available": True,
            "requirements": criteria.get("requirements", []),
            "turnaround_days": criteria.get("turnaround_days", 3),
        }

    async def match(
        self,
        payer_id: str,
        cpt_code: str,
        clinical_evidence: dict,
    ) -> CriteriaMatch:
        """
        Match clinical evidence against payer criteria.

        Returns match result with score, met/unmet requirements,
        and predicted outcome.
        """
        criteria_data = await self.get_criteria(payer_id, cpt_code)
        requirements = []
        met_count = 0

        for req in criteria_data.get("requirements", []):
            coverage_req = CoverageRequirement(
                description=req.get("desc", ""),
                category=req.get("category", "documentation"),
                required=True,
            )
            # Check if clinical evidence supports this requirement
            if self._check_requirement(coverage_req, clinical_evidence):
                coverage_req.met = True
                met_count += 1
            requirements.append(coverage_req)

        total = len(requirements)
        score = met_count / total if total > 0 else 0.0

        # Determine likely outcome
        if score >= 0.9:
            likely = "approved"
        elif score >= 0.7:
            likely = "likely_approved"
        elif score >= 0.5:
            likely = "needs_more_info"
        else:
            likely = "likely_denied"

        return CriteriaMatch(
            payer_name=criteria_data.get("payer_name", payer_id),
            service_code=cpt_code,
            pa_required=criteria_data.get("pa_required", True),
            criteria_available=criteria_data.get("criteria_available", True),
            requirements=requirements,
            match_score=score,
            likely_outcome=likely,
            missing_requirements=[r.description for r in requirements if not r.met],
            turnaround_days=criteria_data.get("turnaround_days", 3),
        )

    def _check_requirement(self, req: CoverageRequirement, evidence: dict) -> bool:
        """Check if clinical evidence satisfies a requirement. Rule-based matching."""
        desc_lower = req.description.lower()
        conditions = [c.get("display", "").lower() for c in evidence.get("conditions", [])]
        procedures = [p.get("display", "").lower() for p in evidence.get("procedures", [])]
        all_text = " ".join(conditions + procedures)

        if "bmi" in desc_lower and any("bmi" in c for c in conditions):
            return True
        if "x-ray" in desc_lower and any("x-ray" in p or "radiograph" in p for p in procedures):
            return True
        if "physical therapy" in desc_lower and any("therapy" in p for p in procedures):
            return True
        if "conservative" in desc_lower and len(evidence.get("medications", [])) > 0:
            return True
        if "imaging" in desc_lower and any("mri" in p or "ct" in p or "x-ray" in p for p in procedures):
            return True
        if "diagnosis" in desc_lower and len(conditions) > 0:
            return True

        return False
