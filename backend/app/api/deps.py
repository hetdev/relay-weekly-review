"""Dependencies: per-request connection + service wiring (composition at
the edges; business code never constructs infrastructure itself)."""

from __future__ import annotations

from typing import Iterator

from fastapi import Request

from app.reviews.repository import SqlReviewRepository
from app.reviews.service import ReviewService


def get_service(request: Request) -> Iterator[ReviewService]:
    engine = request.app.state.engine
    with engine.connect() as connection:
        yield ReviewService(SqlReviewRepository(connection), request.app.state.settings)
