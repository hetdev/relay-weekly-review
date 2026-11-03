"""HTTP error envelope: one consistent shape for every failure."""

from __future__ import annotations

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.reviews.errors import ReviewError

# Domain errors that indicate caller mistakes map to 4xx; anything else in
# ReviewError is a server-side data problem (5xx).
_STATUS_BY_CODE = {
    "account_not_found": 404,
    "invalid_week": 422,
    "unknown_location": 422,
    "data_quality": 500,
}


def error_body(request: Request, code: str, message: str) -> dict:
    return {
        "error": {
            "code": code,
            "message": message,
            "request_id": getattr(request.state, "request_id", None),
        }
    }


def review_error_handler(request: Request, exc: ReviewError) -> JSONResponse:
    status = _STATUS_BY_CODE.get(exc.code, 500)
    return JSONResponse(status_code=status, content=error_body(request, exc.code, exc.message))


def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    first = exc.errors()[0] if exc.errors() else {}
    location = ".".join(str(part) for part in first.get("loc", []))
    message = first.get("msg", "invalid input")
    detail = f"{location}: {message}" if location else message
    return JSONResponse(
        status_code=422, content=error_body(request, "invalid_input", detail)
    )


def internal_error_handler(request: Request, exc: Exception) -> JSONResponse:
    # Safe message only; the traceback with the request id goes to server logs.
    request_id = getattr(request.state, "request_id", None)
    print(f"[relay] unhandled error request_id={request_id!r} error={exc!r}", flush=True)
    return JSONResponse(
        status_code=500,
        content=error_body(request, "internal_error", "An internal error occurred."),
    )
