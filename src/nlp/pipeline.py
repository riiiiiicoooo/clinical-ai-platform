"""
Clinical NLP Pipeline — Medical concept extraction and normalization.

Orchestrates SciSpaCy NER, MedCAT concept linking, and abbreviation
resolution to extract structured clinical data from free text.
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

from langsmith import traceable

logger = logging.getLogger(__name__)


@dataclass
class ClinicalEntity:
    """A recognized clinical entity from text."""
    text: str
    label: str  # CONDITION, MEDICATION, PROCEDURE, LAB, ANATOMY, TEMPORAL
    start: int
    end: int
    snomed_code: Optional[str] = None
    snomed_display: Optional[str] = None
    icd10_code: Optional[str] = None
    cpt_code: Optional[str] = None
    rxnorm_code: Optional[str] = None
    confidence: float = 0.0


@dataclass
class ClinicalExtraction:
    """Complete extraction result from a clinical note."""
    conditions: list[ClinicalEntity] = field(default_factory=list)
    medications: list[ClinicalEntity] = field(default_factory=list)
    procedures: list[ClinicalEntity] = field(default_factory=list)
    lab_values: list[ClinicalEntity] = field(default_factory=list)
    anatomical_sites: list[ClinicalEntity] = field(default_factory=list)
    temporal_references: list[ClinicalEntity] = field(default_factory=list)
    raw_entities: list[ClinicalEntity] = field(default_factory=list)


class ClinicalNLPPipeline:
    """
    Clinical NLP pipeline combining SciSpaCy, MedCAT, and custom components.

    Pipeline stages:
    1. Abbreviation resolution (HTN → Hypertension)
    2. NER with SciSpaCy (entity detection)
    3. Concept linking with MedCAT (SNOMED CT mapping)
    4. Cross-reference mapping (SNOMED → ICD-10, CPT, RxNorm)
    5. Confidence scoring and filtering
    """

    def __init__(self):
        self._nlp = None  # Lazy load SciSpaCy model
        self._medcat = None  # Lazy load MedCAT
        self._abbreviation_resolver = None
        self._concept_linker = None

    async def initialize(self):
        """Load NLP models (expensive — do once at startup)."""
        import spacy

        # Load SciSpaCy biomedical model
        try:
            self._nlp = spacy.load("en_core_sci_lg")
            logger.info("SciSpaCy model loaded: en_core_sci_lg")
        except OSError:
            self._nlp = spacy.load("en_core_sci_sm")
            logger.warning("Fallback to en_core_sci_sm — install en_core_sci_lg for production")

        # Initialize abbreviation resolver
        from src.nlp.abbreviation import ClinicalAbbreviationResolver
        self._abbreviation_resolver = ClinicalAbbreviationResolver()

        # Initialize concept linker
        from src.nlp.concept_linker import ConceptLinker
        self._concept_linker = ConceptLinker()
        await self._concept_linker.initialize()

        logger.info("Clinical NLP pipeline initialized")

    @traceable(name="nlp.extract_clinical_concepts")
    async def extract(self, text: str) -> ClinicalExtraction:
        """
        Extract clinical concepts from free-text clinical note.

        Returns structured extraction with conditions, medications,
        procedures, labs, and anatomical sites — each mapped to
        medical ontology codes (SNOMED CT, ICD-10, CPT, RxNorm).
        """
        if not self._nlp:
            await self.initialize()

        # Step 1: Resolve abbreviations
        expanded_text = self._abbreviation_resolver.resolve(text)

        # Step 2: NER with SciSpaCy
        doc = self._nlp(expanded_text)
        raw_entities = []

        for ent in doc.ents:
            entity = ClinicalEntity(
                text=ent.text,
                label=self._classify_entity(ent),
                start=ent.start_char,
                end=ent.end_char,
                confidence=0.0,
            )
            raw_entities.append(entity)

        # Step 3: Concept linking (SNOMED CT mapping)
        linked_entities = await self._concept_linker.link_entities(raw_entities, expanded_text)

        # Step 4: Cross-reference mapping
        mapped_entities = await self._concept_linker.cross_reference(linked_entities)

        # Step 5: Organize by type
        extraction = ClinicalExtraction(raw_entities=mapped_entities)
        for entity in mapped_entities:
            if entity.label == "CONDITION":
                extraction.conditions.append(entity)
            elif entity.label == "MEDICATION":
                extraction.medications.append(entity)
            elif entity.label == "PROCEDURE":
                extraction.procedures.append(entity)
            elif entity.label == "LAB":
                extraction.lab_values.append(entity)
            elif entity.label == "ANATOMY":
                extraction.anatomical_sites.append(entity)
            elif entity.label == "TEMPORAL":
                extraction.temporal_references.append(entity)

        logger.info(
            "NLP extraction: %d conditions, %d meds, %d procedures, %d labs",
            len(extraction.conditions),
            len(extraction.medications),
            len(extraction.procedures),
            len(extraction.lab_values),
        )
        return extraction

    def _classify_entity(self, ent) -> str:
        """Classify SciSpaCy entity into clinical category."""
        label = ent.label_.upper()

        # Map SciSpaCy labels to clinical categories
        CONDITION_LABELS = {"DISEASE", "DISORDER", "FINDING", "SIGN_OR_SYMPTOM"}
        MEDICATION_LABELS = {"CHEMICAL", "DRUG", "PHARMACOLOGIC_SUBSTANCE"}
        PROCEDURE_LABELS = {"PROCEDURE", "THERAPEUTIC_PROCEDURE", "DIAGNOSTIC_PROCEDURE"}
        LAB_LABELS = {"LAB_VALUE", "LABORATORY_FINDING", "QUANTITATIVE_CONCEPT"}
        ANATOMY_LABELS = {"BODY_PART", "BODY_STRUCTURE", "ANATOMICAL_STRUCTURE"}
        TEMPORAL_LABELS = {"TEMPORAL_CONCEPT", "DATE", "DURATION"}

        if label in CONDITION_LABELS or "disease" in ent.text.lower():
            return "CONDITION"
        elif label in MEDICATION_LABELS:
            return "MEDICATION"
        elif label in PROCEDURE_LABELS:
            return "PROCEDURE"
        elif label in LAB_LABELS:
            return "LAB"
        elif label in ANATOMY_LABELS:
            return "ANATOMY"
        elif label in TEMPORAL_LABELS:
            return "TEMPORAL"
        else:
            return "CONDITION"  # Default: most clinical entities are conditions
