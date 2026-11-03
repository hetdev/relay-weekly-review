"""API routes. Thin: validate, delegate to the service, translate errors."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request

from app.api.deps import get_service
from app.api.dtos import (
    AccountOut,
    OptionsOut,
    PolicyOut,
    ReviewOut,
    account_out,
    options_out,
    review_out,
)
from app.reviews.calendar import CalendarError, parse_week_start
from app.reviews.errors import InvalidWeek
from app.reviews.metrics import Metric
from app.reviews.service import ReviewService

router = APIRouter(prefix="/api/v1")


@router.get("/accounts", response_model=list[AccountOut])
def list_accounts(service: ReviewService = Depends(get_service)) -> list[AccountOut]:
    return [account_out(account) for account in service.list_accounts()]


@router.get("/accounts/{account_id}/review-options", response_model=OptionsOut)
def review_options(
    account_id: int, service: ReviewService = Depends(get_service)
) -> OptionsOut:
    return options_out(service.review_options(account_id))


@router.get("/accounts/{account_id}/weekly-review", response_model=ReviewOut)
def weekly_review(
    account_id: int,
    request: Request,
    service: ReviewService = Depends(get_service),
    week_start: str = Query(pattern=r"^\d{4}-\d{2}-\d{2}$", description="Monday, YYYY-MM-DD"),
    metric: Metric = Query(default=Metric.CALL_RECEIVED),
    location: str | None = Query(default=None, max_length=80),
) -> ReviewOut:
    try:
        week_monday = parse_week_start(week_start)
    except CalendarError as exc:
        raise InvalidWeek(str(exc)) from exc
    result = service.weekly_review(account_id, week_monday, metric, location)
    policy = request.app.state.settings.policy
    return review_out(
        result,
        request_id=request.state.request_id,
        policy_fields=PolicyOut(
            version=policy.version,
            baseline_weeks=policy.baseline_weeks,
            low_volume_reference=policy.low_volume_reference,
            min_absolute_change=policy.min_absolute_change,
            min_relative_change=policy.min_relative_change,
        ),
    )
