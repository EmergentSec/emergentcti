import logging
from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from cti.core.config import get_settings
from cti.core.elasticsearch import get_es_client
from cti.services.search_service import ensure_index

settings = get_settings()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # Startup
    logging.basicConfig(level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))
    logger.info("Starting CTI Platform")

    # Ensure Elasticsearch index
    try:
        es = get_es_client()
        await ensure_index(es)
        await es.close()
    except Exception:
        logger.warning("Could not connect to Elasticsearch", exc_info=True)

    # Create initial admin user if needed
    try:
        from cti.core.database import async_session_factory
        from cti.services.auth_service import create_initial_admin

        async with async_session_factory() as session:
            admin = await create_initial_admin(
                session, settings.ADMIN_PASSWORD.get_secret_value()
            )
            if admin:
                logger.info("Created initial admin user (username: admin)")
            await session.commit()
    except Exception:
        logger.warning("Could not create initial admin user", exc_info=True)

    # Seed SSO provider configs from environment variables
    try:
        from cti.core.database import async_session_factory as sso_session_factory
        from cti.sso.service import seed_sso_from_env

        async with sso_session_factory() as session:
            await seed_sso_from_env(session)
            await session.commit()
    except Exception:
        logger.warning("Could not seed SSO configs from environment", exc_info=True)

    # Seed MITRE ATT&CK data if needed
    try:
        from cti.core.database import async_session_factory as attack_session_factory
        from cti.services.attack_service import seed_attack_data

        async with attack_session_factory() as session:
            await seed_attack_data(session)
            await session.commit()
    except Exception:
        logger.warning("Could not seed ATT&CK data", exc_info=True)

    yield

    # Shutdown
    logger.info("Shutting down CTI Platform")


def create_app() -> FastAPI:
    app = FastAPI(
        title="CTI Platform",
        description="Cyber Threat Intelligence Platform API",
        version="0.1.0",
        lifespan=lifespan,
        openapi_url="/api/openapi.json" if settings.ENVIRONMENT != "production" else None,
        docs_url="/api/docs" if settings.ENVIRONMENT != "production" else None,
        redoc_url="/api/redoc" if settings.ENVIRONMENT != "production" else None,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    from cti.api.v1.router import api_router

    app.include_router(api_router)

    @app.get("/api/v1/health")
    async def health() -> dict:
        return {"status": "healthy", "version": "0.1.0"}

    return app


app = create_app()
