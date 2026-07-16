from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.health import router as health_router
from app.config import get_settings
from app.db import Database
from app.logging import configure_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)
    app.state.database = Database.from_url(settings.database_url)
    yield
    await app.state.database.dispose()


def create_app() -> FastAPI:
    """App factory; tests construct the app and inject their own state."""
    app = FastAPI(title="HP Docs RAG ChatBot", lifespan=lifespan)
    app.include_router(health_router)
    return app


app = create_app()
