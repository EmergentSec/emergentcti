"""Health check endpoint — no auth required."""

from fastapi import APIRouter

router = APIRouter()


@router.get("")
async def health_check() -> dict:
    return {"status": "healthy", "version": "0.1.0"}
