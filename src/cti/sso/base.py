from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class SSOUserInfo:
    """Normalized user information returned by SSO providers."""

    email: str
    name: str | None = None
    external_id: str | None = None
    avatar_url: str | None = None
    groups: list[str] = field(default_factory=list)


class BaseSSOProvider(ABC):
    """Abstract base class for SSO provider implementations."""

    def __init__(self, client_id: str, client_secret: str, **kwargs: str) -> None:
        self.client_id = client_id
        self.client_secret = client_secret

    @abstractmethod
    def get_authorization_url(self, redirect_uri: str, state: str) -> str:
        """Build the OAuth2 authorization URL to redirect the user to."""
        ...

    @abstractmethod
    async def handle_callback(self, code: str, redirect_uri: str) -> SSOUserInfo:
        """Exchange authorization code for tokens and return normalized user info."""
        ...
