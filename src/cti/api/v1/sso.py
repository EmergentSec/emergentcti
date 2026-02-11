import logging
import secrets
import time

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cti.core.database import get_db
from cti.core.dependencies import AdminUser
from cti.core.security import encrypt_config
from cti.models.sso_config import SSOProviderConfig
from cti.models.user import AuthProvider
from cti.schemas.sso import (
    SSOProviderConfigUpdate,
    SSOProviderPublic,
    SSOProviderResponse,
)
from cti.sso.oidc import GenericOIDCProvider
from cti.sso.registry import get_provider
from cti.sso.service import get_or_create_sso_user, issue_tokens_for_user

logger = logging.getLogger(__name__)
router = APIRouter()

# In-memory OAuth state storage.
# TODO: For multi-worker deployments, migrate state storage to Redis.
# This is adequate for homelab/single-worker setups.
_oauth_states: dict[str, float] = {}

STATE_TTL_SECONDS = 600  # 10 minutes


def _generate_state() -> str:
    """Generate a random state token and store it with a TTL."""
    state = secrets.token_urlsafe(32)
    _oauth_states[state] = time.time()
    return state


def _validate_state(state: str) -> bool:
    """Validate and consume a state token. Returns False if invalid or expired."""
    created_at = _oauth_states.pop(state, None)
    if created_at is None:
        return False
    return not time.time() - created_at > STATE_TTL_SECONDS


def _cleanup_expired_states() -> None:
    """Remove expired state tokens to prevent memory leaks."""
    now = time.time()
    expired = [s for s, ts in _oauth_states.items() if now - ts > STATE_TTL_SECONDS]
    for s in expired:
        _oauth_states.pop(s, None)


async def _get_sso_config(
    db: AsyncSession, provider_type_str: str
) -> SSOProviderConfig:
    """Load an enabled SSO config from DB by provider type string."""
    try:
        provider_type = AuthProvider(provider_type_str)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown provider type: {provider_type_str}",
        ) from exc

    if provider_type == AuthProvider.local:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot use SSO flow with local auth provider",
        )

    result = await db.execute(
        select(SSOProviderConfig).where(
            SSOProviderConfig.provider_type == provider_type,
            SSOProviderConfig.enabled.is_(True),
        )
    )
    config = result.scalar_one_or_none()
    if config is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"SSO provider {provider_type_str} is not configured or not enabled",
        )
    return config


@router.get("/providers", response_model=list[SSOProviderPublic])
async def list_enabled_providers(
    db: AsyncSession = Depends(get_db),
) -> list[SSOProviderPublic]:
    """Return only enabled SSO providers for the login page. No auth required."""
    result = await db.execute(
        select(SSOProviderConfig).where(SSOProviderConfig.enabled.is_(True))
    )
    configs = result.scalars().all()
    return [
        SSOProviderPublic(
            provider_type=c.provider_type,
            display_name=c.display_name,
        )
        for c in configs
    ]


@router.get("/{provider_type}/authorize")
async def sso_authorize(
    provider_type: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Initiate SSO login by returning the authorization URL. No auth required."""
    _cleanup_expired_states()

    config = await _get_sso_config(db, provider_type)
    provider = get_provider(config)
    state = _generate_state()

    redirect_uri = str(request.base_url).rstrip("/") + f"/api/v1/sso/{provider_type}/callback"

    # Use async discovery for OIDC providers when available
    if isinstance(provider, GenericOIDCProvider):
        authorization_url = await provider.get_authorization_url_async(redirect_uri, state)
    else:
        authorization_url = provider.get_authorization_url(redirect_uri, state)

    return {"authorization_url": authorization_url}


@router.get("/{provider_type}/callback")
async def sso_callback(
    provider_type: str,
    code: str,
    state: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    """Handle OAuth2 callback. Validates state, exchanges code, provisions user.

    Redirects to frontend with tokens in URL fragment (not query params)
    to avoid tokens being logged in server access logs.
    """
    if not _validate_state(state):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OAuth state",
        )

    config = await _get_sso_config(db, provider_type)
    provider = get_provider(config)

    redirect_uri = str(request.base_url).rstrip("/") + f"/api/v1/sso/{provider_type}/callback"

    try:
        user_info = await provider.handle_callback(code, redirect_uri)
    except Exception as exc:
        logger.exception("SSO callback failed for provider %s", provider_type)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to authenticate with SSO provider",
        ) from exc

    if not user_info.email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="SSO provider did not return an email address",
        )

    # Check allowed domains if configured
    if config.allowed_domains:
        email_domain = user_info.email.rsplit("@", 1)[-1].lower()
        allowed = [d.lower() for d in config.allowed_domains]
        if email_domain not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Email domain '{email_domain}' is not allowed for this SSO provider",
            )

    try:
        auth_provider = AuthProvider(provider_type)
        user, is_new_user = await get_or_create_sso_user(
            db,
            auth_provider,
            user_info,
            config.default_role,
            config.auto_create_users,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled",
        )

    tokens = issue_tokens_for_user(user)
    tokens.is_new_user = is_new_user

    # Redirect to frontend with tokens in URL fragment for security.
    # Fragments are not sent to the server in subsequent requests and
    # are not logged in server access logs.
    frontend_url = request.headers.get("Origin", "http://localhost:5173")
    fragment = (
        f"access_token={tokens.access_token}"
        f"&refresh_token={tokens.refresh_token}"
        f"&token_type={tokens.token_type}"
        f"&is_new_user={str(is_new_user).lower()}"
    )
    return RedirectResponse(
        url=f"{frontend_url}/#{fragment}",
        status_code=status.HTTP_302_FOUND,
    )


@router.get("/config", response_model=list[SSOProviderResponse])
async def list_sso_configs(
    _admin: AdminUser,
    db: AsyncSession = Depends(get_db),
) -> list[SSOProviderResponse]:
    """Return all SSO provider configs (admin only). Never exposes client secrets."""
    result = await db.execute(
        select(SSOProviderConfig).order_by(SSOProviderConfig.provider_type)
    )
    configs = result.scalars().all()
    return [SSOProviderResponse.model_validate(c) for c in configs]


@router.put("/config/{provider_type}", response_model=SSOProviderResponse)
async def update_sso_config(
    provider_type: str,
    data: SSOProviderConfigUpdate,
    _admin: AdminUser,
    db: AsyncSession = Depends(get_db),
) -> SSOProviderResponse:
    """Create or update SSO provider config (admin only).

    Upserts the config: creates if it doesn't exist, updates if it does.
    Client secret is encrypted before storage.
    """
    try:
        auth_provider = AuthProvider(provider_type)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown provider type: {provider_type}",
        ) from exc

    if auth_provider == AuthProvider.local:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot configure SSO for local auth provider",
        )

    # Load existing or create new
    result = await db.execute(
        select(SSOProviderConfig).where(
            SSOProviderConfig.provider_type == auth_provider
        )
    )
    config = result.scalar_one_or_none()

    if config is None:
        config = SSOProviderConfig(
            provider_type=auth_provider,
            display_name=data.display_name or auth_provider.value,
        )
        db.add(config)

    # Update simple fields
    if data.display_name is not None:
        config.display_name = data.display_name
    if data.enabled is not None:
        config.enabled = data.enabled
    if data.allowed_domains is not None:
        config.allowed_domains = data.allowed_domains
    if data.default_role is not None:
        config.default_role = data.default_role
    if data.auto_create_users is not None:
        config.auto_create_users = data.auto_create_users

    # Update provider_config JSONB fields
    provider_config = dict(config.provider_config or {})
    if data.client_id is not None:
        provider_config["client_id"] = data.client_id
    if data.tenant_id is not None:
        provider_config["tenant_id"] = data.tenant_id
    if data.issuer_url is not None:
        provider_config["issuer_url"] = data.issuer_url
    config.provider_config = provider_config

    # Encrypt client secret if provided
    if data.client_secret is not None:
        config.client_secret_encrypted = encrypt_config(data.client_secret)

    await db.flush()
    await db.refresh(config)
    return SSOProviderResponse.model_validate(config)


@router.delete(
    "/config/{provider_type}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_sso_config(
    provider_type: str,
    _admin: AdminUser,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete an SSO provider config (admin only)."""
    try:
        auth_provider = AuthProvider(provider_type)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown provider type: {provider_type}",
        ) from exc

    result = await db.execute(
        select(SSOProviderConfig).where(
            SSOProviderConfig.provider_type == auth_provider
        )
    )
    config = result.scalar_one_or_none()
    if config is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"SSO provider config for {provider_type} not found",
        )

    await db.delete(config)
    await db.flush()
