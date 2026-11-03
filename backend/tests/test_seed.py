"""Seed import behavior: verification, idempotence, tamper resistance, UTC
independence of the session timezone."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

from app.reviews import seed as seed_module
from tests.conftest import BACKEND_DIR, TEST_ADMIN_URL

SEED_FILE = BACKEND_DIR.parent / "review-input" / "starter" / "seed.sql"

# These tests own the database lifecycle for the whole module: no per-test
# truncation, each test advances the marker/data state deliberately.
pytestmark = pytest.mark.no_truncate


@pytest.fixture(scope="module")
def seed_database_url(admin_engine_module):
    yield TEST_ADMIN_URL


@pytest.fixture(scope="module")
def admin_engine_module():
    """Module-scoped: the seed tests own the whole database layout."""
    from alembic import command
    from alembic.config import Config

    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    import os

    os.environ["RELAY_MIGRATION_DATABASE_URL"] = TEST_ADMIN_URL
    command.upgrade(config, "head")
    engine = create_engine(TEST_ADMIN_URL, future=True)
    with engine.begin() as connection:
        connection.execute(text("TRUNCATE activity_events, accounts, seed_import RESTART IDENTITY CASCADE"))
    yield engine
    engine.dispose()


class TestImport:
    def test_first_import_loads_verified_counts(self, seed_database_url):
        message = seed_module.run_import(SEED_FILE, seed_database_url)
        assert "imported 20 accounts and 12626 events" in message
        engine = create_engine(seed_database_url, future=True)
        with engine.connect() as connection:
            accounts = connection.execute(text("SELECT count(*) FROM accounts")).scalar_one()
            events = connection.execute(text("SELECT count(*) FROM activity_events")).scalar_one()
            marker = connection.execute(text("SELECT source_sha256 FROM seed_import")).scalar_one()
            orphans = connection.execute(
                text("SELECT count(*) FROM activity_events e WHERE NOT EXISTS "
                     "(SELECT 1 FROM accounts a WHERE a.id = e.account_id)")
            ).scalar_one()
        engine.dispose()
        assert (accounts, events) == (20, 12626)
        assert marker == seed_module.EXPECTED_SHA256
        assert orphans == 0

    def test_rerun_is_a_noop(self, seed_database_url):
        assert seed_module.run_import(SEED_FILE, seed_database_url).startswith("no-op")

    def test_tampered_file_fails_provenance_and_changes_nothing(self, seed_database_url, tmp_path):
        tampered = tmp_path / "seed_tampered.sql"
        lines = SEED_FILE.read_text(encoding="utf-8").splitlines()
        lines.append(
            "INSERT INTO activity_events (id, account_id, location, event_type, occurred_at, "
            "duration_seconds, outcome) VALUES (999999, 1, 'Evil', 'call_received', "
            "'2026-07-01 00:00:00', NULL, NULL);"
        )
        tampered.write_text("\n".join(lines) + "\n", encoding="utf-8")
        with pytest.raises(seed_module.SeedError, match="provenance"):
            seed_module.run_import(tampered, seed_database_url)
        engine = create_engine(seed_database_url, future=True)
        with engine.connect() as connection:
            events = connection.execute(text("SELECT count(*) FROM activity_events")).scalar_one()
        engine.dispose()
        assert events == 12626  # unchanged

    def test_marker_mismatch_refuses_overwrite(self, seed_database_url):
        engine = create_engine(seed_database_url, future=True)
        with engine.begin() as connection:
            connection.execute(text("UPDATE seed_import SET source_sha256 = '0' * 64"))
        engine.dispose()
        with pytest.raises(seed_module.SeedError, match="refusing"):
            seed_module.run_import(SEED_FILE, seed_database_url)

    def test_nonempty_without_marker_refuses(self, seed_database_url):
        engine = create_engine(seed_database_url, future=True)
        with engine.begin() as connection:
            connection.execute(text("DELETE FROM seed_import"))
        engine.dispose()
        with pytest.raises(seed_module.SeedError, match="non-empty"):
            seed_module.run_import(SEED_FILE, seed_database_url)

    def test_utc_interpretation_independent_of_session_timezone(self, seed_database_url):
        # A session pinned to Asia/Tokyo must read the same instants.
        engine = create_engine(
            seed_database_url,
            connect_args={"options": "-c timezone=Asia/Tokyo"},
            future=True,
        )
        with engine.connect() as connection:
            session_tz = connection.execute(text("SHOW timezone")).scalar_one()
            row = connection.execute(
                text("SELECT occurred_at FROM activity_events WHERE id = 1")
            ).scalar_one()
        engine.dispose()
        assert session_tz == "Asia/Tokyo"
        assert row == datetime(2026, 2, 1, 10, 57, 44, tzinfo=timezone.utc)

    def test_nullables_preserved_from_source(self, seed_database_url):
        engine = create_engine(seed_database_url, future=True)
        with engine.connect() as connection:
            null_durations = connection.execute(
                text("SELECT count(*) FROM activity_events WHERE duration_seconds IS NULL")
            ).scalar_one()
            null_outcomes = connection.execute(
                text("SELECT count(*) FROM activity_events WHERE outcome IS NULL")
            ).scalar_one()
        engine.dispose()
        assert null_durations > 0 and null_outcomes > 0
