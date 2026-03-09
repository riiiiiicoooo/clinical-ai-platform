"""
CCI Edit Checker — Correct Coding Initiative bundling compliance.

Validates CPT code combinations against CCI edit rules to prevent
billing errors from incorrect bundling/unbundling of procedures.
"""

import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class CCIEditResult:
    """Result of CCI edit check for a procedure pair."""
    code1: str
    code2: str
    is_bundled: bool
    modifier_allowed: bool  # Can modifier 59/XE/XS/XP/XU override?
    edit_type: str  # column1_column2, mutually_exclusive, add_on
    description: str


# CCI Edit pairs (representative subset — full CCI database has 200K+ edits)
CCI_EDITS = {
    # Orthopedic bundling
    ("27447", "20610"): {"bundled": True, "modifier_ok": True, "type": "column1_column2",
                         "desc": "Knee arthrocentesis bundled with total knee replacement"},
    ("27447", "27331"): {"bundled": True, "modifier_ok": False, "type": "column1_column2",
                         "desc": "Knee arthrotomy bundled with total knee replacement"},
    ("27130", "20610"): {"bundled": True, "modifier_ok": True, "type": "column1_column2",
                         "desc": "Hip arthrocentesis bundled with total hip replacement"},

    # Cardiology bundling
    ("93306", "93320"): {"bundled": True, "modifier_ok": False, "type": "column1_column2",
                         "desc": "Doppler echo bundled with complete echo"},
    ("93306", "93325"): {"bundled": True, "modifier_ok": False, "type": "column1_column2",
                         "desc": "Color flow Doppler bundled with complete echo"},
    ("93452", "93453"): {"bundled": True, "modifier_ok": False, "type": "mutually_exclusive",
                         "desc": "Left and combined heart cath are mutually exclusive"},

    # E/M bundling
    ("99213", "99214"): {"bundled": True, "modifier_ok": False, "type": "mutually_exclusive",
                         "desc": "E/M levels are mutually exclusive"},
    ("99214", "99215"): {"bundled": True, "modifier_ok": False, "type": "mutually_exclusive",
                         "desc": "E/M levels are mutually exclusive"},

    # Imaging bundling
    ("71046", "71045"): {"bundled": True, "modifier_ok": False, "type": "column1_column2",
                         "desc": "1-view chest X-ray bundled with 2-view"},
    ("73721", "73720"): {"bundled": True, "modifier_ok": False, "type": "column1_column2",
                         "desc": "MRI knee without contrast bundled with with+without"},
}

# Add-on codes (must be reported with primary code)
ADDON_CODES = {
    "99417": {"primary": ["99205", "99215"], "desc": "Prolonged E/M service"},
    "93320": {"primary": ["93303", "93304", "93306"], "desc": "Doppler echo (add-on to echo)"},
    "93325": {"primary": ["93303", "93304", "93306", "93320"], "desc": "Color flow Doppler mapping"},
}


class CCIChecker:
    """
    Checks CPT code combinations for CCI edit compliance.

    Validates that procedures are correctly bundled/unbundled
    and that modifiers are appropriately applied.
    """

    def check_pair(self, code1: str, code2: str) -> CCIEditResult:
        """Check CCI edit for a pair of CPT codes."""
        # Check both orderings
        edit = CCI_EDITS.get((code1, code2)) or CCI_EDITS.get((code2, code1))

        if edit:
            return CCIEditResult(
                code1=code1,
                code2=code2,
                is_bundled=edit["bundled"],
                modifier_allowed=edit["modifier_ok"],
                edit_type=edit["type"],
                description=edit["desc"],
            )

        return CCIEditResult(
            code1=code1,
            code2=code2,
            is_bundled=False,
            modifier_allowed=True,
            edit_type="none",
            description="No CCI edit found — codes can be billed separately",
        )

    def check_all(self, codes: list[str]) -> list[CCIEditResult]:
        """Check all pairwise combinations of CPT codes for CCI edits."""
        results = []
        for i, code1 in enumerate(codes):
            for code2 in codes[i + 1:]:
                result = self.check_pair(code1, code2)
                if result.is_bundled:
                    results.append(result)
        return results

    def check_addon(self, addon_code: str, primary_codes: list[str]) -> dict:
        """Verify add-on code is paired with valid primary code."""
        addon_info = ADDON_CODES.get(addon_code)
        if not addon_info:
            return {"valid": True, "is_addon": False}

        valid_primaries = addon_info["primary"]
        has_primary = any(p in primary_codes for p in valid_primaries)

        return {
            "valid": has_primary,
            "is_addon": True,
            "requires": valid_primaries,
            "description": addon_info["desc"],
            "error": None if has_primary else f"Add-on code {addon_code} requires one of: {', '.join(valid_primaries)}",
        }
