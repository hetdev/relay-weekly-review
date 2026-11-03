"""Liveness and database-readiness checks. No configuration, no secrets."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.db.engine import ping

router = APIRouter()


@router.get("/healthz")
def liveness() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/readyz")
def readiness(request: Request) -> JSONResponse:
    if ping(request.app.state.engine):
        return JSONResponse({"status": "ready"})
    return JSONResponse(status_code=503, content={"status": "storage_unavailable"})
