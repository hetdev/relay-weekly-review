"""Seed reconciliation: expectations calculated independently (direct SQL
against the fixed seed, boundaries computed here with zoneinfo) and stored
as literals with their calculation notes. The API must reproduce them.

Account 5 (Pacific Smiles, America/Los_Angeles), call_received, week of
2026-07-20 (all weeks PDT, UTC-7; window [Mon 07:00Z, next Mon 07:00Z)):
  baseline weekly totals from direct SQL: 24,18,19,23,20,13,36,26 (sum 179)
  target week total: 19; target per location: A=4,B=2,C=7,D=2,E=4 (sums to 19)
  reference = 179/8 = 22.375; delta = 19-22.375 = -3.375
  percent = 100*(-3.375)/22.375 = -15.0838...; range [13, 36] -> no_review_flag

Account 12 (Redline Tire & Service, LA), same metric/week:
  baseline: 31,32,33,26,30,45,37,38 (sum 272); target 31
  reference = 272/8 = 34.0; delta = -3.0; range [26, 45] -> no_review_flag
"""

from __future__ import annotations

import os
from datetime import date, timedelta
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
from app.reviews import seed as seed_module
from app.reviews.policy import PolicyConfig

RECON_ADMIN_URL = os.environ.get(
    "RELAY_RECON_ADMIN_URL", "postgresql+psycopg://relay_admin@127.0.0.1:5433/relay_recon"
)
RECON_APP_URL = os.environ.get(
    "RELAY_RECON_APP_URL", "postgresql+psycopg://relay_app@127.0.0.1:5433/relay_recon"
)
BACKEND_DIR = Path(__file__).resolve().parents[1]
SEED_FILE = BACKEND_DIR.parent / "review-input" / "starter" / "seed.sql"

LA = ZoneInfo("America/Los_Angeles")
BASELINE = [date(2026, 5, 25) + timedelta(weeks=k) for k in range(8)]
TARGET = date(2026, 7, 20)

ACCOUNT5_BASELINE = [24, 18, 19, 23, 20, 13, 36, 26]
ACCOUNT5_TARGET = 19
ACCOUNT5_TARGET_BY_LOCATION = {"Site A": 4, "Site B": 2, "Site C": 7, "Site D": 2, "Site E": 4}
ACCOUNT5_REFERENCE = 179 / 8  # 22.375

ACCOUNT12_BASELINE = [31, 32, 33, 26, 30, 45, 37, 38]
ACCOUNT12_TARGET = 31


@pytest.fixture(scope="module")
def recon_engine() -> Engine:
    os.environ["RELAY_MIGRATION_DATABASE_URL"] = RECON_ADMIN_URL
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    command.upgrade(config, "head")
    engine = create_engine(RECON_ADMIN_URL, future=True)
    with engine.begin() as connection:  # read-only role needs its grants here too
        connection.execute(text("GRANT USAGE ON SCHEMA public TO relay_app"))
        connection.execute(text("GRANT SELECT ON ALL TABLES IN SCHEMA public TO relay_app"))
    seed_module.run_import(SEED_FILE, RECON_ADMIN_URL)  # no-op when already imported
    yield engine
    engine.dispose()


@pytest.fixture(scope="module")
def recon_client(recon_engine: Engine) -> TestClient:
    settings = Settings(
        database_url=RECON_APP_URL,
        admin_database_url=RECON_ADMIN_URL,
        allowed_account_ids=None,
        demo_now=DEMO_NOW_DEFAULT,
        coverage_start=COVERAGE_START_DEFAULT,
        coverage_end=COVERAGE_END_DEFAULT,
        policy=PolicyConfig(),
    )
    engine = create_db_engine(RECON_APP_URL)
    app = create_app(settings=settings, engine=engine)
    with TestClient(app) as client:
        yield client
    engine.dispose()


def sql_week_count(connection, account_id: int, monday: date, tz=LA) -> int:
    """Independent boundary computation for this test only."""
    from datetime import datetime, timedelta, timezone

    start_local = datetime(monday.year, monday.month, monday.day, tzinfo=LA)
    end_local = start_local + timedelta(days=7)
    return int(
        connection.execute(
            text(
                "SELECT count(*) FROM activity_events "
                "WHERE account_id = :aid AND event_type = 'call_received' "
                "AND occurred_at >= :s AND occurred_at < :e"
            ),
            {
                "aid": account_id,
                "s": start_local.astimezone(timezone.utc),
                "e": end_local.astimezone(timezone.utc),
            },
        ).scalar_one()
    )


class TestStoredExpectations:
    def test_account5_totals_and_arithmetic(self, recon_client):
        data = recon_client.get(
            "/api/v1/accounts/5/weekly-review", params={"week_start": "2026-07-20"}
        ).json()
        summary = data["account_summary"]
        counts = [w["count"] for w in summary["weeks"]]
        assert counts == ACCOUNT5_BASELINE + [ACCOUNT5_TARGET]
        assert summary["count"] == ACCOUNT5_TARGET
        assert summary["reference"] == pytest.approx(ACCOUNT5_REFERENCE)
        assert summary["delta"] == pytest.approx(ACCOUNT5_TARGET - ACCOUNT5_REFERENCE)
        assert summary["percent_change"] == pytest.approx(
            100 * (ACCOUNT5_TARGET - ACCOUNT5_REFERENCE) / ACCOUNT5_REFERENCE
        )
        assert summary["observed_min"] == 13 and summary["observed_max"] == 36
        assert summary["reason"] == "no_review_flag"

    def test_account5_target_week_by_location_additive(self, recon_client):
        data = recon_client.get(
            "/api/v1/accounts/5/weekly-review", params={"week_start": "2026-07-20"}
        ).json()
        by_location = {row["location"]: row["view"]["count"] for row in data["locations"]}
        assert by_location == ACCOUNT5_TARGET_BY_LOCATION
        assert sum(by_location.values()) == ACCOUNT5_TARGET  # additive property

    def test_account12_totals(self, recon_client):
        data = recon_client.get(
            "/api/v1/accounts/12/weekly-review", params={"week_start": "2026-07-20"}
        ).json()
        counts = [w["count"] for w in data["account_summary"]["weeks"]]
        assert counts == ACCOUNT12_BASELINE + [ACCOUNT12_TARGET]
        assert data["account_summary"]["reference"] == pytest.approx(272 / 8)


class TestIndependentSqlSweep:
    @pytest.mark.parametrize("account_id", [5, 12])
    def test_every_location_week_count_matches_direct_sql(
        self, recon_client, recon_engine, account_id
    ):
        data = recon_client.get(
            f"/api/v1/accounts/{account_id}/weekly-review", params={"week_start": "2026-07-20"}
        ).json()
        with recon_engine.connect() as connection:
            for row in data["locations"]:
                location = row["location"].replace("'", "''")
                for point in row["view"]["weeks"]:
                    monday = point["week_start"]
                    year, month, day = (int(part) for part in monday.split("-"))
                    from datetime import datetime, timedelta, timezone

                    start_local = datetime(year, month, day, tzinfo=LA)
                    end_local = start_local + timedelta(days=7)
                    expected = int(
                        connection.execute(
                            text(
                                f"SELECT count(*) FROM activity_events "
                                f"WHERE account_id = {account_id} "
                                f"AND event_type = 'call_received' "
                                f"AND location = '{location}' "
                                f"AND occurred_at >= :s AND occurred_at < :e"
                            ),
                            {
                                "s": start_local.astimezone(timezone.utc),
                                "e": end_local.astimezone(timezone.utc),
                            },
                        ).scalar_one()
                    )
                    assert point["count"] == expected, (location, monday)

    def test_location_references_match_sql_means_where_classified(
        self, recon_client, recon_engine
    ):
        data = recon_client.get(
            "/api/v1/accounts/5/weekly-review", params={"week_start": "2026-07-20"}
        ).json()
        with recon_engine.connect() as connection:
            for row in data["locations"]:
                if row["view"]["reason"] == "insufficient_history":
                    continue
                location = row["location"].replace("'", "''")
                total = 0
                from datetime import datetime, timedelta, timezone

                for monday in BASELINE:
                    start_local = datetime(monday.year, monday.month, monday.day, tzinfo=LA)
                    end_local = start_local + timedelta(days=7)
                    total += int(
                        connection.execute(
                            text(
                                f"SELECT count(*) FROM activity_events "
                                f"WHERE account_id = 5 AND event_type = 'call_received' "
                                f"AND location = '{location}' "
                                f"AND occurred_at >= :s AND occurred_at < :e"
                            ),
                            {
                                "s": start_local.astimezone(timezone.utc),
                                "e": end_local.astimezone(timezone.utc),
                            },
                        ).scalar_one()
                    )
                assert row["view"]["reference"] == pytest.approx(total / 8), row["location"]

    def test_fixture_freshness_metadata_present(self, recon_client):
        data = recon_client.get(
            "/api/v1/accounts/5/weekly-review", params={"week_start": "2026-07-20"}
        ).json()
        assert data["coverage"]["last_observed_event_utc"].startswith("2026-07-2")
        options = recon_client.get("/api/v1/accounts/5/review-options").json()
        assert options["default_week"] == "2026-07-20"
        assert options["timezone"] == "America/Los_Angeles"
