"""Repository integration tests against real PostgreSQL: bucketing across
DST, duplicates, nullables, quoting, account scoping, FK enforcement."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

from app.reviews.repository import SqlReviewRepository
from tests.conftest import TEST_ADMIN_URL, insert_account, insert_event, local_noon

CHICAGO = ZoneInfo("America/Chicago")
UTC = timezone.utc


@pytest.fixture
def repository(admin_engine) -> SqlReviewRepository:
    with admin_engine.connect() as connection:
        yield SqlReviewRepository(connection)


class TestWeeklyBucketing:
    def test_spring_forward_week_buckets_by_local_wall_clock(self, admin_engine, event_ids, repository):
        insert_account(admin_engine, 101, "DST", "America/Chicago")
        # Weeks start Monday, so Sunday Mar 8 belongs to the week of Mar 2.
        # Sat Mar 7 23:30Z = 17:30 CST -> week of Mar 2
        insert_event(admin_engine, event_ids, 101, "Site A", datetime(2026, 3, 7, 23, 30, tzinfo=UTC))
        # Sun Mar 8 06:30Z = 00:30 CST (before the 02:00 jump) -> week of Mar 2
        insert_event(admin_engine, event_ids, 101, "Site A", datetime(2026, 3, 8, 6, 30, tzinfo=UTC))
        # Sun Mar 8 08:30Z = 03:30 CDT (after the jump, same wall date) -> week of Mar 2
        insert_event(admin_engine, event_ids, 101, "Site A", datetime(2026, 3, 8, 8, 30, tzinfo=UTC))
        # Mon Mar 9 06:30Z = 01:30 CDT -> week of Mar 9
        insert_event(admin_engine, event_ids, 101, "Site A", datetime(2026, 3, 9, 6, 30, tzinfo=UTC))

        rows = repository.weekly_counts_by_location(
            101, "call_received",
            datetime(2026, 3, 2, 6, 0, tzinfo=UTC),  # week_window(Mar 2) start
            datetime(2026, 3, 16, 5, 0, tzinfo=UTC),  # end of week of Mar 9
            "America/Chicago",
        )
        by_week = {(row.location, row.week_monday): row.event_count for row in rows}
        assert by_week == {("Site A", date(2026, 3, 2)): 3, ("Site A", date(2026, 3, 9)): 1}

    def test_fall_back_week_buckets_correctly(self, admin_engine, event_ids, repository):
        insert_account(admin_engine, 102, "Fall", "America/New_York")
        # Sunday Nov 1 belongs to the week starting Monday Oct 26.
        insert_event(admin_engine, event_ids, 102, "Site A", datetime(2026, 10, 31, 23, 30, tzinfo=UTC))  # Sat 19:30 EDT
        insert_event(admin_engine, event_ids, 102, "Site A", datetime(2026, 11, 1, 4, 30, tzinfo=UTC))   # Sun 00:30 EDT
        insert_event(admin_engine, event_ids, 102, "Site A", datetime(2026, 11, 1, 6, 30, tzinfo=UTC))   # Sun 01:30 EST (after fall back)
        insert_event(admin_engine, event_ids, 102, "Site A", datetime(2026, 11, 2, 5, 30, tzinfo=UTC))   # Mon 00:30 EST = 05:30Z -> week Nov 2

        rows = repository.weekly_counts_by_location(
            102, "call_received",
            datetime(2026, 10, 26, 4, 0, tzinfo=UTC),
            datetime(2026, 11, 9, 5, 0, tzinfo=UTC),
            "America/New_York",
        )
        by_week = {(row.location, row.week_monday): row.event_count for row in rows}
        assert by_week == {("Site A", date(2026, 10, 26)): 3, ("Site A", date(2026, 11, 2)): 1}

    def test_half_open_interval_excludes_endpoint(self, admin_engine, event_ids, repository):
        insert_account(admin_engine, 103, "HalfOpen", "UTC")
        insert_event(admin_engine, event_ids, 103, "Site A", datetime(2026, 3, 9, 0, 0, tzinfo=UTC))
        rows = repository.weekly_counts_by_location(
            103, "call_received",
            datetime(2026, 3, 2, tzinfo=UTC), datetime(2026, 3, 9, tzinfo=UTC), "UTC",
        )
        assert rows == []  # event exactly at window end is excluded

    def test_metric_filter_uses_single_path(self, admin_engine, event_ids, repository):
        insert_account(admin_engine, 104, "Metrics", "UTC")
        monday = date(2026, 6, 1)
        insert_event(admin_engine, event_ids, 104, "Site A", local_noon(monday, ZoneInfo("UTC")), event_type="call_received")
        insert_event(admin_engine, event_ids, 104, "Site A", local_noon(monday, ZoneInfo("UTC")), event_type="lead_created")
        insert_event(admin_engine, event_ids, 104, "Site A", local_noon(monday, ZoneInfo("UTC")), event_type="lead_created")
        for metric, expected in (("call_received", 1), ("lead_created", 2), ("appointment_set", 0)):
            rows = repository.weekly_counts_by_location(
                104, metric, datetime(2026, 5, 31, tzinfo=UTC), datetime(2026, 6, 8, tzinfo=UTC), "UTC"
            )
            total = sum(row.event_count for row in rows)
            assert total == expected


class TestSourceMessiness:
    def test_duplicate_payloads_with_distinct_ids_count_twice(self, admin_engine, event_ids, repository):
        insert_account(admin_engine, 105, "Dupes", "UTC")
        when = datetime(2026, 6, 2, 12, 0, tzinfo=UTC)
        insert_event(admin_engine, event_ids, 105, "Site A", when, event_id=501)
        insert_event(admin_engine, event_ids, 105, "Site A", when, event_id=502)  # same payload, new id
        rows = repository.weekly_counts_by_location(
            105, "call_received", datetime(2026, 6, 1, tzinfo=UTC), datetime(2026, 6, 8, tzinfo=UTC), "UTC"
        )
        assert rows[0].event_count == 2

    def test_nullable_and_unusual_values_round_trip(self, admin_engine, event_ids):
        insert_account(admin_engine, 106, "Nulls", "UTC")
        insert_event(admin_engine, event_ids, 106, "Site A", datetime(2026, 6, 2, tzinfo=UTC), duration_seconds=None, outcome=None)
        insert_event(admin_engine, event_ids, 106, "Site A", datetime(2026, 6, 3, tzinfo=UTC), duration_seconds=999999, outcome="weird_future_outcome")
        engine = create_engine(TEST_ADMIN_URL, future=True)
        with engine.connect() as connection:
            rows = connection.execute(
                text("SELECT duration_seconds, outcome FROM activity_events WHERE account_id=106 ORDER BY id")
            ).all()
        engine.dispose()
        assert rows == [(None, None), (999999, "weird_future_outcome")]

    def test_quoted_location_string_is_bound_safely(self, admin_engine, event_ids, repository):
        insert_account(admin_engine, 107, "Quoted", "UTC")
        nasty = "O'Harbor -- ; DROP TABLE activity_events; --"
        insert_event(admin_engine, event_ids, 107, nasty, datetime(2026, 6, 2, tzinfo=UTC))
        first = repository.location_first_observed(107, before_utc=datetime(2026, 7, 1, tzinfo=UTC))
        assert nasty in first

    def test_fk_enforced_for_unknown_account(self, admin_engine, event_ids):
        insert_account(admin_engine, 108, "FK", "UTC")
        engine = create_engine(TEST_ADMIN_URL, future=True)
        with pytest.raises(IntegrityError):
            with engine.begin() as connection:
                connection.execute(
                    text("INSERT INTO activity_events (id, account_id, location, event_type, occurred_at) "
                         "VALUES (999001, 424242, 'X', 'call_received', '2026-06-02T12:00:00+00:00')")
                )
        engine.dispose()


class TestAccountScoping:
    def test_same_location_names_stay_isolated(self, admin_engine, event_ids, repository):
        insert_account(admin_engine, 110, "Alpha", "UTC")
        insert_account(admin_engine, 111, "Beta", "UTC")
        for account_id, count in ((110, 3), (111, 7)):
            for _ in range(count):
                insert_event(admin_engine, event_ids, account_id, "Site A", datetime(2026, 6, 2, 12, 0, tzinfo=UTC))
        for account_id, expected in ((110, 3), (111, 7)):
            rows = repository.weekly_counts_by_location(
                account_id, "call_received",
                datetime(2026, 6, 1, tzinfo=UTC), datetime(2026, 6, 8, tzinfo=UTC), "UTC",
            )
            assert sum(r.event_count for r in rows) == expected

    def test_first_observed_never_reveals_future_locations(self, admin_engine, event_ids, repository):
        insert_account(admin_engine, 112, "Future", "UTC")
        insert_event(admin_engine, event_ids, 112, "Past Site", datetime(2026, 3, 2, tzinfo=UTC))
        insert_event(admin_engine, event_ids, 112, "Future Site", datetime(2026, 6, 2, tzinfo=UTC))
        as_of_may = repository.location_first_observed(112, before_utc=datetime(2026, 5, 1, tzinfo=UTC))
        assert list(as_of_may) == ["Past Site"]
        as_of_july = repository.location_first_observed(112, before_utc=datetime(2026, 7, 1, tzinfo=UTC))
        assert sorted(as_of_july) == ["Future Site", "Past Site"]
