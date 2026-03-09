"""
SMART on FHIR OAuth 2.0 Authentication.

Implements the SMART App Launch Framework for EHR integration.
Handles authorization code flow, token management, and launch context.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional
from urllib.parse import urlencode

import httpx

logger = logging.getLogger(__name__)


class SMARTAuth:
    """
    SMART on FHIR OAuth 2.0 handler.

    Supports both standalone launch and EHR launch flows.
    Manages token refresh and launch context (patient, encounter).
    """

    def __init__(
        self,
        fhir_base_url: str,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        scopes: str = "patient/*.read launch/patient openid fhirUser",
    ):
        self.fhir_base_url = fhir_base_url
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.scopes = scopes
        self._conformance: Optional[dict] = None
        self._http = httpx.AsyncClient(timeout=15.0)

    async def discover_endpoints(self) -> dict:
        """Discover OAuth endpoints from FHIR server metadata."""
        if self._conformance:
            return self._conformance

        metadata_url = f"{self.fhir_base_url}/metadata"
        response = await self._http.get(metadata_url)
        response.raise_for_status()
        capability = response.json()

        # Extract OAuth URLs from CapabilityStatement
        security = capability.get("rest", [{}])[0].get("security", {})
        extensions = security.get("extension", [])

        oauth_ext = next(
            (e for e in extensions if "oauth-uris" in e.get("url", "")),
            {},
        )
        sub_extensions = oauth_ext.get("extension", [])

        self._conformance = {
            "authorize": next(
                (e["valueUri"] for e in sub_extensions if e.get("url") == "authorize"),
                "",
            ),
            "token": next(
                (e["valueUri"] for e in sub_extensions if e.get("url") == "token"),
                "",
            ),
        }
        return self._conformance

    def get_authorization_url(self, state: str, aud: str = None) -> str:
        """Generate authorization URL for SMART launch."""
        endpoints = self._conformance or {}
        authorize_url = endpoints.get("authorize", f"{self.fhir_base_url}/oauth2/authorize")

        params = {
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "scope": self.scopes,
            "state": state,
            "aud": aud or self.fhir_base_url,
        }
        return f"{authorize_url}?{urlencode(params)}"

    async def exchange_code(self, code: str) -> dict:
        """Exchange authorization code for access token."""
        endpoints = await self.discover_endpoints()
        token_url = endpoints.get("token", f"{self.fhir_base_url}/oauth2/token")

        response = await self._http.post(
            token_url,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": self.redirect_uri,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            },
        )
        response.raise_for_status()
        token_data = response.json()

        return {
            "access_token": token_data["access_token"],
            "token_type": token_data.get("token_type", "Bearer"),
            "expires_at": datetime.utcnow() + timedelta(seconds=token_data.get("expires_in", 3600)),
            "refresh_token": token_data.get("refresh_token"),
            "patient": token_data.get("patient"),  # Launch context
            "encounter": token_data.get("encounter"),
            "scope": token_data.get("scope", ""),
        }

    async def refresh_token(self, refresh_token: str) -> dict:
        """Refresh an expired access token."""
        endpoints = await self.discover_endpoints()
        token_url = endpoints.get("token", f"{self.fhir_base_url}/oauth2/token")

        response = await self._http.post(
            token_url,
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            },
        )
        response.raise_for_status()
        token_data = response.json()

        return {
            "access_token": token_data["access_token"],
            "expires_at": datetime.utcnow() + timedelta(seconds=token_data.get("expires_in", 3600)),
            "refresh_token": token_data.get("refresh_token", refresh_token),
        }

    async def close(self):
        await self._http.aclose()
