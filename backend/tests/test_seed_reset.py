"""Reset must preserve existing rows on validation or import failure."""

from pathlib import Path

import pytest
from sqlalchemy import text

from app.reviews import seed
from tests.conftest import TEST_ADMIN_URL

SEED_FILE = Path(__file__).resolve().parents[2] / "review-input/starter/seed.sql"


@pytest.fixture
def existing_rows(admin_engine):
    with admin_engine.begin() as connection:
        connection.execute(text(
            "INSERT INTO accounts VALUES (9900, 'Existing account', 'Test', 'UTC', '2025-01-01Z')"
        ))
        connection.execute(text(
            "INSERT INTO activity_events VALUES "
            "(9900, 9900, 'Existing site', 'call_received', '2026-06-01Z', NULL, NULL)"
        ))
        connection.execute(text(
            "INSERT INTO seed_import "
            "(source_sha256, source_path, accounts_loaded, events_loaded, imported_at) "
            "VALUES (:digest, 'existing-data', 1, 1, '2026-06-02Z')"
        ), {"digest": "a" * 64})

    def snapshot():
        with admin_engine.connect() as connection:
            return [
                [tuple(row) for row in connection.execute(text(query))]
                for query in (
                    "SELECT * FROM accounts ORDER BY id",
                    "SELECT * FROM activity_events ORDER BY id",
                    "SELECT * FROM seed_import ORDER BY id",
                )
            ]

    return snapshot


@pytest.mark.parametrize("invalid_file", ["missing", "tampered"])
def test_cli_reset_preserves_rows_when_seed_is_invalid(existing_rows, monkeypatch, tmp_path, invalid_file):
    before = existing_rows()
    path = tmp_path / "invalid.sql"
    if invalid_file == "tampered":
        path.write_text("not the reviewed seed\n")
    monkeypatch.setenv("RELAY_ALLOW_RESET", "1")
    result = seed.main(["--seed-file", str(path), "--database-url", TEST_ADMIN_URL, "--reset"])
    assert result != 0
    assert existing_rows() == before


def test_cli_reset_rolls_back_clear_and_insert_on_load_failure(existing_rows, monkeypatch):
    before = existing_rows()
    monkeypatch.setenv("RELAY_ALLOW_RESET", "1")
    # Fail after the original data was cleared and replacement rows inserted.
    monkeypatch.setattr(seed, "_integrity_ok", lambda connection: False)
    result = seed.main(["--seed-file", str(SEED_FILE), "--database-url", TEST_ADMIN_URL, "--reset"])
    assert result == 2
    assert existing_rows() == before


def test_cli_reset_replaces_rows_and_remains_idempotent(existing_rows, monkeypatch):
    monkeypatch.setenv("RELAY_ALLOW_RESET", "1")
    assert seed.main(["--seed-file", str(SEED_FILE), "--database-url", TEST_ADMIN_URL, "--reset"]) == 0
    accounts, events, markers = existing_rows()
    assert len(accounts) == 20 and len(events) == 12626 and len(markers) == 1
    assert 9900 not in {row[0] for row in accounts}
    assert markers[0][1] == seed.EXPECTED_SHA256
    assert seed.run_import(SEED_FILE, TEST_ADMIN_URL).startswith("no-op")
