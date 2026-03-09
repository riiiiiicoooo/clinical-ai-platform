"""
Role-Based Access Control — HIPAA minimum necessary access enforcement.

Implements role-based permissions for PHI access, ensuring each user
can only access data necessary for their job function.
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class Role(str, Enum):
    CLINICIAN = "clinician"
    CODER = "coder"
    PA_COORDINATOR = "pa_coordinator"
    BILLING_STAFF = "billing_staff"
    ADMIN = "admin"
    ANALYST = "analyst"
    SYSTEM = "system"  # AI agents


class Permission(str, Enum):
    # Patient data
    READ_DEMOGRAPHICS = "read:demographics"
    READ_CLINICAL = "read:clinical"
    READ_BILLING = "read:billing"
    WRITE_CLINICAL = "write:clinical"

    # Prior auth
    CREATE_PA = "create:prior_auth"
    SUBMIT_PA = "submit:prior_auth"
    APPROVE_PA = "approve:prior_auth"

    # Coding
    SUGGEST_CODES = "suggest:codes"
    APPROVE_CODES = "approve:codes"

    # Analytics
    VIEW_AGGREGATE = "view:aggregate"
    VIEW_INDIVIDUAL = "view:individual"
    EXPORT_DATA = "export:data"

    # Admin
    MANAGE_USERS = "manage:users"
    VIEW_AUDIT = "view:audit"
    MANAGE_CONFIG = "manage:config"


# Role → Permission mapping
ROLE_PERMISSIONS = {
    Role.CLINICIAN: {
        Permission.READ_DEMOGRAPHICS,
        Permission.READ_CLINICAL,
        Permission.WRITE_CLINICAL,
        Permission.CREATE_PA,
        Permission.SUGGEST_CODES,
        Permission.VIEW_INDIVIDUAL,
    },
    Role.CODER: {
        Permission.READ_DEMOGRAPHICS,
        Permission.READ_CLINICAL,
        Permission.READ_BILLING,
        Permission.SUGGEST_CODES,
        Permission.APPROVE_CODES,
        Permission.VIEW_INDIVIDUAL,
    },
    Role.PA_COORDINATOR: {
        Permission.READ_DEMOGRAPHICS,
        Permission.READ_CLINICAL,
        Permission.READ_BILLING,
        Permission.CREATE_PA,
        Permission.SUBMIT_PA,
        Permission.VIEW_INDIVIDUAL,
    },
    Role.BILLING_STAFF: {
        Permission.READ_DEMOGRAPHICS,
        Permission.READ_BILLING,
        Permission.VIEW_AGGREGATE,
    },
    Role.ADMIN: {
        Permission.READ_DEMOGRAPHICS,
        Permission.READ_CLINICAL,
        Permission.READ_BILLING,
        Permission.VIEW_AGGREGATE,
        Permission.VIEW_INDIVIDUAL,
        Permission.EXPORT_DATA,
        Permission.MANAGE_USERS,
        Permission.VIEW_AUDIT,
        Permission.MANAGE_CONFIG,
    },
    Role.ANALYST: {
        Permission.VIEW_AGGREGATE,
        Permission.EXPORT_DATA,
    },
    Role.SYSTEM: {
        Permission.READ_DEMOGRAPHICS,
        Permission.READ_CLINICAL,
        Permission.READ_BILLING,
        Permission.CREATE_PA,
        Permission.SUGGEST_CODES,
        Permission.VIEW_AGGREGATE,
    },
}


@dataclass
class AccessDecision:
    """Result of an access control check."""
    allowed: bool
    user_id: str
    role: Role
    permission: Permission
    reason: str = ""


class RBACEngine:
    """
    HIPAA-compliant role-based access control.

    Enforces minimum necessary access principle: users can only
    access PHI categories required for their job function.
    """

    def __init__(self, audit_logger=None):
        self._audit_logger = audit_logger

    def check_permission(self, user_role: Role, permission: Permission) -> AccessDecision:
        """Check if a role has a specific permission."""
        allowed_permissions = ROLE_PERMISSIONS.get(user_role, set())
        allowed = permission in allowed_permissions

        decision = AccessDecision(
            allowed=allowed,
            user_id="",
            role=user_role,
            permission=permission,
            reason="Permission granted" if allowed else f"Role {user_role.value} lacks {permission.value}",
        )

        if not allowed:
            logger.warning("Access denied: role=%s, permission=%s", user_role.value, permission.value)

        return decision

    def get_role_permissions(self, role: Role) -> set[Permission]:
        """Get all permissions for a role."""
        return ROLE_PERMISSIONS.get(role, set())

    def get_phi_access_scope(self, role: Role) -> list[str]:
        """Determine which PHI categories a role can access."""
        permissions = self.get_role_permissions(role)
        scope = []

        if Permission.READ_DEMOGRAPHICS in permissions:
            scope.append("demographics")
        if Permission.READ_CLINICAL in permissions:
            scope.extend(["diagnoses", "medications", "lab_results", "encounters", "allergies"])
        if Permission.READ_BILLING in permissions:
            scope.extend(["claims", "insurance", "billing"])

        return scope
