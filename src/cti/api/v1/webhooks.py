import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from cti.core.database import get_db
from cti.core.dependencies import AdminUser
from cti.schemas.alert import (
    WebhookConfigCreate,
    WebhookConfigResponse,
    WebhookConfigUpdate,
    WebhookTestResponse,
)
from cti.services import webhook_service

router = APIRouter()


@router.get("", response_model=list[WebhookConfigResponse])
async def list_webhooks(
    _user: AdminUser,
    db: AsyncSession = Depends(get_db),
) -> list[WebhookConfigResponse]:
    """List all webhook configurations."""
    webhooks = await webhook_service.list_webhooks(db)
    return [WebhookConfigResponse.model_validate(w) for w in webhooks]


@router.post("", response_model=WebhookConfigResponse, status_code=status.HTTP_201_CREATED)
async def create_webhook(
    data: WebhookConfigCreate,
    user: AdminUser,
    db: AsyncSession = Depends(get_db),
) -> WebhookConfigResponse:
    """Create a new webhook configuration."""
    webhook = await webhook_service.create_webhook(db, data, user_id=user.id)
    return WebhookConfigResponse.model_validate(webhook)


@router.put("/{webhook_id}", response_model=WebhookConfigResponse)
async def update_webhook(
    webhook_id: uuid.UUID,
    data: WebhookConfigUpdate,
    _user: AdminUser,
    db: AsyncSession = Depends(get_db),
) -> WebhookConfigResponse:
    """Update a webhook configuration."""
    webhook = await webhook_service.update_webhook(db, webhook_id, data)
    if not webhook:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Webhook not found"
        )
    return WebhookConfigResponse.model_validate(webhook)


@router.delete("/{webhook_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_webhook(
    webhook_id: uuid.UUID,
    _user: AdminUser,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a webhook configuration."""
    deleted = await webhook_service.delete_webhook(db, webhook_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Webhook not found"
        )


@router.post("/{webhook_id}/test", response_model=WebhookTestResponse)
async def test_webhook(
    webhook_id: uuid.UUID,
    _user: AdminUser,
    db: AsyncSession = Depends(get_db),
) -> WebhookTestResponse:
    """Send a test payload to a webhook."""
    webhook = await webhook_service.get_webhook(db, webhook_id)
    if not webhook:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Webhook not found"
        )

    result = await webhook_service.send_test_webhook(webhook)
    return WebhookTestResponse(**result)
