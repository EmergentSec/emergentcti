import logging
from urllib.parse import urlencode

import httpx
from authlib.integrations.httpx_client import AsyncOAuth2Client

from cti.sso.base import BaseSSOProvider, SSOUserInfo

logger = logging.getLogger(__name__)

AZURE_AD_AUTH_BASE = "https://login.microsoftonline.com"
MS_GRAPH_BASE = "https://graph.microsoft.com/v1.0"


class AzureADProvider(BaseSSOProvider):
    """Azure AD (Microsoft 365) SSO provider using authlib."""

    def __init__(
        self, client_id: str, client_secret: str, **kwargs: str
    ) -> None:
        super().__init__(client_id, client_secret)
        self.tenant_id = kwargs.get("tenant_id", "common")
        self.authority = f"{AZURE_AD_AUTH_BASE}/{self.tenant_id}/v2.0"
        self.authorize_url = f"{AZURE_AD_AUTH_BASE}/{self.tenant_id}/oauth2/v2.0/authorize"
        self.token_url = f"{AZURE_AD_AUTH_BASE}/{self.tenant_id}/oauth2/v2.0/token"

    def get_authorization_url(self, redirect_uri: str, state: str) -> str:
        params = {
            "client_id": self.client_id,
            "response_type": "code",
            "redirect_uri": redirect_uri,
            "scope": "openid email profile",
            "state": state,
            "response_mode": "query",
        }
        return f"{self.authorize_url}?{urlencode(params)}"

    async def handle_callback(self, code: str, redirect_uri: str) -> SSOUserInfo:
        client = AsyncOAuth2Client(
            client_id=self.client_id,
            client_secret=self.client_secret,
            token_endpoint=self.token_url,
        )
        try:
            token = await client.fetch_token(
                self.token_url,
                code=code,
                redirect_uri=redirect_uri,
                grant_type="authorization_code",
            )

            # Fetch user profile from MS Graph
            async with httpx.AsyncClient() as http_client:
                resp = await http_client.get(
                    f"{MS_GRAPH_BASE}/me",
                    headers={"Authorization": f"Bearer {token['access_token']}"},
                )
                resp.raise_for_status()
                profile = resp.json()

            email = profile.get("mail") or profile.get("userPrincipalName", "")
            return SSOUserInfo(
                email=email.lower(),
                name=profile.get("displayName"),
                external_id=profile.get("id"),
                avatar_url=None,  # MS Graph photo requires separate endpoint
            )
        finally:
            await client.aclose()
