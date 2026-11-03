"""Weekly-review application service.

Orchestrates account scope, time boundaries, aggregation, and the pure
comparison policy. Depends on the ReviewRepository port and the calendar/
policy modules only — never on FastAPI or SQLAlchemy types.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.config import Settings, validated_timezone
from app.reviews import calendar
from app.reviews.errors import AccountNotFound, DataQualityError, InvalidWeek, UnknownLocation
from app.reviews.metrics import Metric
from app.reviews.ports import AccountRecord, ReviewRepository
from app.reviews.policy import PolicyResult, classify, rank_key


@dataclass(frozen=True)
class WeekPoint:
    week_start: date
    covered: bool  # inside the assumed fixture recording interval
    count: int


@dataclass(frozen=True)
class ComparisonView:
    """Shared shape for the account rollup, a filtered scope, and each
    location row."""

    count: int
    reference: float | None
    delta: float | None
    percent_change: float | None
    observed_min: int | None
    observed_max: int | None
    reason: str | None
    weeks: list[WeekPoint] = field(default_factory=list)
    classification_suppressed: bool = False


@dataclass(frozen=True)
class LocationRow:
    location: str
    first_observed_utc: datetime | None
    view: ComparisonView


@dataclass(frozen=True)
class ReviewResult:
    account: AccountRecord
    metric: Metric
    location_filter: str | None
    timezone: str
    week_start_local: datetime
    week_end_local: datetime
    week_start_utc: datetime
    week_end_utc: datetime
    baseline_week_count: int
    baseline_weeks_covered: int
    baseline_start_utc: datetime
    coverage_start: datetime
    coverage_end: datetime
    demo_now: datetime
    last_observed_event_utc: datetime | None
    warnings: list[str]
    summary: ComparisonView  # selected population (account or filtered location)
    account_summary: ComparisonView  # always the full-account rollup
    locations: list[LocationRow]  # ranked; single row when a location filter is active


@dataclass(frozen=True)
class OptionsResult:
    account: AccountRecord
    timezone: str
    locations: list[str]  # known as of min(demo_now, coverage_end)
    default_week: date
    available_weeks: list[date]
    coverage_start: datetime
    coverage_end: datetime
    demo_now: datetime
    last_observed_event_utc: datetime | None


class ReviewService:
    def __init__(self, repository: ReviewRepository, settings: Settings) -> None:
        self._repository = repository
        self._settings = settings

    # ------------------------------------------------------------ accounts

    def list_accounts(self) -> list[AccountRecord]:
        allowed = self._settings.allowed_account_ids
        accounts = self._repository.list_accounts()
        if allowed is None:
            return accounts
        return [account for account in accounts if account.id in allowed]

    def _load_account(self, account_id: int) -> AccountRecord:
        account = self._repository.get_account(account_id)
        allowed = self._settings.allowed_account_ids
        if account is None or (allowed is not None and account_id not in allowed):
            raise AccountNotFound()
        try:
            validated_timezone(account.timezone)
        except ValueError as exc:
            raise DataQualityError(
                f"account {account_id} has an invalid timezone {account.timezone!r}"
            ) from exc
        return account

    # ------------------------------------------------------------ options

    def review_options(self, account_id: int) -> OptionsResult:
        account = self._load_account(account_id)
        tz = ZoneInfo(account.timezone)
        settings = self._settings
        visibility_limit = min(settings.demo_now, settings.coverage_end)
        first_observed = self._repository.location_first_observed(
            account_id, before_utc=visibility_limit
        )
        mondays = calendar.supported_mondays(
            tz, settings.demo_now, settings.coverage_start, settings.coverage_end
        )
        return OptionsResult(
            account=account,
            timezone=account.timezone,
            locations=sorted(first_observed),
            default_week=mondays[-1],
            available_weeks=mondays,
            coverage_start=settings.coverage_start,
            coverage_end=settings.coverage_end,
            demo_now=settings.demo_now,
            last_observed_event_utc=self._repository.last_observed_event(account_id),
        )

    # ------------------------------------------------------ weekly review

    def weekly_review(
        self,
        account_id: int,
        week_monday: date,
        metric: Metric,
        location_filter: str | None,
    ) -> ReviewResult:
        account = self._load_account(account_id)
        tz = ZoneInfo(account.timezone)
        settings = self._settings
        policy_config = settings.policy

        # -- boundaries ------------------------------------------------
        if not calendar.is_monday(week_monday):
            raise InvalidWeek(f"week_start must be a Monday, got {week_monday.isoformat()}")
        start_local, end_local, start_utc, end_utc = calendar.week_window(week_monday, tz)
        completeness_limit = min(settings.demo_now, settings.coverage_end)
        if end_utc > completeness_limit:
            raise InvalidWeek(
                "week is not complete yet under the fixture demo clock and coverage"
            )
        if end_utc <= settings.coverage_start:
            raise InvalidWeek("week ends before the supported fixture coverage begins")

        baseline_mondays = calendar.preceding_mondays(week_monday, policy_config.baseline_weeks)
        _, _, baseline_start_utc, _ = calendar.week_window(baseline_mondays[0], tz)

        # -- scope and known locations (never reveal the review's future) --
        first_observed = self._repository.location_first_observed(
            account_id, before_utc=end_utc
        )
        if location_filter is not None:
            options_locations = self._repository.location_first_observed(
                account_id, before_utc=completeness_limit
            )
            if location_filter not in options_locations:
                raise UnknownLocation(
                    f"location {location_filter!r} is not known for account {account_id}"
                )

        # -- one bounded aggregation query for the whole window ----------
        aggregate_rows = self._repository.weekly_counts_by_location(
            account_id,
            metric.value,
            window_start_utc=baseline_start_utc,
            window_end_utc=end_utc,
            tz_name=account.timezone,
        )
        counts: dict[tuple[str, date], int] = {
            (row.location, row.week_monday): row.event_count for row in aggregate_rows
        }

        # -- zero-filled buckets over calendar boundaries ----------------
        all_mondays = baseline_mondays + [week_monday]
        covered_flags = {
            monday: calendar.week_covered(
                *calendar.week_window(monday, tz)[2:],
                settings.coverage_start,
                settings.coverage_end,
            )
            for monday in all_mondays
        }
        observed_locations = set(first_observed) | (
            {location_filter} if location_filter is not None else set()
        )

        def weeks_for(location: str) -> list[WeekPoint]:
            return [
                WeekPoint(monday, covered_flags[monday], counts.get((location, monday), 0))
                for monday in all_mondays
            ]

        def covered_baseline(weeks: list[WeekPoint]) -> tuple[int, ...]:
            return tuple(point.count for point in weeks[:-1] if point.covered)

        # -- per-location rows --------------------------------------------
        location_rows: list[LocationRow] = []
        for location in sorted(observed_locations):
            weeks = weeks_for(location)
            location_first_seen = first_observed.get(location)
            observed_before_baseline = (
                location_first_seen is not None and location_first_seen <= baseline_start_utc
            )
            result = classify(
                policy_config,
                count=weeks[-1].count,
                covered_baseline_counts=covered_baseline(weeks),
                first_observed_before_baseline=observed_before_baseline,
            )
            location_rows.append(
                LocationRow(location, location_first_seen, _view(result, weeks))
            )
        location_rows.sort(
            key=lambda row: rank_key(
                row.location,
                row.view.reason,
                row.view.count,
                row.view.observed_min,
                row.view.observed_max,
            )
        )

        # -- full-account rollup from all account events -------------------
        account_weeks = [
            WeekPoint(
                monday,
                covered_flags[monday],
                sum(counts.get((location, monday), 0) for location in first_observed),
            )
            for monday in all_mondays
        ]
        warnings: list[str] = []
        if first_observed:
            account_first_observed = min(first_observed.values())
            account_result = classify(
                policy_config,
                count=account_weeks[-1].count,
                covered_baseline_counts=covered_baseline(account_weeks),
                first_observed_before_baseline=account_first_observed <= baseline_start_utc,
            )
            account_view = _view(account_result, account_weeks)
            # Population stability: a location that first appears inside or
            # after the baseline window changes the comparison population.
            # Warn and suppress the overall classification; totals stay visible.
            late_locations = [
                location
                for location, first_seen in first_observed.items()
                if first_seen > baseline_start_utc
            ]
            if late_locations and account_view.reason not in (
                "insufficient_history",
                "no_activity_recorded",
            ):
                warnings.append("population_change")
                account_view = replace(account_view, reason=None, classification_suppressed=True)
        else:
            # No events observed as of this week's end (rule 1).
            account_view = ComparisonView(
                count=0,
                reference=None,
                delta=None,
                percent_change=None,
                observed_min=None,
                observed_max=None,
                reason="no_activity_recorded",
                weeks=account_weeks,
            )

        summary = account_view
        if location_filter is not None:
            summary = next(
                row.view for row in location_rows if row.location == location_filter
            )
            # A filtered view shows exactly the selected population.
            location_rows = [row for row in location_rows if row.location == location_filter]

        return ReviewResult(
            account=account,
            metric=metric,
            location_filter=location_filter,
            timezone=account.timezone,
            week_start_local=start_local,
            week_end_local=end_local,
            week_start_utc=start_utc,
            week_end_utc=end_utc,
            baseline_week_count=policy_config.baseline_weeks,
            baseline_weeks_covered=sum(1 for monday in baseline_mondays if covered_flags[monday]),
            baseline_start_utc=baseline_start_utc,
            coverage_start=settings.coverage_start,
            coverage_end=settings.coverage_end,
            demo_now=settings.demo_now,
            last_observed_event_utc=self._repository.last_observed_event(account_id),
            warnings=warnings,
            summary=summary,
            account_summary=account_view,
            locations=location_rows,
        )


def _view(result: PolicyResult, weeks: list[WeekPoint]) -> ComparisonView:
    return ComparisonView(
        count=weeks[-1].count,
        reference=result.reference,
        delta=result.delta,
        percent_change=result.percent_change,
        observed_min=result.observed_min,
        observed_max=result.observed_max,
        reason=result.reason,
        weeks=weeks,
    )
