import logging
import secrets

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cti.core.config import get_settings
from cti.core.security import (
    create_access_token,
    create_refresh_token,
    encrypt_config,
    hash_password,
)
from cti.models.sso_config import SSOProviderConfig
from cti.models.user import AuthProvider, User, UserRole
from cti.schemas.sso import SSOCallbackResponse
from cti.sso.base import SSOUserInfo

logger = logging.getLogger(__name__)


async def get_or_create_sso_user(
    db: AsyncSession,
    provider_type: AuthProvider,
    user_info: SSOUserInfo,
    default_role: UserRole,
    auto_create: bool,
) -> tuple[User, bool]:
    """JIT provisioning for SSO users.

    Looks up user by email first for account linking. If found, updates
    external_id and auth_provider. If not found and auto_create is True,
    creates a new user with a random unusable password hash.

    Returns a tuple of (user, is_new_user).
    """
    # Look up existing user by email (account linking)
    result = await db.execute(select(User).where(User.email == user_info.email))
    user = result.scalar_one_or_none()

    if user is not None:
        # Link the SSO identity to the existing account
        user.auth_provider = provider_type
        if user_info.external_id:
            user.external_id = user_info.external_id
        if user_info.avatar_url:
            user.avatar_url = user_info.avatar_url
        await db.flush()
        return user, False

    if not auto_create:
        msg = (
            f"User {user_info.email} not found and auto-creation is disabled "
            f"for provider {provider_type.value}"
        )
        raise ValueError(msg)

    # Create new user with random unusable password
    random_password = secrets.token_urlsafe(32)
    # Derive a username from the email local part, ensuring uniqueness
    base_username = user_info.email.split("@")[0][:50]
    username = base_username

    # Check for username collision
    existing = await db.execute(select(User).where(User.username == username))
    if existing.scalar_one_or_none():
        username = f"{base_username}_{secrets.token_hex(4)}"

    user = User(
        username=username,
        email=user_info.email,
        hashed_password=hash_password(random_password),
        role=default_role,
        is_active=True,
        auth_provider=provider_type,
        external_id=user_info.external_id,
        avatar_url=user_info.avatar_url,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    logger.info("Created SSO user %s via %s", user.email, provider_type.value)
    return user, True


def issue_tokens_for_user(user: User) -> SSOCallbackResponse:
    """Create JWT access and refresh tokens for an authenticated SSO user."""
    token_data = {"sub": str(user.id), "role": user.role.value}
    return SSOCallbackResponse(
        access_token=create_access_token(token_data),
        refresh_token=create_refresh_token(token_data),
        is_new_user=False,
    )


async def seed_sso_from_env(db: AsyncSession) -> None:
    """Seed SSO provider configs from environment variables.

    Only creates configs that don't already exist in the database.
    This allows env-var-based bootstrap while preserving DB-managed configs.
    """
    settings = get_settings()

    providers: list[dict] = []

    if settings.SSO_AZURE_AD_ENABLED and settings.SSO_AZURE_AD_CLIENT_ID:
        providers.append({
            "provider_type": AuthProvider.azure_ad,
            "display_name": "Microsoft 365",
            "enabled": True,
            "provider_config": {
                "client_id": settings.SSO_AZURE_AD_CLIENT_ID,
                "tenant_id": settings.SSO_AZURE_AD_TENANT_ID,
            },
            "client_secret": settings.SSO_AZURE_AD_CLIENT_SECRET.get_secret_value(),
        })

    if settings.SSO_GOOGLE_ENABLED and settings.SSO_GOOGLE_CLIENT_ID:
        provider_config: dict[str, str] = {
            "client_id": settings.SSO_GOOGLE_CLIENT_ID,
        }
        if settings.SSO_GOOGLE_ALLOWED_DOMAIN:
            provider_config["allowed_domain"] = settings.SSO_GOOGLE_ALLOWED_DOMAIN
        providers.append({
            "provider_type": AuthProvider.google,
            "display_name": "Google Workspace",
            "enabled": True,
            "provider_config": provider_config,
            "client_secret": settings.SSO_GOOGLE_CLIENT_SECRET.get_secret_value(),
        })

    if settings.SSO_OIDC_ENABLED and settings.SSO_OIDC_CLIENT_ID:
        providers.append({
            "provider_type": AuthProvider.oidc,
            "display_name": settings.SSO_OIDC_DISPLAY_NAME,
            "enabled": True,
            "provider_config": {
                "client_id": settings.SSO_OIDC_CLIENT_ID,
                "issuer_url": settings.SSO_OIDC_ISSUER_URL,
            },
            "client_secret": settings.SSO_OIDC_CLIENT_SECRET.get_secret_value(),
        })

    # Resolve default role from env
    try:
        default_role = UserRole(settings.SSO_DEFAULT_ROLE)
    except ValueError:
        default_role = UserRole.readonly

    for provider_data in providers:
        provider_type = provider_data["provider_type"]

        # Check if config already exists
        result = await db.execute(
            select(SSOProviderConfig).where(
                SSOProviderConfig.provider_type == provider_type
            )
        )
        if result.scalar_one_or_none():
            logger.debug(
                "SSO config for %s already exists, skipping env seed",
                provider_type.value,
            )
            continue

        client_secret_raw = provider_data.pop("client_secret", "")
        client_secret_encrypted = (
            encrypt_config(client_secret_raw) if client_secret_raw else None
        )

        config = SSOProviderConfig(
            provider_type=provider_type,
            display_name=provider_data["display_name"],
            enabled=provider_data["enabled"],
            provider_config=provider_data["provider_config"],
            client_secret_encrypted=client_secret_encrypted,
            default_role=default_role,
            auto_create_users=settings.SSO_AUTO_CREATE_USERS,
        )
        db.add(config)
        logger.info(
            "Seeded SSO config for %s from environment", provider_type.value
        )
