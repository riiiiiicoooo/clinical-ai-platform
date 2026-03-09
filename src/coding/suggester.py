"""
Medical Code Suggester — ICD-10-CM and CPT code recommendation engine.

Combines NLP extraction output with code lookup tables to suggest
the most accurate and specific medical codes for billing.
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

from langsmith import traceable

logger = logging.getLogger(__name__)


@dataclass
class CodeSuggestion:
    """A suggested medical code with supporting evidence."""
    code: str
    system: str  # icd10, cpt
    display: str
    confidence: float  # 0-1.0
    source_text: str  # Clinical text supporting this code
    specificity: str  # optimal, could_be_more_specific, unspecified
    alternatives: list[str] = field(default_factory=list)
    revenue_impact: Optional[float] = None


@dataclass
class CodingSuggestionSet:
    """Complete set of coding suggestions for an encounter."""
    encounter_id: str
    diagnosis_codes: list[CodeSuggestion] = field(default_factory=list)
    procedure_codes: list[CodeSuggestion] = field(default_factory=list)
    modifier_suggestions: list[str] = field(default_factory=list)
    documentation_gaps: list[str] = field(default_factory=list)
    estimated_revenue_current: float = 0.0
    estimated_revenue_optimized: float = 0.0


# ICD-10-CM code specificity tree (subset)
ICD10_SPECIFICITY = {
    "E11": {
        "display": "Type 2 diabetes mellitus",
        "more_specific": {
            "E11.2": "with kidney complications",
            "E11.3": "with ophthalmic complications",
            "E11.4": "with neurological complications",
            "E11.5": "with circulatory complications",
            "E11.6": "with other specified complications",
            "E11.65": "with hyperglycemia",
            "E11.69": "with other specified complication",
            "E11.8": "with unspecified complications",
            "E11.9": "without complications (UNSPECIFIED — avoid)",
        },
    },
    "I10": {
        "display": "Essential (primary) hypertension",
        "note": "No further specificity available — I10 is the most specific code",
    },
    "I50": {
        "display": "Heart failure",
        "more_specific": {
            "I50.1": "Left ventricular failure, unspecified",
            "I50.2": "Systolic (congestive) heart failure",
            "I50.20": "Unspecified systolic",
            "I50.21": "Acute systolic",
            "I50.22": "Chronic systolic",
            "I50.23": "Acute on chronic systolic",
            "I50.3": "Diastolic (congestive) heart failure",
            "I50.30": "Unspecified diastolic",
            "I50.31": "Acute diastolic",
            "I50.32": "Chronic diastolic",
            "I50.33": "Acute on chronic diastolic",
            "I50.4": "Combined systolic and diastolic",
            "I50.9": "Heart failure, unspecified (AVOID)",
        },
    },
    "J44": {
        "display": "Other chronic obstructive pulmonary disease",
        "more_specific": {
            "J44.0": "with acute lower respiratory infection",
            "J44.1": "with acute exacerbation",
            "J44.9": "unspecified (AVOID when possible)",
        },
    },
    "N18": {
        "display": "Chronic kidney disease",
        "more_specific": {
            "N18.1": "Stage 1",
            "N18.2": "Stage 2 (mild)",
            "N18.3": "Stage 3 (moderate)",
            "N18.30": "Stage 3 unspecified",
            "N18.31": "Stage 3a",
            "N18.32": "Stage 3b",
            "N18.4": "Stage 4 (severe)",
            "N18.5": "Stage 5",
            "N18.6": "End stage renal disease",
            "N18.9": "Unspecified (AVOID — always stage if GFR available)",
        },
    },
}


class CodeSuggester:
    """
    Medical code suggestion engine.

    Takes NLP extraction output and suggests the most accurate
    ICD-10-CM and CPT codes with specificity optimization.
    """

    @traceable(name="coding.suggest_codes")
    async def suggest(self, nlp_extraction, encounter_note: str = "") -> CodingSuggestionSet:
        """
        Generate coding suggestions from NLP extraction output.

        Returns ICD-10-CM and CPT codes with confidence scores,
        specificity analysis, and revenue impact estimates.
        """
        suggestions = CodingSuggestionSet(encounter_id="")

        # Process conditions → ICD-10-CM codes
        for condition in nlp_extraction.conditions:
            if condition.icd10_code:
                specificity = self._check_specificity(condition.icd10_code)
                suggestion = CodeSuggestion(
                    code=condition.icd10_code,
                    system="icd10",
                    display=condition.snomed_display or condition.text,
                    confidence=condition.confidence,
                    source_text=condition.text,
                    specificity=specificity["status"],
                    alternatives=specificity.get("more_specific_options", []),
                )
                suggestions.diagnosis_codes.append(suggestion)

                if specificity["status"] == "could_be_more_specific":
                    suggestions.documentation_gaps.append(
                        f"Code {condition.icd10_code} could be more specific. "
                        f"Options: {', '.join(specificity.get('more_specific_options', [])[:3])}"
                    )

        # Process procedures → CPT codes
        for procedure in nlp_extraction.procedures:
            if procedure.cpt_code:
                suggestion = CodeSuggestion(
                    code=procedure.cpt_code,
                    system="cpt",
                    display=procedure.text,
                    confidence=procedure.confidence,
                    source_text=procedure.text,
                    specificity="optimal",
                )
                suggestions.procedure_codes.append(suggestion)

        return suggestions

    def _check_specificity(self, icd10_code: str) -> dict:
        """Check if an ICD-10 code can be more specific."""
        # Find the base code in specificity tree
        base_codes = [icd10_code[:3], icd10_code[:4], icd10_code[:5]]

        for base in base_codes:
            if base in ICD10_SPECIFICITY:
                tree = ICD10_SPECIFICITY[base]
                more_specific = tree.get("more_specific", {})

                if not more_specific:
                    return {"status": "optimal"}

                # Check if current code ends in .9 (unspecified)
                if icd10_code.endswith("9") or icd10_code.endswith(".9"):
                    options = [f"{k}: {v}" for k, v in more_specific.items() if not k.endswith("9")]
                    return {
                        "status": "could_be_more_specific",
                        "more_specific_options": options[:5],
                    }

                # Check if there are deeper codes available
                deeper = [k for k in more_specific if k.startswith(icd10_code) and k != icd10_code]
                if deeper:
                    return {
                        "status": "could_be_more_specific",
                        "more_specific_options": [f"{k}: {more_specific[k]}" for k in deeper[:5]],
                    }

        return {"status": "optimal"}
