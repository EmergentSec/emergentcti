import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from cti.models.user import AuthProvider, UserRole


class SSOProviderResponse(BaseModel):
    """Admin view of SSO provider configuration. Never exposes client_secret."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    provider_type: AuthProvider
    display_name: str
    enabled: bool
    provider_config: dict = Field(default_factory=dict)
    default_role: UserRole
    allowed_domains: list[str] | None = None
    auto_create_users: bool
    created_at: datetime
    updated_at: datetime


class SSOProviderPublic(BaseModel):
    """Public view for the login page. Only shows enabled providers."""

    provider_type: AuthProvider
    display_name: str


class SSOProviderConfigUpdate(BaseModel):
    """Flat update schema. Backend maps fields to provider_config JSONB + encrypted secret."""

    display_name: str | None = None
    enabled: bool | None = None
    client_id: str | None = None
    client_secret: str | None = None
    tenant_id: str | None = None
    issuer_url: str | None = None
    allowed_domains: list[str] | None = None
    default_role: UserRole | None = None
    auto_create_users: bool | None = None


class SSOCallbackResponse(BaseModel):
    """Returned after successful SSO login."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    is_new_user: bool = False
