import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from cti.core.database import get_db
from cti.core.dependencies import AdminUser, CurrentUser
from cti.schemas.auth import (
    ApiKeyResponse,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from cti.schemas.bulk import BulkIds, BulkUserUpdate, UserUpdate
from cti.services import auth_service, user_service

router = APIRouter()


@router.post("/login", response_model=TokenResponse)
async def login(data: LoginRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    return await auth_service.authenticate_user(db, data.username, data.password)


@router.post("/register", response_model=UserResponse)
async def register(
    data: RegisterRequest,
    _admin: AdminUser,
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    user = await auth_service.register_user(db, data)
    return UserResponse.model_validate(user)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(data: RefreshRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    return await auth_service.refresh_tokens(db, data.refresh_token)


@router.get("/me", response_model=UserResponse)
async def me(current_user: CurrentUser) -> UserResponse:
    return UserResponse.model_validate(current_user)


@router.get("/users", response_model=list[UserResponse])
async def list_users(
    _admin: AdminUser,
    db: AsyncSession = Depends(get_db),
) -> list[UserResponse]:
    users = await auth_service.list_users(db)
    return [UserResponse.model_validate(u) for u in users]


@router.post("/api-key", response_model=ApiKeyResponse)
async def create_api_key(
    current_user: CurrentUser, db: AsyncSession = Depends(get_db)
) -> ApiKeyResponse:
    key = await auth_service.generate_user_api_key(db, current_user.id)
    return ApiKeyResponse(api_key=key)


@router.put("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: uuid.UUID,
    data: UserUpdate,
    _admin: AdminUser,
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    user = await user_service.update_user(db, user_id, role=data.role, is_active=data.is_active)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return UserResponse.model_validate(user)


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: uuid.UUID,
    _admin: AdminUser,
    db: AsyncSession = Depends(get_db),
) -> None:
    deleted = await user_service.delete_user(db, user_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")


@router.patch("/users/bulk", status_code=status.HTTP_200_OK)
async def bulk_update_users(
    data: BulkUserUpdate,
    _admin: AdminUser,
    db: AsyncSession = Depends(get_db),
) -> dict:
    count = await user_service.bulk_update_users(
        db, data.ids, role=data.role, is_active=data.is_active
    )
    return {"updated": count}


@router.delete("/users/bulk", status_code=status.HTTP_200_OK)
async def bulk_delete_users(
    data: BulkIds,
    _admin: AdminUser,
    db: AsyncSession = Depends(get_db),
) -> dict:
    count = await user_service.bulk_delete_users(db, data.ids)
    return {"deleted": count}
