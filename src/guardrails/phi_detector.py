"""
PHI Detector — Identifies and masks Protected Health Information in text.

Uses regex patterns and Microsoft Presidio-compatible detection for
the 18 HIPAA Safe Harbor identifiers. Prevents PHI leakage in
LLM prompts, responses, and logs.
"""

import re
import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class PHIDetection:
    """A detected PHI element in text."""
    text: str
    phi_type: str
    start: int
    end: int
    confidence: float


# HIPAA Safe Harbor: 18 identifiers to detect
PHI_PATTERNS = {
    "SSN": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "PHONE": re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"),
    "EMAIL": re.compile(r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b"),
    "MRN": re.compile(r"\bMRN[:\s#]*\d{6,10}\b", re.IGNORECASE),
    "ACCOUNT_NUMBER": re.compile(r"\bACCT[:\s#]*\d{8,12}\b", re.IGNORECASE),
    "MEMBER_ID": re.compile(r"\bMEMBER\s*(?:ID)?[:\s#]*[A-Z0-9]{8,15}\b", re.IGNORECASE),
    "POLICY_NUMBER": re.compile(r"\bPOLICY[:\s#]*[A-Z0-9]{6,15}\b", re.IGNORECASE),
    "IP_ADDRESS": re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b"),
    "URL": re.compile(r"https?://[^\s<>\"]+"),
    "ZIP_CODE": re.compile(r"\b\d{5}(?:-\d{4})?\b"),
    "DATE_OF_BIRTH": re.compile(
        r"\b(?:DOB|Date of Birth|Birth Date)[:\s]*\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b",
        re.IGNORECASE,
    ),
    "DATE_FULL": re.compile(
        r"\b(?:0[1-9]|1[0-2])[/-](?:0[1-9]|[12]\d|3[01])[/-](?:19|20)\d{2}\b"
    ),
    "VEHICLE_ID": re.compile(r"\b[A-HJ-NPR-Z0-9]{17}\b"),  # VIN
    "DEA_NUMBER": re.compile(r"\b[ABFM][A-Z]\d{7}\b"),  # DEA registration
    "NPI": re.compile(r"\bNPI[:\s#]*\d{10}\b", re.IGNORECASE),
    "CLAIM_NUMBER": re.compile(r"\bCLAIM[:\s#]*[A-Z0-9]{8,15}\b", re.IGNORECASE),
}

# Name detection (simplified — in production use Presidio with trained NER)
NAME_PATTERN = re.compile(
    r"\b(?:Patient|Pt|Mr\.|Mrs\.|Ms\.|Dr\.)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})\b"
)


class PHIDetector:
    """
    Detects Protected Health Information in text.

    Scans for HIPAA Safe Harbor identifiers using regex patterns.
    In production, integrates with Microsoft Presidio for more
    accurate detection with NER-based name/location identification.
    """

    def __init__(self, custom_patterns: dict = None):
        self._patterns = {**PHI_PATTERNS}
        if custom_patterns:
            self._patterns.update(custom_patterns)

    def detect(self, text: str) -> list[PHIDetection]:
        """Detect all PHI elements in text."""
        detections = []

        for phi_type, pattern in self._patterns.items():
            for match in pattern.finditer(text):
                detections.append(PHIDetection(
                    text=match.group(0),
                    phi_type=phi_type,
                    start=match.start(),
                    end=match.end(),
                    confidence=0.9,
                ))

        # Name detection
        for match in NAME_PATTERN.finditer(text):
            detections.append(PHIDetection(
                text=match.group(1),
                phi_type="NAME",
                start=match.start(1),
                end=match.end(1),
                confidence=0.7,
            ))

        # Sort by position
        detections.sort(key=lambda d: d.start)
        return detections

    def mask(self, text: str, mask_char: str = "X") -> str:
        """Replace all detected PHI with mask characters."""
        detections = self.detect(text)
        masked = text

        # Replace in reverse order to preserve positions
        for detection in reversed(detections):
            replacement = f"[{detection.phi_type}]"
            masked = masked[:detection.start] + replacement + masked[detection.end:]

        return masked

    def has_phi(self, text: str) -> bool:
        """Quick check: does text contain any PHI?"""
        for pattern in self._patterns.values():
            if pattern.search(text):
                return True
        if NAME_PATTERN.search(text):
            return True
        return False

    def safe_for_logging(self, text: str) -> str:
        """Mask PHI for safe inclusion in application logs."""
        return self.mask(text)
