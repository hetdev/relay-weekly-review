"""Composition root: builds the app, wires settings/engine/service deps."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from sqlalchemy.engine import Engine

from app.api import errors as api_errors
from app.api.deps import get_service
from app.api.request_id import RequestIdMiddleware
from app.api.routes import router as api_router
from app.api.routes_health import router as health_router
from app.config import Settings, load_env_file
from app.db.engine import create_db_engine
from app.reviews.errors import ReviewError


def create_app(
    settings: Settings | None = None,
    engine: Engine | None = None,
) -> FastAPI:
    if settings is None:
        load_env_file(Path(__file__).resolve().parents[1] / ".env")
        settings = Settings.from_env()

    app = FastAPI(
        title="Relay Weekly Review API",
        version="1.0.0",
        description="Weekly activity review against a location's own recent history (DASH-247).",
    )
    app.state.settings = settings
    app.state.engine = engine if engine is not None else create_db_engine(settings.database_url)

    app.add_middleware(RequestIdMiddleware)
    app.include_router(health_router)
    app.include_router(api_router)

    app.add_exception_handler(ReviewError, api_errors.review_error_handler)
    app.add_exception_handler(RequestValidationError, api_errors.validation_error_handler)
    app.add_exception_handler(Exception, api_errors.internal_error_handler)
    return app


app = create_app()
