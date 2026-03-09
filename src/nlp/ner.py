"""
Medical Named Entity Recognition — Enhanced NER for clinical text.

Extends SciSpaCy NER with custom medical entity patterns for
medications, dosages, lab values, and clinical measurements.
"""

import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class MedicationMention:
    """Structured medication mention from clinical text."""
    drug_name: str
    dose: Optional[str] = None
    frequency: Optional[str] = None
    route: Optional[str] = None
    start: int = 0
    end: int = 0


@dataclass
class LabValueMention:
    """Structured lab value mention from clinical text."""
    test_name: str
    value: Optional[float] = None
    unit: Optional[str] = None
    reference_range: Optional[str] = None
    is_abnormal: bool = False
    start: int = 0
    end: int = 0


class MedicalNER:
    """
    Enhanced medical NER with regex-based pattern matching.

    Catches structured mentions that SciSpaCy may miss:
    - Medication dosages: "Lisinopril 10mg PO daily"
    - Lab values: "HbA1c 7.2%", "WBC 12.5 K/uL"
    - Vital signs: "BP 140/90", "HR 88 bpm"
    - Clinical measurements: "BMI 28.3"
    """

    # Medication patterns
    MEDICATION_PATTERN = re.compile(
        r"(?P<drug>[A-Z][a-z]+(?:\s[A-Z][a-z]+)?)\s+"
        r"(?P<dose>\d+(?:\.\d+)?\s*(?:mg|mcg|g|mL|units|IU))"
        r"(?:\s+(?P<route>PO|IV|IM|SQ|SC|PR|SL|INH|TOP|TD|OP))?"
        r"(?:\s+(?P<freq>daily|BID|TID|QID|q\d+h|PRN|QHS|QAM|QPM|weekly|monthly))?"
    )

    # Lab value patterns
    LAB_PATTERNS = [
        # HbA1c 7.2%, Glucose 120 mg/dL, WBC 12.5 K/uL
        re.compile(
            r"(?P<test>HbA1c|A1C|glucose|WBC|RBC|Hgb|Hct|PLT|BUN|Cr|creatinine|"
            r"Na|K|Cl|CO2|Ca|Mg|Phos|AST|ALT|ALP|Tbili|albumin|TSH|T4|T3|"
            r"INR|PT|PTT|ESR|CRP|troponin|BNP|proBNP|ferritin|iron|TIBC|"
            r"LDL|HDL|cholesterol|triglycerides|GFR|eGFR|lactate|procalcitonin)"
            r"\s*[=:of]*\s*(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>%|mg/dL|g/dL|K/uL|"
            r"mEq/L|mmol/L|U/L|ng/mL|pg/mL|mcg/dL|mL/min|seconds|sec)?",
            re.IGNORECASE,
        ),
    ]

    # Vital sign patterns
    VITAL_PATTERNS = {
        "blood_pressure": re.compile(r"BP\s*[=:]*\s*(?P<sys>\d{2,3})/(?P<dia>\d{2,3})"),
        "heart_rate": re.compile(r"(?:HR|heart rate|pulse)\s*[=:]*\s*(?P<value>\d{2,3})\s*(?:bpm)?", re.IGNORECASE),
        "temperature": re.compile(r"(?:Temp|temperature)\s*[=:]*\s*(?P<value>\d{2,3}(?:\.\d)?)\s*(?:°?[FC])?", re.IGNORECASE),
        "respiratory_rate": re.compile(r"(?:RR|resp rate)\s*[=:]*\s*(?P<value>\d{1,2})", re.IGNORECASE),
        "spo2": re.compile(r"(?:SpO2|O2 sat|oxygen sat)\s*[=:]*\s*(?P<value>\d{2,3})%?", re.IGNORECASE),
        "bmi": re.compile(r"BMI\s*[=:]*\s*(?P<value>\d{2}(?:\.\d)?)", re.IGNORECASE),
    }

    def extract_medications(self, text: str) -> list[MedicationMention]:
        """Extract structured medication mentions from text."""
        mentions = []
        for match in self.MEDICATION_PATTERN.finditer(text):
            mentions.append(MedicationMention(
                drug_name=match.group("drug"),
                dose=match.group("dose"),
                frequency=match.group("freq"),
                route=match.group("route"),
                start=match.start(),
                end=match.end(),
            ))
        return mentions

    def extract_lab_values(self, text: str) -> list[LabValueMention]:
        """Extract structured lab values from text."""
        mentions = []
        for pattern in self.LAB_PATTERNS:
            for match in pattern.finditer(text):
                value = float(match.group("value"))
                test = match.group("test").lower()
                mentions.append(LabValueMention(
                    test_name=match.group("test"),
                    value=value,
                    unit=match.group("unit") or "",
                    is_abnormal=self._is_abnormal(test, value),
                    start=match.start(),
                    end=match.end(),
                ))
        return mentions

    def extract_vitals(self, text: str) -> dict:
        """Extract vital signs from text."""
        vitals = {}
        for vital_name, pattern in self.VITAL_PATTERNS.items():
            match = pattern.search(text)
            if match:
                if vital_name == "blood_pressure":
                    vitals[vital_name] = {
                        "systolic": int(match.group("sys")),
                        "diastolic": int(match.group("dia")),
                    }
                else:
                    vitals[vital_name] = float(match.group("value"))
        return vitals

    def _is_abnormal(self, test: str, value: float) -> bool:
        """Check if a lab value is outside normal range."""
        NORMAL_RANGES = {
            "hba1c": (4.0, 5.6),
            "a1c": (4.0, 5.6),
            "glucose": (70, 100),
            "wbc": (4.5, 11.0),
            "hgb": (12.0, 17.5),
            "hct": (36.0, 51.0),
            "plt": (150, 400),
            "bun": (7, 20),
            "cr": (0.6, 1.2),
            "creatinine": (0.6, 1.2),
            "na": (136, 145),
            "k": (3.5, 5.0),
            "gfr": (60, 120),
            "egfr": (60, 120),
            "tsh": (0.4, 4.0),
            "ldl": (0, 100),
            "hdl": (40, 60),
            "triglycerides": (0, 150),
            "ast": (10, 40),
            "alt": (7, 56),
            "inr": (0.8, 1.2),
            "lactate": (0.5, 2.0),
        }
        normal = NORMAL_RANGES.get(test)
        if normal:
            return value < normal[0] or value > normal[1]
        return False
