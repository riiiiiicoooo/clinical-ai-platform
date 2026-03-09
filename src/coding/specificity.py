"""
Code Specificity Optimizer — Ensures codes are at maximum specificity.

Identifies under-coded diagnoses and recommends more specific alternatives
based on available clinical documentation.
"""

import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class SpecificityRecommendation:
    """Recommendation to improve code specificity."""
    current_code: str
    current_display: str
    recommended_code: str
    recommended_display: str
    required_documentation: str
    estimated_revenue_delta: float  # Additional revenue from specificity


# Specificity upgrade paths
SPECIFICITY_UPGRADES = {
    # Diabetes
    "E11.9": [
        {"code": "E11.65", "display": "Type 2 DM with hyperglycemia",
         "doc_needed": "Document recent blood glucose > 250 mg/dL or HbA1c > 9%",
         "delta": 0.0},
        {"code": "E11.22", "display": "Type 2 DM with CKD",
         "doc_needed": "Document CKD stage and link to diabetes",
         "delta": 15.0},
        {"code": "E11.40", "display": "Type 2 DM with diabetic neuropathy",
         "doc_needed": "Document neuropathy symptoms and exam findings",
         "delta": 12.0},
        {"code": "E11.51", "display": "Type 2 DM with diabetic peripheral angiopathy",
         "doc_needed": "Document peripheral vascular disease and link to diabetes",
         "delta": 18.0},
    ],
    # Heart failure
    "I50.9": [
        {"code": "I50.22", "display": "Chronic systolic HF",
         "doc_needed": "Document systolic vs diastolic and acute vs chronic",
         "delta": 25.0},
        {"code": "I50.32", "display": "Chronic diastolic HF",
         "doc_needed": "Document diastolic dysfunction on echo",
         "delta": 25.0},
        {"code": "I50.42", "display": "Chronic combined systolic and diastolic HF",
         "doc_needed": "Document both systolic and diastolic dysfunction",
         "delta": 30.0},
    ],
    # CKD
    "N18.9": [
        {"code": "N18.3", "display": "CKD Stage 3",
         "doc_needed": "Document GFR 30-59 mL/min",
         "delta": 10.0},
        {"code": "N18.4", "display": "CKD Stage 4",
         "doc_needed": "Document GFR 15-29 mL/min",
         "delta": 20.0},
        {"code": "N18.5", "display": "CKD Stage 5",
         "doc_needed": "Document GFR < 15 mL/min",
         "delta": 35.0},
    ],
    # COPD
    "J44.9": [
        {"code": "J44.0", "display": "COPD with acute lower respiratory infection",
         "doc_needed": "Document concurrent respiratory infection",
         "delta": 15.0},
        {"code": "J44.1", "display": "COPD with acute exacerbation",
         "doc_needed": "Document acute worsening of symptoms",
         "delta": 12.0},
    ],
}


class SpecificityOptimizer:
    """
    Identifies under-coded diagnoses and recommends specificity upgrades.

    Analyzes current ICD-10-CM codes against clinical documentation
    to find opportunities for more specific coding that better
    represents clinical complexity and captures appropriate revenue.
    """

    def analyze(self, current_codes: list[str], clinical_text: str = "") -> list[SpecificityRecommendation]:
        """
        Analyze codes for specificity improvement opportunities.

        Returns recommendations sorted by estimated revenue impact.
        """
        recommendations = []

        for code in current_codes:
            upgrades = SPECIFICITY_UPGRADES.get(code, [])
            for upgrade in upgrades:
                rec = SpecificityRecommendation(
                    current_code=code,
                    current_display=self._get_display(code),
                    recommended_code=upgrade["code"],
                    recommended_display=upgrade["display"],
                    required_documentation=upgrade["doc_needed"],
                    estimated_revenue_delta=upgrade["delta"],
                )
                recommendations.append(rec)

        # Sort by revenue impact
        recommendations.sort(key=lambda r: r.estimated_revenue_delta, reverse=True)
        return recommendations

    def _get_display(self, code: str) -> str:
        """Get display name for an ICD-10 code."""
        DISPLAYS = {
            "E11.9": "Type 2 diabetes mellitus without complications",
            "I50.9": "Heart failure, unspecified",
            "N18.9": "Chronic kidney disease, unspecified",
            "J44.9": "Chronic obstructive pulmonary disease, unspecified",
            "I10": "Essential (primary) hypertension",
            "I25.10": "Atherosclerotic heart disease of native coronary artery",
        }
        return DISPLAYS.get(code, code)
