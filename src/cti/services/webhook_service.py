import hashlib
import hmac
import json
import logging
import uuid
from datetime import UTC, datetime

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cti.core.security import decrypt_config, encrypt_config
from cti.models.alert import WebhookConfig
from cti.schemas.alert import WebhookConfigCreate, WebhookConfigUpdate

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Webhook dispatch
# ---------------------------------------------------------------------------


def _build_signature(body: bytes, secret: str) -> str:
    """Compute HMAC-SHA256 signature of the request body."""
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


async def dispatch_webhook(
    db: AsyncSession, event_type: str, payload: dict
) -> None:
    """Find all enabled webhooks matching event_type and send HTTP POST."""
    result = await db.execute(
        select(WebhookConfig).where(WebhookConfig.enabled.is_(True))
    )
    webhooks = result.scalars().all()

    body_dict = {
        "event": event_type,
        "data": payload,
        "timestamp": datetime.now(UTC).isoformat(),
    }
    body_bytes = json.dumps(body_dict, default=str).encode()

    for webhook in webhooks:
        # Check if this webhook subscribes to this event type
        if webhook.events and event_type not in webhook.events:
            continue

        headers: dict[str, str] = {"Content-Type": "application/json"}

        # Add HMAC signature if secret is configured
        if webhook.secret_encrypted is not None:
            try:
                secret = decrypt_config(webhook.secret_encrypted)
                signature = _build_signature(body_bytes, secret)
                headers["X-Webhook-Signature"] = signature
            except Exception:
                logger.warning(
                    "Failed to decrypt webhook secret for %s", webhook.id, exc_info=True
                )

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    webhook.url,
                    content=body_bytes,
                    headers=headers,
                )
                if response.status_code >= 400:
                    logger.warning(
                        "Webhook %s returned status %d for event %s",
                        webhook.name,
                        response.status_code,
                        event_type,
                    )
        except Exception:
            logger.error(
                "Failed to dispatch webhook %s for event %s",
                webhook.name,
                event_type,
                exc_info=True,
            )


async def send_test_webhook(webhook: WebhookConfig) -> dict:
    """Send a test payload to a webhook and return the result."""
    body_dict = {
        "event": "webhook.test",
        "data": {
            "message": "This is a test webhook from CTI Platform",
            "webhook_id": str(webhook.id),
            "webhook_name": webhook.name,
        },
        "timestamp": datetime.now(UTC).isoformat(),
    }
    body_bytes = json.dumps(body_dict, default=str).encode()

    headers: dict[str, str] = {"Content-Type": "application/json"}

    if webhook.secret_encrypted is not None:
        try:
            secret = decrypt_config(webhook.secret_encrypted)
            signature = _build_signature(body_bytes, secret)
            headers["X-Webhook-Signature"] = signature
        except Exception:
            return {
                "success": False,
                "status_code": None,
                "error": "Failed to decrypt webhook secret",
            }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                webhook.url,
                content=body_bytes,
                headers=headers,
            )
            return {
                "success": response.status_code < 400,
                "status_code": response.status_code,
                "error": None if response.status_code < 400 else f"HTTP {response.status_code}",
            }
    except Exception as e:
        return {"success": False, "status_code": None, "error": str(e)}


# ---------------------------------------------------------------------------
# CRUD for webhook configs
# ---------------------------------------------------------------------------


async def create_webhook(
    db: AsyncSession, data: WebhookConfigCreate, user_id: uuid.UUID | None = None
) -> WebhookConfig:
    secret_encrypted = None
    if data.secret:
        secret_encrypted = encrypt_config(data.secret)

    webhook = WebhookConfig(
        name=data.name,
        url=data.url,
        secret_encrypted=secret_encrypted,
        enabled=data.enabled,
        events=data.events,
        created_by=user_id,
    )
    db.add(webhook)
    await db.flush()
    await db.refresh(webhook)
    return webhook


async def list_webhooks(db: AsyncSession) -> list[WebhookConfig]:
    result = await db.execute(select(WebhookConfig).order_by(WebhookConfig.name))
    return list(result.scalars().all())


async def get_webhook(db: AsyncSession, webhook_id: uuid.UUID) -> WebhookConfig | None:
    result = await db.execute(
        select(WebhookConfig).where(WebhookConfig.id == webhook_id)
    )
    return result.scalar_one_or_none()


async def update_webhook(
    db: AsyncSession, webhook_id: uuid.UUID, data: WebhookConfigUpdate
) -> WebhookConfig | None:
    webhook = await get_webhook(db, webhook_id)
    if not webhook:
        return None

    update_data = data.model_dump(exclude_unset=True)
    secret = update_data.pop("secret", None)

    for field, value in update_data.items():
        setattr(webhook, field, value)

    if secret is not None:
        webhook.secret_encrypted = encrypt_config(secret)

    await db.flush()
    await db.refresh(webhook)
    return webhook


async def delete_webhook(db: AsyncSession, webhook_id: uuid.UUID) -> bool:
    webhook = await get_webhook(db, webhook_id)
    if not webhook:
        return False
    await db.delete(webhook)
    await db.flush()
    return True
