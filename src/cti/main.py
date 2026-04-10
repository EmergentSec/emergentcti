"""FastAPI application entry point with lifespan management."""

from __future__ import annotations

import hashlib
import logging
import secrets
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import SecretStr
from sqlalchemy import func, select

from cti.api.v1.router import api_router
from cti.core.config import get_settings
from cti.core.database import async_session_factory
from cti.core.redis import close_redis, init_redis
from cti.models.api_key import ApiKey
from cti.models.user import User, UserRole
from cti.services import feed_service
from cti.services.scheduler import add_decay_job, init_scheduler, sync_feed_jobs

logger = logging.getLogger(__name__)


async def seed_initial_api_key() -> str | None:
    """Create a default API key if none exist. Returns the raw key or None."""
    async with async_session_factory() as db:
        result = await db.execute(select(func.count(ApiKey.id)))
        if result.scalar_one() > 0:
            return None

        raw_key = f"cti_{secrets.token_urlsafe(32)}"
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        api_key = ApiKey(
            name="Default Admin Key",
            key_hash=key_hash,
            key_prefix=raw_key[:12],
            description="Auto-generated on first startup",
        )
        db.add(api_key)
        await db.commit()
        return raw_key


async def seed_initial_admin_user() -> None:
    """Create a default admin user if no users exist and ADMIN_PASSWORD is set."""
    settings = get_settings()
    admin_pass = settings.ADMIN_PASSWORD.get_secret_value()
    if not admin_pass:
        return  # skip if not configured

    async with async_session_factory() as db:
        # Check if any users exist
        result = await db.execute(select(func.count(User.id)))
        if result.scalar_one() > 0:
            return  # already seeded

        from cti.services.auth_service import hash_password
        password_hash = await hash_password(admin_pass)
        user = User(
            username=settings.ADMIN_USERNAME,
            password_hash=password_hash,
            role=UserRole.admin,
            is_active=True,
        )
        db.add(user)
        await db.commit()
        logger.info("Initial admin user created: %s", settings.ADMIN_USERNAME)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    settings = get_settings()

    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
        format="%(asctime)s %(levelname)-8s [%(name)s] %(message)s",
    )

    # 1. Initialize Redis
    await init_redis(settings.REDIS_URL)
    logger.info("Redis connected")

    # 2. Validate/generate JWT_SECRET_KEY
    if not settings.JWT_SECRET_KEY.get_secret_value():
        new_secret = secrets.token_urlsafe(32)
        object.__setattr__(settings, "JWT_SECRET_KEY", SecretStr(new_secret))
        logger.warning(
            "JWT_SECRET_KEY not set — generated a random secret. "
            "Sessions will NOT persist across restarts. Set JWT_SECRET_KEY in your environment."
        )

    # 3. Seed default feeds and sync preconfigured feed configs
    async with async_session_factory() as db:
        count = await feed_service.seed_default_feeds(db)
        await db.commit()
        if count:
            logger.info("Seeded %d default feeds", count)
    async with async_session_factory() as db:
        await feed_service.update_preconfigured_feeds(db)
        await db.commit()

    # 4. Seed initial admin user
    await seed_initial_admin_user()

    # 5. Seed initial API key
    initial_key = await seed_initial_api_key()
    if initial_key:
        logger.info("=" * 60)
        logger.info("INITIAL API KEY (save this, it won't be shown again):")
        logger.info("  %s", initial_key)
        logger.info("=" * 60)

    # 6. Start scheduler
    sched = init_scheduler(settings.REDIS_URL)
    async with async_session_factory() as db:
        await sync_feed_jobs(db)
    await add_decay_job()
    sched.start()
    logger.info("Scheduler started")

    yield

    # Shutdown
    sched.shutdown(wait=False)
    await close_redis()
    logger.info("Shutdown complete")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="EmergentCTI",
        description="Lightweight CTI IOC Feed Aggregation Platform",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router)

    return app


app = create_app()
