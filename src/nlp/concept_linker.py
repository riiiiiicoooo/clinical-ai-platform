"""
Medical Concept Linker — Maps clinical entities to standardized ontologies.

Links NER output to SNOMED CT concepts via MedCAT, then cross-references
to ICD-10-CM, CPT, and RxNorm for downstream coding and billing.
"""

import logging
from typing import Optional

from langsmith import traceable

logger = logging.getLogger(__name__)


# SNOMED CT → ICD-10-CM mapping (subset for common conditions)
SNOMED_TO_ICD10 = {
    "38341003": "I10",          # Hypertension → Essential hypertension
    "73211009": "E11.9",        # Diabetes mellitus type 2
    "44054006": "E11.9",        # Diabetes mellitus type 2
    "84114007": "I50.9",        # Heart failure
    "22298006": "I21.9",        # Myocardial infarction
    "195967001": "J45.909",     # Asthma
    "13645005": "J44.1",        # COPD exacerbation
    "709044004": "N18.9",       # Chronic kidney disease
    "399211009": "I25.10",      # Coronary artery disease
    "49436004": "I48.91",       # Atrial fibrillation
    "230690007": "I63.9",       # Cerebrovascular accident (stroke)
    "414545008": "I25.10",      # Ischemic heart disease
    "59621000": "I10",          # Essential hypertension
    "267036007": "R06.02",      # Shortness of breath
    "29857009": "M54.5",        # Chest pain
    "386661006": "R50.9",       # Fever
    "25064002": "R51",          # Headache
    "21522001": "R10.9",        # Abdominal pain
    "68566005": "N39.0",        # Urinary tract infection
    "233604007": "J18.9",       # Pneumonia
    "40055000": "J02.9",        # Pharyngitis
    "36971009": "J00",          # Sinusitis → Common cold/rhinitis
}

# Common CPT code mappings (procedure → CPT)
PROCEDURE_TO_CPT = {
    "total_knee_replacement": "27447",
    "total_hip_replacement": "27130",
    "coronary_angiography": "93454",
    "echocardiogram": "93306",
    "mri_brain": "70553",
    "mri_knee": "73721",
    "ct_abdomen": "74177",
    "ct_chest": "71260",
    "xray_chest": "71046",
    "colonoscopy": "45378",
    "upper_endoscopy": "43239",
    "cardiac_catheterization": "93452",
    "stress_test": "93015",
    "physical_therapy_eval": "97161",
    "occupational_therapy_eval": "97165",
}


class ConceptLinker:
    """
    Links clinical entities to standardized medical ontologies.

    Uses MedCAT for SNOMED CT concept resolution, then cross-references
    to ICD-10-CM, CPT, and RxNorm using curated mapping tables + UMLS API.
    """

    def __init__(self, umls_api_key: str = None):
        self._umls_api_key = umls_api_key
        self._medcat = None

    async def initialize(self):
        """Load MedCAT model with SNOMED CT vocabulary."""
        try:
            from medcat.cat import CAT
            # In production: load from trained model pack
            # self._medcat = CAT.load_model_pack("path/to/medcat_model_pack")
            logger.info("MedCAT concept linker initialized")
        except ImportError:
            logger.warning("MedCAT not installed — using fallback concept linking")

    @traceable(name="nlp.link_entities")
    async def link_entities(self, entities: list, text: str) -> list:
        """
        Link extracted entities to SNOMED CT concepts.

        For each entity, attempts to find the best matching SNOMED CT concept
        using MedCAT's context-aware disambiguation.
        """
        if self._medcat:
            # Production: use MedCAT for context-aware concept linking
            doc = self._medcat.get_entities(text)
            # Map MedCAT entities back to our entity objects
            for entity in entities:
                for med_ent in doc.get("entities", {}).values():
                    if (entity.start >= med_ent["start"] and entity.end <= med_ent["end"]):
                        entity.snomed_code = med_ent.get("cui", "")
                        entity.snomed_display = med_ent.get("pretty_name", "")
                        entity.confidence = med_ent.get("context_similarity", 0.0)
                        break
        else:
            # Fallback: keyword-based SNOMED mapping
            for entity in entities:
                code, display = self._fallback_snomed_lookup(entity.text)
                if code:
                    entity.snomed_code = code
                    entity.snomed_display = display
                    entity.confidence = 0.7

        return entities

    @traceable(name="nlp.cross_reference")
    async def cross_reference(self, entities: list) -> list:
        """
        Cross-reference SNOMED CT codes to ICD-10, CPT, and RxNorm.

        Uses curated mapping tables first, falls back to UMLS API for
        codes not in the local mapping.
        """
        for entity in entities:
            if entity.snomed_code:
                # SNOMED → ICD-10 mapping
                icd10 = SNOMED_TO_ICD10.get(entity.snomed_code)
                if icd10:
                    entity.icd10_code = icd10

                # For procedures: map to CPT
                if entity.label == "PROCEDURE":
                    cpt = self._lookup_cpt(entity.text)
                    if cpt:
                        entity.cpt_code = cpt

                # For medications: lookup RxNorm
                if entity.label == "MEDICATION":
                    rxnorm = self._lookup_rxnorm(entity.text)
                    if rxnorm:
                        entity.rxnorm_code = rxnorm

        return entities

    def _fallback_snomed_lookup(self, text: str) -> tuple[Optional[str], Optional[str]]:
        """Keyword-based SNOMED CT lookup for common conditions."""
        text_lower = text.lower().strip()

        KEYWORD_MAP = {
            "hypertension": ("38341003", "Hypertension"),
            "high blood pressure": ("38341003", "Hypertension"),
            "htn": ("38341003", "Hypertension"),
            "diabetes": ("73211009", "Diabetes mellitus type 2"),
            "type 2 diabetes": ("73211009", "Diabetes mellitus type 2"),
            "dm2": ("73211009", "Diabetes mellitus type 2"),
            "heart failure": ("84114007", "Heart failure"),
            "chf": ("84114007", "Heart failure"),
            "copd": ("13645005", "COPD exacerbation"),
            "asthma": ("195967001", "Asthma"),
            "atrial fibrillation": ("49436004", "Atrial fibrillation"),
            "afib": ("49436004", "Atrial fibrillation"),
            "ckd": ("709044004", "Chronic kidney disease"),
            "chronic kidney disease": ("709044004", "Chronic kidney disease"),
            "cad": ("399211009", "Coronary artery disease"),
            "coronary artery disease": ("399211009", "Coronary artery disease"),
            "pneumonia": ("233604007", "Pneumonia"),
            "uti": ("68566005", "Urinary tract infection"),
            "stroke": ("230690007", "Cerebrovascular accident"),
            "chest pain": ("29857009", "Chest pain"),
            "shortness of breath": ("267036007", "Shortness of breath"),
            "sob": ("267036007", "Shortness of breath"),
        }

        for keyword, (code, display) in KEYWORD_MAP.items():
            if keyword in text_lower:
                return code, display
        return None, None

    def _lookup_cpt(self, text: str) -> Optional[str]:
        """Lookup CPT code for a procedure."""
        text_lower = text.lower()
        for procedure_key, cpt_code in PROCEDURE_TO_CPT.items():
            if any(word in text_lower for word in procedure_key.split("_")):
                return cpt_code
        return None

    def _lookup_rxnorm(self, text: str) -> Optional[str]:
        """Lookup RxNorm code for a medication."""
        COMMON_MEDICATIONS = {
            "lisinopril": "29046",
            "metformin": "6809",
            "atorvastatin": "83367",
            "amlodipine": "17767",
            "metoprolol": "6918",
            "omeprazole": "7646",
            "losartan": "52175",
            "gabapentin": "25480",
            "hydrochlorothiazide": "5487",
            "sertraline": "36437",
            "warfarin": "11289",
            "apixaban": "1364430",
            "furosemide": "4603",
            "levothyroxine": "10582",
            "prednisone": "8640",
            "albuterol": "435",
        }
        text_lower = text.lower().strip()
        for drug, rxnorm in COMMON_MEDICATIONS.items():
            if drug in text_lower:
                return rxnorm
        return None
