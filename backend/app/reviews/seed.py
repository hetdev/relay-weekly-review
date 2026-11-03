"""Seed import command — explicit, verifiable, and safe to rerun.

Usage:
    python -m app.reviews.seed --seed-file ../review-input/starter/seed.sql \
        [--database-url URL] [--reset]

Guarantees (PLAN.md section 5):
- The reviewed seed file is verified by SHA-256 and byte size before parsing.
- Parsing is strict line-by-line pattern matching (the file is data, never
  executed); any unmatched line fails the import.
- Loading is transactional; the marker row commits only with the data.
- A rerun against a matching, consistent database is a no-op. Inconsistent
  data or a different hash is a hard failure. Rows are never silently
  overwritten.
- --reset requires RELAY_ALLOW_RESET=1 and a relay_* database name, and is
  the only path that clears an existing demo database. Clearing and loading
  share one transaction; a failed import restores the existing data.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from sqlalchemy import create_engine, text

# Reviewed provenance for review-input/starter/seed.sql (review-input/provenance.json).
EXPECTED_SHA256 = "40e60ee81d999eb32057b4437bc84e9ec197265d4e58c13c0bfbad150e6eaea2"
EXPECTED_SIZE = 2_435_560
EXPECTED_ACCOUNTS = 20
EXPECTED_EVENTS = 12_626

_ACCOUNT_RE = re.compile(
    r"^INSERT INTO accounts \(id, name, industry, timezone, created_at\) VALUES "
    r"\((\d+), '((?:[^']|'')*)', '((?:[^']|'')*)', '([A-Za-z_/+0-9-]+)', "
    r"'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})'\);$"
)
_EVENT_RE = re.compile(
    r"^INSERT INTO activity_events \(id, account_id, location, event_type, occurred_at, "
    r"duration_seconds, outcome\) VALUES "
    r"\((\d+), (\d+), '((?:[^']|'')*)', '([a-z_]+)', "
    r"'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', (NULL|\d+), (NULL|'(?:[^']|'')*')\);$"
)


def _unquote(value: str) -> str:
    return value[1:-1].replace("''", "'")


def _utc(stamp: str) -> datetime:
    # Source timestamps carry no offset and are documented as UTC; that
    # interpretation is made here, explicitly, independent of any session
    # or machine timezone.
    return datetime.strptime(stamp, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)


def parse_seed_file(path: Path) -> tuple[list[tuple], list[tuple]]:
    accounts: list[tuple] = []
    events: list[tuple] = []
    for line_number, raw_line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        line = raw_line.strip()
        if not line or line.startswith("--"):
            continue
        account_match = _ACCOUNT_RE.match(line)
        if account_match is not None:
            aid, name, industry, tz_name, created = account_match.groups()
            # Regex groups for name/industry already exclude the quotes;
            # only outcome below carries its quotes inside the group.
            accounts.append((int(aid), name, industry, tz_name, _utc(created)))
            continue
        event_match = _EVENT_RE.match(line)
        if event_match is not None:
            eid, account_id, location, event_type, occurred, duration, outcome = (
                event_match.groups()
            )
            events.append(
                (
                    int(eid),
                    int(account_id),
                    location,
                    event_type,
                    _utc(occurred),
                    None if duration == "NULL" else int(duration),
                    None if outcome == "NULL" else _unquote(outcome),
                )
            )
            continue
        raise SeedError(f"unrecognized seed line {line_number}: {line[:120]!r}")
    if len(accounts) != EXPECTED_ACCOUNTS or len(events) != EXPECTED_EVENTS:
        raise SeedError(
            f"expected {EXPECTED_ACCOUNTS} accounts / {EXPECTED_EVENTS} events, "
            f"parsed {len(accounts)} / {len(events)}"
        )
    return accounts, events


class SeedError(RuntimeError):
    pass


def verify_file(path: Path) -> str:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
            size += len(chunk)
    if size != EXPECTED_SIZE or digest.hexdigest() != EXPECTED_SHA256:
        raise SeedError(
            f"seed file failed provenance check: size={size} sha256={digest.hexdigest()}"
        )
    return digest.hexdigest()


def _live_counts(connection) -> tuple[int, int]:
    accounts = connection.execute(text("SELECT count(*) FROM accounts")).scalar_one()
    events = connection.execute(text("SELECT count(*) FROM activity_events")).scalar_one()
    return int(accounts), int(events)


def _integrity_ok(connection) -> bool:
    orphans = connection.execute(
        text(
            "SELECT count(*) FROM activity_events e "
            "WHERE NOT EXISTS (SELECT 1 FROM accounts a WHERE a.id = e.account_id)"
        )
    ).scalar_one()
    return int(orphans) == 0


def run_import(seed_file: Path, database_url: str, *, reset: bool = False) -> str:
    digest = verify_file(seed_file)
    accounts, events = parse_seed_file(seed_file)
    if reset:
        _validate_reset_target(database_url)
    engine = create_engine(database_url, future=True)
    try:
        with engine.begin() as connection:
            if reset:
                connection.execute(
                    text("TRUNCATE activity_events, accounts, seed_import RESTART IDENTITY CASCADE")
                )
            marker = connection.execute(
                text("SELECT source_sha256 FROM seed_import ORDER BY imported_at DESC LIMIT 1")
            ).first()
            account_count, event_count = _live_counts(connection)
            if marker is not None:
                if (
                    marker.source_sha256 == digest
                    and (account_count, event_count) == (EXPECTED_ACCOUNTS, EXPECTED_EVENTS)
                    and _integrity_ok(connection)
                ):
                    return "no-op: matching marker, counts, and integrity verified"
                raise SeedError(
                    "database already contains an import marker with different content; "
                    "refusing to overwrite (use --reset on the disposable demo database)"
                )
            if account_count or event_count:
                raise SeedError(
                    f"database is non-empty without an import marker "
                    f"({account_count} accounts, {event_count} events); refusing to import"
                )
            connection.execute(
                text(
                    "INSERT INTO accounts (id, name, industry, timezone, created_at) "
                    "VALUES (:id, :name, :industry, :timezone, :created_at)"
                ),
                [
                    {
                        "id": a[0],
                        "name": a[1],
                        "industry": a[2],
                        "timezone": a[3],
                        "created_at": a[4],
                    }
                    for a in accounts
                ],
            )
            connection.execute(
                text(
                    "INSERT INTO activity_events (id, account_id, location, event_type, "
                    "occurred_at, duration_seconds, outcome) "
                    "VALUES (:id, :account_id, :location, :event_type, :occurred_at, "
                    ":duration_seconds, :outcome)"
                ),
                [
                    {
                        "id": e[0],
                        "account_id": e[1],
                        "location": e[2],
                        "event_type": e[3],
                        "occurred_at": e[4],
                        "duration_seconds": e[5],
                        "outcome": e[6],
                    }
                    for e in events
                ],
            )
            connection.execute(
                text(
                    "INSERT INTO seed_import "
                    "(source_sha256, source_path, accounts_loaded, events_loaded, imported_at) "
                    "VALUES (:sha, :path, :accounts, :events, :now)"
                ),
                {
                    "sha": digest,
                    "path": str(seed_file),
                    "accounts": EXPECTED_ACCOUNTS,
                    "events": EXPECTED_EVENTS,
                    "now": datetime.now(timezone.utc),
                },
            )
            # Post-conditions inside the same transaction: counts + FK integrity.
            final_counts = _live_counts(connection)
            if final_counts != (EXPECTED_ACCOUNTS, EXPECTED_EVENTS):
                raise SeedError(f"post-load counts mismatch: {final_counts}")
            if not _integrity_ok(connection):
                raise SeedError("post-load foreign-key integrity check failed")
        return f"imported {EXPECTED_ACCOUNTS} accounts and {EXPECTED_EVENTS} events ({digest[:12]})"
    finally:
        engine.dispose()


def _validate_reset_target(database_url: str) -> None:
    if os.environ.get("RELAY_ALLOW_RESET") != "1":
        raise SeedError("--reset requires RELAY_ALLOW_RESET=1 (disposable demo databases only)")
    database_name = (urlparse(database_url).path or "").lstrip("/")
    if not database_name.startswith("relay_"):
        raise SeedError(f"refusing to reset non-demo database {database_name!r}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Import the reviewed Relay seed fixture")
    parser.add_argument("--seed-file", type=Path, required=True)
    parser.add_argument(
        "--database-url",
        default=None,
        help="admin/migration URL (default: RELAY_ADMIN_DATABASE_URL or the dev default)",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="explicitly clear the disposable demo database before importing",
    )
    args = parser.parse_args(argv)

    from app.config import DEFAULT_ADMIN_DATABASE_URL, load_env_file

    load_env_file(Path(__file__).resolve().parents[2] / ".env")

    database_url = args.database_url or os.environ.get(
        "RELAY_ADMIN_DATABASE_URL", DEFAULT_ADMIN_DATABASE_URL
    )
    try:
        print(run_import(args.seed_file, database_url, reset=args.reset))
        return 0
    except SeedError as error:
        print(f"seed import failed: {error}", file=sys.stderr)
        return 2
    except Exception as error:  # connection issues etc.; nothing was committed
        print(f"seed import error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
