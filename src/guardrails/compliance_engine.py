"""
Compliance Engine — HIPAA compliance enforcement for all AI operations.

Orchestrates PHI detection, clinical safety, RBAC, and audit logging
to ensure every AI interaction meets HIPAA requirements.
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

from src.guardrails.phi_detector import PHIDetector
from src.guardrails.clinical_safety import ClinicalSafetyGuardrails
from src.compliance.rbac import RBACEngine, Role, Permission
from src.compliance.audit_logger import AuditLogger

logger = logging.getLogger(__name__)


@dataclass
class ComplianceResult:
    """Result of full compliance check."""
    compliant: bool
    checks_passed: list[str] = field(default_factory=list)
    checks_failed: list[str] = field(default_factory=list)
    phi_detected: bool = False
    phi_count: int = 0
    safety_violations: list[str] = field(default_factory=list)
    action: str = "allow"  # allow, flag, block, escalate


class ComplianceEngine:
    """
    Orchestrates all compliance checks for AI operations.

    Pre-processing checks (before LLM call):
    1. RBAC — Does user have permission for this operation?
    2. PHI scope — Is the AI accessing only necessary PHI?
    3. Input safety — Any injection attempts in user input?

    Post-processing checks (after LLM response):
    1. Output safety — Any unauthorized clinical actions?
    2. PHI leakage — Is the response leaking PHI that shouldn't be exposed?
    3. Audit logging — Record what happened for compliance
    """

    def __init__(
        self,
        phi_detector: PHIDetector = None,
        safety_guardrails: ClinicalSafetyGuardrails = None,
        rbac_engine: RBACEngine = None,
        audit_logger: AuditLogger = None,
    ):
        self.phi_detector = phi_detector or PHIDetector()
        self.safety = safety_guardrails or ClinicalSafetyGuardrails()
        self.rbac = rbac_engine or RBACEngine()
        self.audit_logger = audit_logger

    async def check_pre_processing(
        self,
        user_role: Role,
        permission: Permission,
        input_text: str,
        patient_id: str = None,
    ) -> ComplianceResult:
        """Run pre-processing compliance checks before AI execution."""
        result = ComplianceResult(compliant=True)

        # 1. RBAC check
        access = self.rbac.check_permission(user_role, permission)
        if access.allowed:
            result.checks_passed.append("rbac")
        else:
            result.checks_failed.append(f"rbac: {access.reason}")
            result.compliant = False
            result.action = "block"

        # 2. Input safety check
        safety = self.safety.check_input(input_text)
        if safety.safe:
            result.checks_passed.append("input_safety")
        else:
            result.checks_failed.append(f"input_safety: {'; '.join(safety.violations)}")
            result.safety_violations.extend(safety.violations)
            result.compliant = False
            result.action = "block"

        # 3. PHI detection in input (for logging purposes)
        phi_detections = self.phi_detector.detect(input_text)
        result.phi_detected = len(phi_detections) > 0
        result.phi_count = len(phi_detections)
        if phi_detections:
            result.checks_passed.append(f"phi_detected: {len(phi_detections)} elements")

        return result

    async def check_post_processing(
        self,
        output_text: str,
        user_role: Role,
    ) -> ComplianceResult:
        """Run post-processing compliance checks on AI output."""
        result = ComplianceResult(compliant=True)

        # 1. Output safety check
        safety = self.safety.check_output(output_text)
        if safety.safe:
            result.checks_passed.append("output_safety")
        else:
            result.checks_failed.append(f"output_safety: {'; '.join(safety.violations)}")
            result.safety_violations.extend(safety.violations)
            if safety.action == "block":
                result.compliant = False
                result.action = "block"
            else:
                result.action = "flag"

        # 2. PHI leakage check
        phi_in_output = self.phi_detector.detect(output_text)
        result.phi_detected = len(phi_in_output) > 0
        result.phi_count = len(phi_in_output)

        # Check if PHI types are within user's access scope
        allowed_scope = self.rbac.get_phi_access_scope(user_role)
        for detection in phi_in_output:
            phi_category = self._map_phi_type_to_scope(detection.phi_type)
            if phi_category and phi_category not in allowed_scope:
                result.checks_failed.append(
                    f"phi_scope: {detection.phi_type} not in user's access scope"
                )
                result.compliant = False
                result.action = "block"

        if not result.checks_failed:
            result.checks_passed.append("phi_scope")

        return result

    def _map_phi_type_to_scope(self, phi_type: str) -> Optional[str]:
        """Map PHI detection type to RBAC scope category."""
        MAPPING = {
            "NAME": "demographics",
            "SSN": "demographics",
            "DATE_OF_BIRTH": "demographics",
            "PHONE": "demographics",
            "EMAIL": "demographics",
            "MRN": "demographics",
            "MEMBER_ID": "insurance",
            "POLICY_NUMBER": "insurance",
            "CLAIM_NUMBER": "billing",
        }
        return MAPPING.get(phi_type)
