from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.conversations import router as conversations_router
from app.api.health import router as health_router
from app.config import get_settings
from app.db import Database
from app.logging import configure_logging
from app.providers.factory import build_provider


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)
    # Added here, not at construction: the frontend origin comes from
    # Settings, which requires DATABASE_URL and must stay unavailable at
    # import time so the fast suite's create_app()-only tests stay hermetic.
    # Safe before the app has served a request — add_middleware only raises
    # once the ASGI middleware stack is built, which happens on first call.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_origin],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.state.database = Database.from_url(settings.database_url)
    app.state.provider = build_provider(settings)
    yield
    await app.state.database.dispose()


def create_app() -> FastAPI:
    """App factory; tests construct the app and inject their own state."""
    app = FastAPI(title="HP Docs RAG ChatBot", lifespan=lifespan)
    app.include_router(health_router)
    app.include_router(conversations_router)
    return app


app = create_app()
