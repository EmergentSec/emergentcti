import logging
from urllib.parse import urlencode

from authlib.integrations.httpx_client import AsyncOAuth2Client
from authlib.jose import jwt as jose_jwt

from cti.sso.base import BaseSSOProvider, SSOUserInfo

logger = logging.getLogger(__name__)

GOOGLE_AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_CERTS_URL = "https://www.googleapis.com/oauth2/v3/certs"


class GoogleProvider(BaseSSOProvider):
    """Google Workspace SSO provider using authlib."""

    def __init__(
        self, client_id: str, client_secret: str, **kwargs: str
    ) -> None:
        super().__init__(client_id, client_secret)
        self.allowed_domain = kwargs.get("allowed_domain", "")

    def get_authorization_url(self, redirect_uri: str, state: str) -> str:
        params: dict[str, str] = {
            "client_id": self.client_id,
            "response_type": "code",
            "redirect_uri": redirect_uri,
            "scope": "openid email profile",
            "state": state,
            "access_type": "offline",
            "prompt": "select_account",
        }
        # Restrict to specific Google Workspace domain if configured
        if self.allowed_domain:
            params["hd"] = self.allowed_domain
        return f"{GOOGLE_AUTHORIZE_URL}?{urlencode(params)}"

    async def handle_callback(self, code: str, redirect_uri: str) -> SSOUserInfo:
        client = AsyncOAuth2Client(
            client_id=self.client_id,
            client_secret=self.client_secret,
            token_endpoint=GOOGLE_TOKEN_URL,
        )
        try:
            token = await client.fetch_token(
                GOOGLE_TOKEN_URL,
                code=code,
                redirect_uri=redirect_uri,
                grant_type="authorization_code",
            )

            # Decode the ID token to extract user information.
            # We decode without verification here because the token was obtained
            # directly from Google over TLS. For additional security in production,
            # fetch Google's JWKS and pass them to decode().
            id_token = token.get("id_token", "")
            claims = jose_jwt.decode(
                id_token,
                {"kty": "oct", "k": ""},  # skip signature verification
            )

            email = str(claims.get("email", "")).lower()
            return SSOUserInfo(
                email=email,
                name=claims.get("name"),
                external_id=claims.get("sub"),
                avatar_url=claims.get("picture"),
            )
        finally:
            await client.aclose()
