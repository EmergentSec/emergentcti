from cti.core.security import decrypt_config
from cti.models.sso_config import SSOProviderConfig
from cti.models.user import AuthProvider
from cti.sso.azure_ad import AzureADProvider
from cti.sso.base import BaseSSOProvider
from cti.sso.google import GoogleProvider
from cti.sso.oidc import GenericOIDCProvider

PROVIDER_MAP: dict[AuthProvider, type[BaseSSOProvider]] = {
    AuthProvider.azure_ad: AzureADProvider,
    AuthProvider.google: GoogleProvider,
    AuthProvider.oidc: GenericOIDCProvider,
}


def get_provider(config: SSOProviderConfig) -> BaseSSOProvider:
    """Instantiate an SSO provider from a database config record."""
    provider_cls = PROVIDER_MAP.get(config.provider_type)
    if provider_cls is None:
        msg = f"Unsupported SSO provider type: {config.provider_type}"
        raise ValueError(msg)

    provider_config = config.provider_config or {}
    client_id = provider_config.get("client_id", "")

    # Decrypt the client secret
    client_secret = ""
    if config.client_secret_encrypted:
        client_secret = decrypt_config(config.client_secret_encrypted)

    # Pass additional kwargs from provider_config
    kwargs: dict[str, str] = {}
    if config.provider_type == AuthProvider.azure_ad:
        kwargs["tenant_id"] = provider_config.get("tenant_id", "common")
    elif config.provider_type == AuthProvider.google:
        kwargs["allowed_domain"] = provider_config.get("allowed_domain", "")
    elif config.provider_type == AuthProvider.oidc:
        kwargs["issuer_url"] = provider_config.get("issuer_url", "")

    return provider_cls(client_id=client_id, client_secret=client_secret, **kwargs)
