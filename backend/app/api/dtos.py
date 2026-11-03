"""Wire contract (Pydantic models) — the single source of truth for the API.

The TypeScript client is typed against these shapes; `npm run sync-openapi`
in the frontend regenerates the OpenAPI schema these models produce.
"""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field

from app.reviews.service import ComparisonView, LocationRow, OptionsResult, ReviewResult
from app.reviews.ports import AccountRecord


class AccountOut(BaseModel):
    id: int
    name: str
    industry: str
    timezone: str


class WeekPointOut(BaseModel):
    week_start: date
    covered: bool
    count: int


class ComparisonOut(BaseModel):
    count: int
    reference: float | None
    delta: float | None
    percent_change: float | None
    observed_min: int | None
    observed_max: int | None
    reason: str | None
    classification_suppressed: bool = False
    weeks: list[WeekPointOut] = Field(default_factory=list)


class LocationOut(BaseModel):
    location: str
    first_observed_utc: datetime | None
    view: ComparisonOut


class CoverageOut(BaseModel):
    coverage_start_utc: datetime
    coverage_end_utc: datetime
    demo_now_utc: datetime
    last_observed_event_utc: datetime | None
    warnings: list[str]


class TimeOut(BaseModel):
    timezone: str
    week_start_local: datetime
    week_end_local: datetime
    week_start_utc: datetime
    week_end_utc: datetime


class BaselineOut(BaseModel):
    week_count: int
    weeks_covered: int
    start_utc: datetime


class ScopeOut(BaseModel):
    account_id: int
    account_name: str
    metric: str
    location: str | None
    week_start: str


class PolicyOut(BaseModel):
    version: str
    baseline_weeks: int
    low_volume_reference: float
    min_absolute_change: int
    min_relative_change: float


class ReviewOut(BaseModel):
    request_id: str
    scope: ScopeOut
    time: TimeOut
    baseline: BaselineOut
    policy: PolicyOut
    coverage: CoverageOut
    summary: ComparisonOut
    account_summary: ComparisonOut
    locations: list[LocationOut]


class OptionsOut(BaseModel):
    account: AccountOut
    timezone: str
    locations: list[str]
    default_week: date
    available_weeks: list[date]
    coverage: CoverageOut


def account_out(account: AccountRecord) -> AccountOut:
    return AccountOut(
        id=account.id,
        name=account.name,
        industry=account.industry,
        timezone=account.timezone,
    )


def comparison_out(view: ComparisonView) -> ComparisonOut:
    return ComparisonOut(
        count=view.count,
        reference=view.reference,
        delta=view.delta,
        percent_change=view.percent_change,
        observed_min=view.observed_min,
        observed_max=view.observed_max,
        reason=view.reason,
        classification_suppressed=view.classification_suppressed,
        weeks=[
            WeekPointOut(week_start=point.week_start, covered=point.covered, count=point.count)
            for point in view.weeks
        ],
    )


def location_out(row: LocationRow) -> LocationOut:
    return LocationOut(
        location=row.location, first_observed_utc=row.first_observed_utc, view=comparison_out(row.view)
    )


def review_out(result: ReviewResult, request_id: str, policy_fields: PolicyOut) -> ReviewOut:
    return ReviewOut(
        request_id=request_id,
        scope=ScopeOut(
            account_id=result.account.id,
            account_name=result.account.name,
            metric=result.metric.value,
            location=result.location_filter,
            week_start=result.week_start_local.date().isoformat(),
        ),
        time=TimeOut(
            timezone=result.timezone,
            week_start_local=result.week_start_local,
            week_end_local=result.week_end_local,
            week_start_utc=result.week_start_utc,
            week_end_utc=result.week_end_utc,
        ),
        baseline=BaselineOut(
            week_count=result.baseline_week_count,
            weeks_covered=result.baseline_weeks_covered,
            start_utc=result.baseline_start_utc,
        ),
        policy=policy_fields,
        coverage=CoverageOut(
            coverage_start_utc=result.coverage_start,
            coverage_end_utc=result.coverage_end,
            demo_now_utc=result.demo_now,
            last_observed_event_utc=result.last_observed_event_utc,
            warnings=result.warnings,
        ),
        summary=comparison_out(result.summary),
        account_summary=comparison_out(result.account_summary),
        locations=[location_out(row) for row in result.locations],
    )


def options_out(result: OptionsResult) -> OptionsOut:
    return OptionsOut(
        account=account_out(result.account),
        timezone=result.timezone,
        locations=result.locations,
        default_week=result.default_week,
        available_weeks=result.available_weeks,
        coverage=CoverageOut(
            coverage_start_utc=result.coverage_start,
            coverage_end_utc=result.coverage_end,
            demo_now_utc=result.demo_now,
            last_observed_event_utc=result.last_observed_event_utc,
            warnings=[],
        ),
    )
