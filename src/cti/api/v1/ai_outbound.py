"""Interactive preview endpoint for external-AI outbound content."""
# ruff: noqa: B008, TC001, TC002

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from cti.core.database import get_db
from cti.core.dependencies import AuthSubject, get_current_auth
from cti.models.api_key import ApiKey
from cti.models.user import User
from cti.schemas.ai_outbound import OutboundPreview, OutboundPreviewRequest
from cti.services.ai import outbound
from cti.services.ai.outbound_types import OutboundRef

router = APIRouter()


async def require_interactive_user(
    auth: AuthSubject = Depends(get_current_auth),
) -> User:
    if isinstance(auth, ApiKey):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Interactive user session required",
        )
    return auth


@router.post("/preview", response_model=OutboundPreview)
async def preview_outbound_content(
    data: OutboundPreviewRequest,
    db: AsyncSession = Depends(get_db),
    auth: User = Depends(require_interactive_user),
) -> OutboundPreview:
    refs = [OutboundRef(type=ref.type, id=str(ref.id)) for ref in data.refs]
    return await outbound.build_preview(db, auth, data.provider, data.model, refs)
