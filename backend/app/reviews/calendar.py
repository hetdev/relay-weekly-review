"""Local calendar weeks, constructed with zoneinfo — never fixed 168-hour spans.

A week is Monday 00:00 local to the following Monday 00:00 local, as a
half-open interval. Each boundary is constructed as a local wall-clock
midnight and converted to an aware UTC instant, so DST transitions can make
the elapsed length 167 or 169 hours without shifting the boundaries.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

UTC = timezone.utc


class CalendarError(ValueError):
    """Malformed or unsupported calendar input."""


def parse_week_start(value: str) -> date:
    """Strictly parse YYYY-MM-DD (rejects 2026-7-2 and friends)."""
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise CalendarError(f"week_start must be YYYY-MM-DD, got {value!r}") from exc
    if parsed.strftime("%Y-%m-%d") != value:
        raise CalendarError(f"week_start must be YYYY-MM-DD, got {value!r}")
    return parsed


def is_monday(day: date) -> bool:
    return day.weekday() == 0


def monday_of(day: date) -> date:
    return day - timedelta(days=day.weekday())


def local_midnight(monday: date, tz: ZoneInfo) -> datetime:
    """Midnight wall clock on the given date in tz, as an aware datetime."""
    return datetime(monday.year, monday.month, monday.day, tzinfo=tz)


def week_window(
    monday: date, tz: ZoneInfo
) -> tuple[datetime, datetime, datetime, datetime]:
    """(start_local, end_local, start_utc, end_utc) for the week beginning monday."""
    if not is_monday(monday):
        raise CalendarError(f"week must begin on a Monday, got {monday.isoformat()}")
    start_local = local_midnight(monday, tz)
    end_local = local_midnight(monday + timedelta(days=7), tz)
    return start_local, end_local, start_local.astimezone(UTC), end_local.astimezone(UTC)


def preceding_mondays(target: date, count: int) -> list[date]:
    """The `count` Mondays immediately before target, oldest first."""
    return [target - timedelta(weeks=k) for k in range(count, 0, -1)]


def week_covered(
    start_utc: datetime, end_utc: datetime, coverage_start: datetime, coverage_end: datetime
) -> bool:
    """A week is covered when its whole UTC interval lies inside the
    assumed recording interval."""
    return start_utc >= coverage_start and end_utc <= coverage_end


def latest_complete_monday(tz: ZoneInfo, now_utc: datetime, coverage_end: datetime) -> date:
    """Most recent Monday whose local week has fully ended by
    min(now_utc, coverage_end)."""
    limit = min(now_utc, coverage_end)
    candidate = monday_of(now_utc.astimezone(tz).date())
    for _ in range(2000):  # bounded walk; guards against unusable coverage
        _, _, _, end_utc = week_window(candidate, tz)
        if end_utc <= limit:
            return candidate
        candidate -= timedelta(days=7)
    raise CalendarError("no complete week exists within the supported coverage window")


def supported_mondays(
    tz: ZoneInfo, now_utc: datetime, coverage_start: datetime, coverage_end: datetime
) -> list[date]:
    """Every selectable complete Monday, oldest first."""
    latest = latest_complete_monday(tz, now_utc, coverage_end)
    mondays: list[date] = []
    candidate = latest
    for _ in range(2000):
        _, _, _, end_utc = week_window(candidate, tz)
        if end_utc <= coverage_start:
            break
        mondays.append(candidate)
        candidate -= timedelta(days=7)
    mondays.reverse()
    return mondays
