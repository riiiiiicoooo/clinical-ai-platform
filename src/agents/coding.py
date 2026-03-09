"""
Medical Coding Agent — ICD-10/CPT code suggestion and optimization.

Analyzes clinical documentation to suggest the most accurate and specific
medical codes, checks bundling rules, and identifies under-coding opportunities.
"""

import logging
from typing import Any

from langsmith import traceable

from src.agents.base import BaseClinicalAgent, AgentConfig

logger = logging.getLogger(__name__)

CODING_SYSTEM_PROMPT = """You are a Certified Medical Coding AI Specialist working within a HIPAA-compliant
clinical operations platform for Meridian Health Partners.

Your responsibilities:
1. ANALYZE clinical encounter documentation to identify all billable diagnoses and procedures
2. SUGGEST the most specific ICD-10-CM diagnosis codes supported by documentation
3. SUGGEST accurate CPT procedure codes with appropriate modifiers
4. CHECK Correct Coding Initiative (CCI) edits for bundling compliance
5. IDENTIFY under-coding opportunities where documentation supports higher specificity
6. FLAG documentation gaps that prevent coding to highest specificity

CRITICAL CODING RULES:
- Code to the highest level of specificity supported by documentation (4th, 5th, 6th, 7th characters)
- Never upcode beyond what documentation supports — this is fraud
- Apply CCI bundling rules: some procedure combinations cannot be billed separately
- Include all relevant modifiers (25, 59, 76, 77, etc.) when applicable
- Document the source clinical text that supports each code
- Flag "query opportunities" where additional documentation could support a higher-specificity code

ICD-10-CM SPECIFICITY RULES:
- Always prefer specific codes over unspecified (e.g., E11.65 over E11.9 for diabetes with hyperglycemia)
- Laterality required where applicable (right/left/bilateral)
- 7th character extensions for injuries (A = initial, D = subsequent, S = sequela)
- Combination codes preferred over multiple codes (e.g., E11.65 diabetes with hyperglycemia)

CPT MODIFIER RULES:
- 25: Significant, separately identifiable E/M service
- 59: Distinct procedural service (CCI edit override)
- 76: Repeat procedure by same physician
- 77: Repeat procedure by another physician
- LT/RT: Left/right side

OUTPUT FORMAT:
```
CODING ANALYSIS
===============
Encounter: [Type] — [Date]
Provider: [Name]

DIAGNOSIS CODES (ICD-10-CM):
1. [Code] — [Description]
   Source: "[Exact text from documentation]"
   Specificity: [Optimal / Could be more specific / Unspecified]

2. [Code] — [Description]
   Source: "[Exact text from documentation]"

PROCEDURE CODES (CPT):
1. [Code] [Modifier] — [Description]
   Source: "[Exact text from documentation]"
   CCI Check: [Pass / Bundling conflict with Code X]

UNDER-CODING OPPORTUNITIES:
- [Current code] → [Suggested more specific code]
  Required documentation: "[What clinician needs to document]"

DOCUMENTATION GAPS:
- [Missing element that prevents higher specificity]

ESTIMATED REVENUE IMPACT:
- Current coding: $[estimate]
- Optimized coding: $[estimate]
- Difference: $[estimate]
```"""


class CodingAgent(BaseClinicalAgent):
    """
    Medical coding intelligence agent.

    Capabilities:
    - ICD-10-CM diagnosis code suggestion from clinical notes
    - CPT procedure code suggestion with modifiers
    - CCI bundling compliance checking
    - Under-coding detection and revenue optimization
    - Documentation gap identification
    """

    def __init__(self, model_router, audit_logger):
        config = AgentConfig(
            name="medical_coding",
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            temperature=0.05,  # Very low temp for coding accuracy
            daily_budget=60.0,
            per_request_limit=0.30,
            tools=["icd10_lookup", "cpt_lookup", "cci_check", "code_specificity_check"],
            requires_phi_access=True,
            audit_level="full",
        )
        super().__init__(config, model_router, audit_logger)

    def get_system_prompt(self) -> str:
        return CODING_SYSTEM_PROMPT

    @traceable(name="coding.build_context")
    async def build_context(self, request: dict, patient_data: dict) -> str:
        """Build coding-specific prompt with clinical documentation."""
        patient = patient_data.get("patient", {})
        conditions = patient_data.get("conditions", [])
        medications = patient_data.get("medications", [])

        # NLP extraction results (from clinical NLP pipeline)
        nlp_extraction = request.get("nlp_extraction", {})
        extracted_conditions = nlp_extraction.get("conditions", [])
        extracted_procedures = nlp_extraction.get("procedures", [])

        encounter_note = request.get("encounter_note", "")
        encounter_type = request.get("encounter_type", "office visit")

        conditions_text = "\n".join(
            f"  - {c['display']} (SNOMED: {c.get('code', 'N/A')})" for c in conditions
        ) or "  None on file"

        nlp_conditions = "\n".join(
            f"  - {c.text} → SNOMED: {c.snomed_code or 'unmapped'}, ICD-10: {c.icd10_code or 'unmapped'}"
            for c in extracted_conditions
        ) or "  No conditions extracted"

        nlp_procedures = "\n".join(
            f"  - {c.text} → CPT: {c.cpt_code or 'unmapped'}"
            for c in extracted_procedures
        ) or "  No procedures extracted"

        return f"""Analyze this clinical encounter and provide coding recommendations:

ENCOUNTER TYPE: {encounter_type}
PATIENT: {patient.get('name', 'Unknown')}, DOB: {patient.get('dob', 'Unknown')}

CLINICAL NOTE:
{encounter_note}

ACTIVE CONDITIONS ON FILE:
{conditions_text}

NLP-EXTRACTED CONDITIONS:
{nlp_conditions}

NLP-EXTRACTED PROCEDURES:
{nlp_procedures}

CURRENT MEDICATIONS:
{chr(10).join(f"  - {m['display']} {m.get('dosage', '')}" for m in medications) or "  None on file"}

Please provide your complete coding analysis with ICD-10-CM and CPT codes,
specificity recommendations, CCI edit checks, and revenue impact estimate.
"""
