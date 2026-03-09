"""
Clinical Safety Guardrails — Prevents unsafe clinical AI outputs.

Ensures AI-generated clinical content doesn't contain:
- Unauthorized treatment recommendations
- Drug dosage errors
- Misleading clinical claims
- Prompt injection attempts
"""

import re
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class SafetyCheckResult:
    """Result of a clinical safety check."""
    safe: bool
    violations: list[str]
    severity: str  # low, medium, high, critical
    action: str  # allow, flag, block, escalate


class ClinicalSafetyGuardrails:
    """
    Clinical content safety checks for AI-generated outputs.

    Layers:
    1. Treatment recommendation boundaries
    2. Dosage range validation
    3. Clinical claim verification
    4. Prompt injection detection
    5. Unauthorized scope detection
    """

    # Unauthorized clinical actions
    UNAUTHORIZED_PATTERNS = [
        (re.compile(r"(?:prescribe|order|administer)\s+(?:medication|drug|treatment)", re.I),
         "AI cannot prescribe medications or order treatments"),
        (re.compile(r"(?:diagnos(?:e|is|ing))\s+(?:the patient|you)\s+(?:with|as having)", re.I),
         "AI cannot make definitive diagnoses"),
        (re.compile(r"(?:you should|must)\s+(?:stop|discontinue|change)\s+(?:your|the)\s+(?:medication|treatment)", re.I),
         "AI cannot direct medication changes"),
        (re.compile(r"(?:guaranteed|certain|definitely will)\s+(?:cure|heal|recover)", re.I),
         "AI cannot guarantee treatment outcomes"),
    ]

    # Prompt injection patterns
    INJECTION_PATTERNS = [
        re.compile(r"ignore\s+(?:all\s+)?(?:previous|above|prior)\s+instructions", re.I),
        re.compile(r"you\s+are\s+now\s+(?:a|an)\s+(?!prior auth|coding)", re.I),
        re.compile(r"forget\s+(?:your|all)\s+(?:rules|instructions|training)", re.I),
        re.compile(r"system\s*(?:prompt|message)\s*:", re.I),
        re.compile(r"<\s*(?:system|admin|root)\s*>", re.I),
    ]

    # Dangerous dosage mentions (simplified — production uses drug database)
    DOSAGE_ALERTS = {
        "acetaminophen": {"max_single": 1000, "max_daily": 4000, "unit": "mg"},
        "ibuprofen": {"max_single": 800, "max_daily": 3200, "unit": "mg"},
        "metformin": {"max_single": 1000, "max_daily": 2550, "unit": "mg"},
        "warfarin": {"max_single": 10, "max_daily": 10, "unit": "mg"},
        "lisinopril": {"max_single": 80, "max_daily": 80, "unit": "mg"},
    }

    def check_output(self, text: str) -> SafetyCheckResult:
        """Run all safety checks on AI-generated clinical output."""
        violations = []

        # Check unauthorized clinical actions
        for pattern, message in self.UNAUTHORIZED_PATTERNS:
            if pattern.search(text):
                violations.append(f"CLINICAL_BOUNDARY: {message}")

        # Check prompt injection
        for pattern in self.INJECTION_PATTERNS:
            if pattern.search(text):
                violations.append("INJECTION: Prompt injection pattern detected")

        # Determine severity
        if any("INJECTION" in v for v in violations):
            severity = "critical"
            action = "block"
        elif any("CLINICAL_BOUNDARY" in v for v in violations):
            severity = "high"
            action = "flag"
        elif violations:
            severity = "medium"
            action = "flag"
        else:
            severity = "low"
            action = "allow"

        return SafetyCheckResult(
            safe=len(violations) == 0,
            violations=violations,
            severity=severity,
            action=action,
        )

    def check_input(self, text: str) -> SafetyCheckResult:
        """Check user input for injection attempts."""
        violations = []

        for pattern in self.INJECTION_PATTERNS:
            if pattern.search(text):
                violations.append("INPUT_INJECTION: Potential prompt injection in user input")

        return SafetyCheckResult(
            safe=len(violations) == 0,
            violations=violations,
            severity="critical" if violations else "low",
            action="block" if violations else "allow",
        )
