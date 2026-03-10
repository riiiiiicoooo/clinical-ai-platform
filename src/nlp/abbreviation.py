"""
Clinical Abbreviation Resolver — Expands medical abbreviations in text.

Healthcare text is dense with abbreviations (HTN, CHF, DM2, SOB, etc.).
This resolver expands them to improve downstream NER and concept linking.
"""

import re


# Common clinical abbreviations and their expansions
CLINICAL_ABBREVIATIONS = {
    # Conditions
    "HTN": "hypertension",
    "DM": "diabetes mellitus",
    "DM1": "diabetes mellitus type 1",
    "DM2": "diabetes mellitus type 2",
    "T2DM": "type 2 diabetes mellitus",
    "CHF": "congestive heart failure",
    "HF": "heart failure",
    "CAD": "coronary artery disease",
    "COPD": "chronic obstructive pulmonary disease",
    "CKD": "chronic kidney disease",
    "ESRD": "end-stage renal disease",
    "AFib": "atrial fibrillation",
    "A-fib": "atrial fibrillation",
    "DVT": "deep vein thrombosis",
    "PE": "pulmonary embolism",
    "CVA": "cerebrovascular accident",
    "TIA": "transient ischemic attack",
    "MI": "myocardial infarction",
    "STEMI": "ST elevation myocardial infarction",
    "NSTEMI": "non-ST elevation myocardial infarction",
    "PNA": "pneumonia",
    "UTI": "urinary tract infection",
    "GERD": "gastroesophageal reflux disease",
    "OA": "osteoarthritis",
    "RA": "rheumatoid arthritis",
    "OSA": "obstructive sleep apnea",
    "BPH": "benign prostatic hyperplasia",
    "AKI": "acute kidney injury",
    "ARDS": "acute respiratory distress syndrome",
    "SLE": "systemic lupus erythematosus",
    "MS": "multiple sclerosis",

    # Symptoms
    "SOB": "shortness of breath",
    "DOE": "dyspnea on exertion",
    "CP": "chest pain",
    "HA": "headache",
    "N/V": "nausea and vomiting",
    "LOC": "loss of consciousness",
    "AMS": "altered mental status",
    "JVD": "jugular venous distension",

    # Clinical terms
    "PMH": "past medical history",
    "PSH": "past surgical history",
    "FH": "family history",
    "SH": "social history",
    "HPI": "history of present illness",
    "CC": "chief complaint",
    "ROS": "review of systems",
    "A&P": "assessment and plan",
    "RTC": "return to clinic",
    "F/U": "follow up",
    "PRN": "as needed",
    "BID": "twice daily",
    "TID": "three times daily",
    "QID": "four times daily",
    "QHS": "every night at bedtime",
    "QAM": "every morning",
    "QPM": "every evening",
    "PO": "by mouth",
    "IV": "intravenous",
    "IM": "intramuscular",
    "SQ": "subcutaneous",
    "SL": "sublingual",
    "INH": "inhaled",
    "TOP": "topical",

    # Lab / measurement
    "CBC": "complete blood count",
    "BMP": "basic metabolic panel",
    "CMP": "comprehensive metabolic panel",
    "LFTs": "liver function tests",
    "TFTs": "thyroid function tests",
    "UA": "urinalysis",
    "ABG": "arterial blood gas",
    "BNP": "B-type natriuretic peptide",
    "Hgb": "hemoglobin",
    "Hct": "hematocrit",
    "WBC": "white blood cell count",
    "PLT": "platelet count",
    "Cr": "creatinine",
    "BUN": "blood urea nitrogen",
    "GFR": "glomerular filtration rate",
    "eGFR": "estimated glomerular filtration rate",
    "HbA1c": "glycated hemoglobin",
    "A1C": "glycated hemoglobin",
    "LDL": "low-density lipoprotein",
    "HDL": "high-density lipoprotein",
    "TG": "triglycerides",
    "TSH": "thyroid stimulating hormone",
    "PSA": "prostate-specific antigen",
    "ESR": "erythrocyte sedimentation rate",
    "CRP": "C-reactive protein",
    "INR": "international normalized ratio",
    "PT": "prothrombin time",
    "PTT": "partial thromboplastin time",

    # Procedures / imaging
    "EKG": "electrocardiogram",
    "ECG": "electrocardiogram",
    "CXR": "chest X-ray",
    "CT": "computed tomography",
    "MRI": "magnetic resonance imaging",
    "US": "ultrasound",
    "TTE": "transthoracic echocardiogram",
    "TEE": "transesophageal echocardiogram",
    "EGD": "esophagogastroduodenoscopy",
    "ERCP": "endoscopic retrograde cholangiopancreatography",
    "PCI": "percutaneous coronary intervention",
    "CABG": "coronary artery bypass graft",
    "TKR": "total knee replacement",
    "THR": "total hip replacement",
}


class ClinicalAbbreviationResolver:
    """
    Resolves clinical abbreviations in free text.

    Uses word-boundary-aware regex replacement to expand abbreviations
    without disrupting surrounding text. Preserves original case context.
    """

    def __init__(self, custom_abbreviations: dict = None):
        self._abbreviations = {**CLINICAL_ABBREVIATIONS}
        if custom_abbreviations:
            self._abbreviations.update(custom_abbreviations)

        # Build regex pattern for all abbreviations (case-sensitive, word-boundary)
        escaped = [re.escape(abbr) for abbr in sorted(self._abbreviations.keys(), key=len, reverse=True)]
        self._pattern = re.compile(
            r"\b(" + "|".join(escaped) + r")\b"
        )

    def resolve(self, text: str) -> str:
        """
        Expand abbreviations in clinical text.

        Replaces abbreviations with full forms while preserving
        the original abbreviation in parentheses for reference.
        Example: "Pt has HTN and DM2" → "Pt has hypertension (HTN) and diabetes mellitus type 2 (DM2)"
        """
        def _replace(match):
            abbr = match.group(0)
            expansion = self._abbreviations.get(abbr)
            if expansion:
                return f"{expansion} ({abbr})"
            return abbr

        return self._pattern.sub(_replace, text)

    def resolve_silent(self, text: str) -> str:
        """Expand abbreviations without preserving original form."""
        def _replace(match):
            return self._abbreviations.get(match.group(0), match.group(0))
        return self._pattern.sub(_replace, text)
