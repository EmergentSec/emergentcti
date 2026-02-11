import logging
from urllib.parse import urlencode

import httpx
from authlib.integrations.httpx_client import AsyncOAuth2Client

from cti.sso.base import BaseSSOProvider, SSOUserInfo

logger = logging.getLogger(__name__)


class GenericOIDCProvider(BaseSSOProvider):
    """Generic OIDC SSO provider using authlib with auto-discovery."""

    def __init__(
        self, client_id: str, client_secret: str, **kwargs: str
    ) -> None:
        super().__init__(client_id, client_secret)
        self.issuer_url = kwargs.get("issuer_url", "").rstrip("/")
        self.discovery_url = f"{self.issuer_url}/.well-known/openid-configuration"
        self._discovery_cache: dict[str, str] | None = None

    async def _discover(self) -> dict[str, str]:
        """Fetch and cache the OIDC discovery document."""
        if self._discovery_cache is not None:
            return self._discovery_cache
        async with httpx.AsyncClient() as client:
            resp = await client.get(self.discovery_url)
            resp.raise_for_status()
            self._discovery_cache = resp.json()
        return self._discovery_cache  # type: ignore[return-value]

    def get_authorization_url(self, redirect_uri: str, state: str) -> str:
        # For the synchronous authorization URL, we construct it from the
        # issuer URL pattern. The actual discovery-based URL is used
        # when the async variant is available via get_authorization_url_async.
        authorize_endpoint = f"{self.issuer_url}/authorize"
        params = {
            "client_id": self.client_id,
            "response_type": "code",
            "redirect_uri": redirect_uri,
            "scope": "openid email profile",
            "state": state,
        }
        return f"{authorize_endpoint}?{urlencode(params)}"

    async def get_authorization_url_async(
        self, redirect_uri: str, state: str
    ) -> str:
        """Build authorization URL using discovered endpoints."""
        discovery = await self._discover()
        authorize_endpoint = discovery.get(
            "authorization_endpoint", f"{self.issuer_url}/authorize"
        )
        params = {
            "client_id": self.client_id,
            "response_type": "code",
            "redirect_uri": redirect_uri,
            "scope": "openid email profile",
            "state": state,
        }
        return f"{authorize_endpoint}?{urlencode(params)}"

    async def handle_callback(self, code: str, redirect_uri: str) -> SSOUserInfo:
        discovery = await self._discover()
        token_endpoint = discovery.get(
            "token_endpoint", f"{self.issuer_url}/token"
        )
        userinfo_endpoint = discovery.get(
            "userinfo_endpoint", f"{self.issuer_url}/userinfo"
        )

        client = AsyncOAuth2Client(
            client_id=self.client_id,
            client_secret=self.client_secret,
            token_endpoint=token_endpoint,
        )
        try:
            token = await client.fetch_token(
                token_endpoint,
                code=code,
                redirect_uri=redirect_uri,
                grant_type="authorization_code",
            )

            # Fetch user info from the userinfo endpoint
            async with httpx.AsyncClient() as http_client:
                resp = await http_client.get(
                    userinfo_endpoint,
                    headers={
                        "Authorization": f"Bearer {token['access_token']}"
                    },
                )
                resp.raise_for_status()
                userinfo = resp.json()

            email = str(userinfo.get("email", "")).lower()
            return SSOUserInfo(
                email=email,
                name=userinfo.get("name") or userinfo.get("preferred_username"),
                external_id=userinfo.get("sub"),
                avatar_url=userinfo.get("picture"),
            )
        finally:
            await client.aclose()
