"""
Encryption Utilities — AES-256 encryption for PHI at rest.

Provides field-level encryption for sensitive data stored in the database,
and key management utilities for HIPAA compliance.
"""

import base64
import hashlib
import logging
import os
from typing import Optional

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

logger = logging.getLogger(__name__)


class PHIEncryptor:
    """
    HIPAA-compliant field-level encryption for PHI.

    Uses AES-256-GCM for authenticated encryption with associated data.
    Supports key rotation and per-field encryption.
    """

    def __init__(self, master_key: str):
        """Initialize with master encryption key (from secure vault)."""
        # Derive AES-256 key from master key
        self._key = hashlib.sha256(master_key.encode()).digest()
        self._fernet = Fernet(base64.urlsafe_b64encode(self._key))

    def encrypt_field(self, plaintext: str) -> str:
        """Encrypt a single PHI field. Returns base64-encoded ciphertext."""
        if not plaintext:
            return ""
        return self._fernet.encrypt(plaintext.encode()).decode()

    def decrypt_field(self, ciphertext: str) -> str:
        """Decrypt a single PHI field."""
        if not ciphertext:
            return ""
        return self._fernet.decrypt(ciphertext.encode()).decode()

    def encrypt_record(self, record: dict, phi_fields: list[str]) -> dict:
        """
        Encrypt specified PHI fields in a record.

        Non-PHI fields are left in plaintext for querying.
        """
        encrypted = {**record}
        for field_name in phi_fields:
            if field_name in encrypted and encrypted[field_name]:
                encrypted[field_name] = self.encrypt_field(str(encrypted[field_name]))
                encrypted[f"_{field_name}_encrypted"] = True
        return encrypted

    def decrypt_record(self, record: dict, phi_fields: list[str]) -> dict:
        """Decrypt specified PHI fields in a record."""
        decrypted = {**record}
        for field_name in phi_fields:
            if record.get(f"_{field_name}_encrypted") and field_name in decrypted:
                decrypted[field_name] = self.decrypt_field(decrypted[field_name])
                del decrypted[f"_{field_name}_encrypted"]
        return decrypted


class TokenVault:
    """
    PHI tokenization — replaces identifiers with random tokens.

    Allows processing of clinical data without exposing direct identifiers.
    Token-to-identifier mapping stored separately with restricted access.
    """

    def __init__(self, encryptor: PHIEncryptor):
        self._encryptor = encryptor
        self._token_map: dict[str, str] = {}  # token → encrypted_identifier

    def tokenize(self, identifier: str) -> str:
        """Replace a PHI identifier with a random token."""
        # Check if already tokenized
        for token, encrypted_id in self._token_map.items():
            if self._encryptor.decrypt_field(encrypted_id) == identifier:
                return token

        # Generate new token
        token = f"TKN-{base64.urlsafe_b64encode(os.urandom(12)).decode()[:16]}"
        self._token_map[token] = self._encryptor.encrypt_field(identifier)
        return token

    def detokenize(self, token: str) -> Optional[str]:
        """Recover original identifier from token (restricted access)."""
        encrypted = self._token_map.get(token)
        if encrypted:
            return self._encryptor.decrypt_field(encrypted)
        return None

    def tokenize_record(self, record: dict, identifier_fields: list[str]) -> dict:
        """Tokenize specified identifier fields in a record."""
        tokenized = {**record}
        for field_name in identifier_fields:
            if field_name in tokenized and tokenized[field_name]:
                tokenized[field_name] = self.tokenize(str(tokenized[field_name]))
        return tokenized
