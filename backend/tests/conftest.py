"""Shared fixtures: a real PostgreSQL database, migrated once per session,
truncated between tests. Synthetic data is hand-calculated; expected values
never come from calling the implementation under test."""

from __future__ import annotations

import os
from datetime import date, datetime, timedelta, timezone
from itertools import count
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from app.config import (
    COVERAGE_END_DEFAULT,
    COVERAGE_START_DEFAULT,
    DEMO_NOW_DEFAULT,
    Settings,
)
from app.db.engine import create_db_engine
from app.main import create_app
from app.reviews.policy import PolicyConfig

BACKEND_DIR = Path(__file__).resolve().parents[1]

TEST_ADMIN_URL = os.environ.get(
    "RELAY_TEST_ADMIN_URL", "postgresql+psycopg://relay_admin@127.0.0.1:5433/relay_test"
)
TEST_APP_URL = os.environ.get(
    "RELAY_TEST_APP_URL", "postgresql+psycopg://relay_app@127.0.0.1:5433/relay_test"
)

SYNTHETIC_ACCOUNT_IDS = frozenset({9001, 9002, 9003, 9004, 9005})


def make_test_settings(allowed: frozenset[int] | None = SYNTHETIC_ACCOUNT_IDS) -> Settings:
    return Settings(
        database_url=TEST_APP_URL,
        admin_database_url=TEST_ADMIN_URL,
        allowed_account_ids=allowed,
        demo_now=DEMO_NOW_DEFAULT,
        coverage_start=COVERAGE_START_DEFAULT,
        coverage_end=COVERAGE_END_DEFAULT,
        policy=PolicyConfig(),
    )


@pytest.fixture(scope="session")
def admin_engine() -> Engine:
    """Migrate the test database once, grant the read-only role, hand out the
    admin engine."""
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    os.environ["RELAY_MIGRATION_DATABASE_URL"] = TEST_ADMIN_URL
    command.upgrade(config, "head")
    engine = create_engine(TEST_ADMIN_URL, future=True)
    with engine.begin() as connection:  # least-privilege grants for the app role
        connection.execute(text("GRANT USAGE ON SCHEMA public TO relay_app"))
        connection.execute(text("GRANT SELECT ON ALL TABLES IN SCHEMA public TO relay_app"))
    yield engine
    engine.dispose()


@pytest.fixture(autouse=True)
def clean_database(request, admin_engine: Engine) -> None:
    if request.node.get_closest_marker("no_truncate"):
        return  # module owns its own database lifecycle (e.g. seed tests)
    with admin_engine.begin() as connection:
        connection.execute(
            text("TRUNCATE activity_events, accounts, seed_import RESTART IDENTITY CASCADE")
        )


@pytest.fixture(scope="session")
def event_ids() -> count:
    return count(1)


# ---------------------------------------------------------------- builders


def insert_account(
    admin_engine: Engine,
    account_id: int,
    name: str,
    timezone_name: str,
    industry: str = "Test Industry",
    created_at: datetime = datetime(2025, 1, 1, tzinfo=timezone.utc),
) -> None:
    with admin_engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO accounts (id, name, industry, timezone, created_at) "
                "VALUES (:id, :name, :industry, :tz, :created)"
            ),
            {"id": account_id, "name": name, "industry": industry, "tz": timezone_name, "created": created_at},
        )


def insert_event(
    admin_engine: Engine,
    event_ids: count,
    account_id: int,
    location: str,
    when_utc: datetime,
    event_type: str = "call_received",
    duration_seconds: int | None = 60,
    outcome: str | None = "connected",
    event_id: int | None = None,
) -> int:
    with admin_engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO activity_events (id, account_id, location, event_type, occurred_at, "
                "duration_seconds, outcome) VALUES (:id, :aid, :loc, :etype, :ts, :dur, :outcome)"
            ),
            {
                "id": event_id or next(event_ids),
                "aid": account_id,
                "loc": location,
                "etype": event_type,
                "ts": when_utc,
                "dur": duration_seconds,
                "outcome": outcome,
            },
        )
    return event_id or 0


def local_noon(monday: date, tz: ZoneInfo, day_offset: int = 0, hour: int = 12) -> datetime:
    """A UTC instant at local noon inside the week beginning `monday`.

    Noon local avoids every DST boundary in US and UTC timezones.
    """
    local = datetime(monday.year, monday.month, monday.day, hour, 0, tzinfo=tz)
    local += timedelta(days=day_offset)
    return local.astimezone(timezone.utc)


def spread_events(
    admin_engine: Engine,
    event_ids: count,
    account_id: int,
    location: str,
    mondays: list[date],
    counts: list[int],
    tz: ZoneInfo,
    event_type: str = "call_received",
) -> None:
    """Insert counts[i] events in the week beginning mondays[i]."""
    for monday, how_many in zip(mondays, counts):
        for i in range(how_many):
            insert_event(
                admin_engine,
                event_ids,
                account_id,
                location,
                local_noon(monday, tz, day_offset=min(i, 5), hour=10 + (i % 6)),
                event_type=event_type,
            )


# Chicago baseline (8 covered weeks) + target for the default review week.
CHICAGO = ZoneInfo("America/Chicago")
BASELINE_MONDAYS = [date(2026, 5, 25) + timedelta(weeks=k) for k in range(8)]  # May 25 .. Jul 13
TARGET_MONDAY = date(2026, 7, 20)


def seed_isolation_fixture(admin_engine: Engine, event_ids: count) -> None:
    """Account 9001 (Chicago) with one location per classification rule,
    plus account 9002 (New York) sharing the location name 'Site A'."""
    insert_account(admin_engine, 9001, "Isolation Alpha", "America/Chicago")
    insert_account(admin_engine, 9002, "Isolation Beta", "America/New_York")

    # Anchor week (May 18) lies BEFORE the baseline window, so locations with
    # an anchor are "observed at or before the baseline began" without adding
    # counts to any baseline week.
    anchor_monday = date(2026, 5, 18)

    # Site A: baseline 10/week, target 4 -> drop 6 (>=5), 60% (>=20%) => below_recent_range
    spread_events(admin_engine, event_ids, 9001, "Site A", [anchor_monday], [1], CHICAGO)
    spread_events(admin_engine, event_ids, 9001, "Site A", BASELINE_MONDAYS, [10] * 8, CHICAGO)
    spread_events(admin_engine, event_ids, 9001, "Site A", [TARGET_MONDAY], [4], CHICAGO)

    # Site B: baseline 10/week, target 20 -> increase 10, 100% => above_recent_range
    spread_events(admin_engine, event_ids, 9001, "Site B", [anchor_monday], [1], CHICAGO)
    spread_events(admin_engine, event_ids, 9001, "Site B", BASELINE_MONDAYS, [10] * 8, CHICAGO)
    spread_events(admin_engine, event_ids, 9001, "Site B", [TARGET_MONDAY], [20], CHICAGO)

    # Site C: first observed Jun 16 (inside the baseline window) -> insufficient_history
    # and population_change at the account level. No anchor on purpose.
    late_mondays = [date(2026, 6, 15), date(2026, 6, 22), date(2026, 6, 29), date(2026, 7, 6), date(2026, 7, 13)]
    spread_events(admin_engine, event_ids, 9001, "Site C", late_mondays, [5, 5, 5, 5, 5], CHICAGO)
    spread_events(admin_engine, event_ids, 9001, "Site C", [TARGET_MONDAY], [30], CHICAGO)

    # Site D: low volume (reference 2 < 5), target 10 => low_volume
    spread_events(admin_engine, event_ids, 9001, "Site D", [anchor_monday], [1], CHICAGO)
    spread_events(admin_engine, event_ids, 9001, "Site D", BASELINE_MONDAYS, [2] * 8, CHICAGO)
    spread_events(admin_engine, event_ids, 9001, "Site D", [TARGET_MONDAY], [10], CHICAGO)

    # Site E: one lead in April (first observed), zero call baseline, 7 in target
    # => activity_after_zero_baseline with percent_change null
    insert_event(
        admin_engine, event_ids, 9001, "Site E",
        datetime(2026, 4, 15, 17, 0, tzinfo=timezone.utc), event_type="lead_created",
    )
    spread_events(admin_engine, event_ids, 9001, "Site E", [TARGET_MONDAY], [7], CHICAGO)

    # Site F: one lead in April, zero baseline, zero target => no_recent_activity
    insert_event(
        admin_engine, event_ids, 9001, "Site F",
        datetime(2026, 4, 16, 17, 0, tzinfo=timezone.utc), event_type="lead_created",
    )

    # Account 9002 Site A: baseline 100/week, target 100 => no_review_flag.
    # Its counts must never leak into 9001 despite the shared location name.
    ny = ZoneInfo("America/New_York")
    ny_anchor = date(2026, 5, 18)
    spread_events(admin_engine, event_ids, 9002, "Site A", [ny_anchor], [1], ny)
    spread_events(admin_engine, event_ids, 9002, "Site A", BASELINE_MONDAYS, [100] * 8, ny)
    spread_events(admin_engine, event_ids, 9002, "Site A", [TARGET_MONDAY], [100], ny)


def seed_calendar_fixture(admin_engine: Engine, event_ids: count) -> None:
    insert_account(admin_engine, 9003, "Early Bird", "UTC")
    insert_account(admin_engine, 9004, "Empty Account", "UTC")
    # One event on Feb 3 2026 UTC: week of Feb 2 is its only early activity.
    insert_event(
        admin_engine, event_ids, 9003, "Site A",
        datetime(2026, 2, 3, 12, 0, tzinfo=timezone.utc),
    )


@pytest.fixture
def client(admin_engine: Engine) -> TestClient:
    """API client over synthetic data with the default restricted principal."""
    seed_isolation_fixture(admin_engine, _shared_event_ids[0])
    seed_calendar_fixture(admin_engine, _shared_event_ids[0])
    engine = create_db_engine(TEST_APP_URL)
    app = create_app(settings=make_test_settings(), engine=engine)
    with TestClient(app) as test_client:
        yield test_client
    engine.dispose()


# Module-level counter shared by the client fixture (ids stay unique).
_shared_event_ids = [count(10_000)]


REVIEW_TARGET = {"week_start": TARGET_MONDAY.isoformat()}
