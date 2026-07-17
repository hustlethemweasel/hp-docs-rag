import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.api.conversations import router as conversations_router
from app.api.errors import http_exception_handler, unhandled_exception_handler
from app.api.health import router as health_router
from app.api.middleware import RequestIDMiddleware
from app.config import DEFAULT_FRONTEND_ORIGIN, get_settings
from app.db import Database
from app.logging import configure_logging
from app.providers.factory import build_provider


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)
    app.state.database = Database.from_url(settings.database_url)
    app.state.provider = build_provider(settings)
    yield
    await app.state.database.dispose()


def create_app(*, frontend_origin: str = DEFAULT_FRONTEND_ORIGIN) -> FastAPI:
    """App factory; tests construct the app and inject their own state.

    CORS must be added here, at construction, not inside lifespan: Starlette
    locks its middleware stack on the very first ASGI call — including the
    lifespan protocol's own dispatch — so adding middleware from inside
    lifespan raises "Cannot add middleware after an application has started"
    under a real server, even though it works when a test drives lifespan()
    directly as a bare async context manager (bypassing that dispatch).
    """
    app = FastAPI(title="HP Docs RAG ChatBot", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[frontend_origin],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestIDMiddleware)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
    app.include_router(health_router)
    app.include_router(conversations_router)
    return app


# Read directly from the environment, not via get_settings(): Settings
# requires DATABASE_URL, which must stay unavailable at import time so the
# fast suite's create_app()-only tests stay hermetic.
app = create_app(
    frontend_origin=os.environ.get("FRONTEND_ORIGIN", DEFAULT_FRONTEND_ORIGIN)
)
