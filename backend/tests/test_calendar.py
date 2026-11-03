"""Calendar unit tests: local Monday boundaries, DST transitions, coverage."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from app.reviews.calendar import (
    CalendarError,
    is_monday,
    latest_complete_monday,
    local_midnight,
    monday_of,
    parse_week_start,
    preceding_mondays,
    supported_mondays,
    week_covered,
    week_window,
)

UTC = timezone.utc
CHICAGO = ZoneInfo("America/Chicago")
NEW_YORK = ZoneInfo("America/New_York")
PHOENIX = ZoneInfo("America/Phoenix")


class TestParsing:
    def test_strict_iso_format(self):
        assert parse_week_start("2026-07-20") == date(2026, 7, 20)

    @pytest.mark.parametrize("bad", ["2026-7-20", "2026-07-5", "26-07-20", "2026/07/20", "2026-13-01", ""])
    def test_rejects_malformed(self, bad):
        with pytest.raises(CalendarError):
            parse_week_start(bad)

    def test_is_monday(self):
        assert is_monday(date(2026, 7, 20))
        assert not is_monday(date(2026, 7, 21))
        assert monday_of(date(2026, 7, 25)) == date(2026, 7, 20)


class TestWeekWindows:
    def test_utc_week_boundaries_half_open(self):
        start_l, end_l, start_u, end_u = week_window(date(2026, 7, 20), ZoneInfo("UTC"))
        assert start_l == datetime(2026, 7, 20, tzinfo=UTC)
        assert end_l == datetime(2026, 7, 27, tzinfo=UTC)
        assert start_u == datetime(2026, 7, 20, tzinfo=UTC)
        assert end_u == datetime(2026, 7, 27, tzinfo=UTC)
        assert end_u - start_u == timedelta(hours=168)

    def test_dst_spring_forward_week_is_167_hours_in_chicago(self):
        # US DST starts Sun 2026-03-08 02:00 CST -> 03:00 CDT
        _, _, start_u, end_u = week_window(date(2026, 3, 2), CHICAGO)
        assert start_u == datetime(2026, 3, 2, 6, 0, tzinfo=UTC)  # Monday 00:00 CST = 06:00Z
        assert end_u == datetime(2026, 3, 9, 5, 0, tzinfo=UTC)  # next Monday 00:00 CDT = 05:00Z
        assert end_u - start_u == timedelta(hours=167)

    def test_dst_fall_back_week_is_169_hours_in_new_york(self):
        # US DST ends Sun 2026-11-01 02:00 EDT -> 01:00 EST
        _, _, start_u, end_u = week_window(date(2026, 10, 26), NEW_YORK)
        assert start_u == datetime(2026, 10, 26, 4, 0, tzinfo=UTC)  # 00:00 EDT
        assert end_u == datetime(2026, 11, 2, 5, 0, tzinfo=UTC)  # 00:00 EST
        assert end_u - start_u == timedelta(hours=169)

    def test_phoenix_has_no_dst(self):
        for monday in (date(2026, 3, 2), date(2026, 10, 26), date(2026, 7, 20)):
            _, _, start_u, end_u = week_window(monday, PHOENIX)
            assert end_u - start_u == timedelta(hours=168)

    def test_local_midnight_converts_correctly_across_the_year(self):
        for monday in (date(2026, 1, 5), date(2026, 7, 20), date(2026, 12, 21)):
            _, _, start_u, _ = week_window(monday, CHICAGO)
            assert start_u == local_midnight(monday, CHICAGO).astimezone(UTC)

    def test_rejects_non_monday(self):
        with pytest.raises(CalendarError):
            week_window(date(2026, 7, 21), CHICAGO)

    def test_month_and_year_boundaries(self):
        # Week spanning a month boundary and one spanning a year boundary.
        _, _, s1, e1 = week_window(date(2026, 3, 30), CHICAGO)
        assert s1.utctimetuple().tm_mon == 3 and e1.utctimetuple().tm_mon == 4
        _, _, s2, e2 = week_window(date(2026, 12, 28), NEW_YORK)
        assert s2.utctimetuple().tm_year == 2026 and e2.utctimetuple().tm_year == 2027


class TestBaseline:
    def test_preceding_mondays_oldest_first(self):
        assert preceding_mondays(date(2026, 7, 20), 8) == [
            date(2026, 5, 25), date(2026, 6, 1), date(2026, 6, 8), date(2026, 6, 15),
            date(2026, 6, 22), date(2026, 6, 29), date(2026, 7, 6), date(2026, 7, 13),
        ]

    def test_target_week_excluded_from_baseline(self):
        assert date(2026, 7, 20) not in preceding_mondays(date(2026, 7, 20), 8)


class TestCoverage:
    def test_week_covered_requires_full_interval_inside(self):
        cov_start = datetime(2026, 2, 1, tzinfo=UTC)
        cov_end = datetime(2026, 7, 28, tzinfo=UTC)
        # UTC week Feb 2-9: fully inside
        assert week_covered(*week_window(date(2026, 2, 2), ZoneInfo("UTC"))[2:], cov_start, cov_end)
        # UTC week Jan 26 - Feb 2: starts before coverage
        assert not week_covered(*week_window(date(2026, 1, 26), ZoneInfo("UTC"))[2:], cov_start, cov_end)
        # Week ending after coverage_end is not covered
        assert not week_covered(*week_window(date(2026, 7, 27), ZoneInfo("UTC"))[2:], cov_start, cov_end)


class TestLatestComplete:
    def test_demo_clock_yields_july_20_everywhere(self):
        now = datetime(2026, 7, 28, 12, 0, tzinfo=UTC)
        cov_end = datetime(2026, 7, 28, 0, 0, tzinfo=UTC)
        for tz in (UTC, CHICAGO, NEW_YORK, PHOENIX):
            assert latest_complete_monday(tz, now, cov_end) == date(2026, 7, 20)

    def test_coverage_end_limits_before_clock(self):
        now = datetime(2026, 7, 30, tzinfo=UTC)
        cov_end = datetime(2026, 7, 21, tzinfo=UTC)
        # Latest week must end by Jul 21: for Chicago that is Jul 13 (ends Jul 20 05:00Z)
        assert latest_complete_monday(CHICAGO, now, cov_end) == date(2026, 7, 13)

    def test_supported_mondays_spans_coverage(self):
        now = datetime(2026, 7, 28, 12, 0, tzinfo=UTC)
        cov_end = datetime(2026, 7, 28, tzinfo=UTC)
        cov_start = datetime(2026, 2, 1, tzinfo=UTC)
        mondays = supported_mondays(ZoneInfo("UTC"), now, cov_start, cov_end)
        assert mondays[-1] == date(2026, 7, 20)
        # The week of Jan 26 ends Feb 2 (after coverage begins), so it stays
        # selectable with an insufficient-history display; Jan 19 ends Jan 26
        # and is rejected entirely.
        assert mondays[0] == date(2026, 1, 26)
        assert len(mondays) == 26  # Jan 26 .. Jul 20 inclusive
        assert mondays == sorted(mondays)
