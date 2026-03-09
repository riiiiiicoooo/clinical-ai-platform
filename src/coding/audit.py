"""
Coding Audit Trail — Tracks every coding decision for compliance.

Maintains a complete audit trail linking each suggested code to its
source clinical documentation, the NLP extraction that identified it,
and the human reviewer who approved/modified it.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class CodingAuditEntry:
    """A single audit entry for a coding decision."""
    id: str
    encounter_id: str
    timestamp: datetime = field(default_factory=datetime.utcnow)

    # Code details
    code: str = ""
    code_system: str = ""  # icd10, cpt
    display: str = ""

    # Source evidence
    source_text: str = ""  # Clinical text supporting code
    nlp_confidence: float = 0.0
    ai_suggested: bool = True

    # Human review
    reviewed_by: Optional[str] = None
    review_action: str = "pending"  # accepted, modified, rejected
    original_code: Optional[str] = None  # If modified, what was AI's suggestion
    modification_reason: Optional[str] = None

    # Compliance
    specificity_check: str = "pass"  # pass, needs_review
    cci_check: str = "pass"  # pass, bundling_conflict


class CodingAuditTrail:
    """
    HIPAA-compliant audit trail for all coding decisions.

    Every code suggestion, modification, and approval is logged
    with full traceability for compliance audits and quality review.
    """

    def __init__(self, db_connection=None):
        self._db = db_connection
        self._entries: list[CodingAuditEntry] = []

    async def log_suggestion(
        self,
        encounter_id: str,
        code: str,
        code_system: str,
        display: str,
        source_text: str,
        confidence: float,
    ) -> str:
        """Log an AI-generated code suggestion."""
        import uuid
        entry_id = str(uuid.uuid4())[:12]

        entry = CodingAuditEntry(
            id=entry_id,
            encounter_id=encounter_id,
            code=code,
            code_system=code_system,
            display=display,
            source_text=source_text,
            nlp_confidence=confidence,
            ai_suggested=True,
        )
        self._entries.append(entry)

        if self._db:
            await self._persist(entry)

        return entry_id

    async def log_review(
        self,
        entry_id: str,
        reviewer: str,
        action: str,
        modified_code: str = None,
        reason: str = None,
    ):
        """Log human review of an AI coding suggestion."""
        entry = next((e for e in self._entries if e.id == entry_id), None)
        if entry:
            entry.reviewed_by = reviewer
            entry.review_action = action
            if modified_code and modified_code != entry.code:
                entry.original_code = entry.code
                entry.code = modified_code
                entry.modification_reason = reason

            if self._db:
                await self._persist(entry)

    async def get_encounter_audit(self, encounter_id: str) -> list[CodingAuditEntry]:
        """Get complete audit trail for an encounter."""
        return [e for e in self._entries if e.encounter_id == encounter_id]

    async def get_accuracy_metrics(self, period_days: int = 30) -> dict:
        """Calculate coding accuracy metrics from audit trail."""
        reviewed = [e for e in self._entries if e.review_action != "pending"]
        if not reviewed:
            return {"accuracy": 0, "total_reviewed": 0}

        accepted = len([e for e in reviewed if e.review_action == "accepted"])
        modified = len([e for e in reviewed if e.review_action == "modified"])
        rejected = len([e for e in reviewed if e.review_action == "rejected"])

        return {
            "total_reviewed": len(reviewed),
            "accepted": accepted,
            "modified": modified,
            "rejected": rejected,
            "accuracy": accepted / len(reviewed) if reviewed else 0,
            "modification_rate": modified / len(reviewed) if reviewed else 0,
        }

    async def _persist(self, entry: CodingAuditEntry):
        """Persist audit entry to database."""
        # In production: INSERT INTO coding_audit_trail ...
        logger.debug("Audit entry persisted: %s", entry.id)
