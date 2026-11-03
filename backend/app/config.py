"""Application settings.

Values come from environment variables with fixture defaults documented in
PLAN.md section 6. Everything is explicit: no hidden configuration files.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from app.reviews.policy import PolicyConfig

# Fixture observation assumptions (PLAN.md section 6, "Observation and clock").
# These are documented assumptions, not inferred service guarantees.
DEMO_NOW_DEFAULT = datetime(2026, 7, 28, 12, 0, 0, tzinfo=timezone.utc)
COVERAGE_START_DEFAULT = datetime(2026, 2, 1, 0, 0, 0, tzinfo=timezone.utc)
COVERAGE_END_DEFAULT = datetime(2026, 7, 28, 0, 0, 0, tzinfo=timezone.utc)

DEFAULT_DATABASE_URL = "postgresql+psycopg://relay_app@127.0.0.1:5433/relay_dev"
DEFAULT_ADMIN_DATABASE_URL = "postgresql+psycopg://relay_admin@127.0.0.1:5433/relay_dev"


def _parse_utc_datetime(value: str, label: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError(f"{label} must include a UTC offset, got {value!r}")
    return parsed.astimezone(timezone.utc)


@dataclass(frozen=True)
class Settings:
    """Runtime settings for one API process."""

    database_url: str
    admin_database_url: str
    allowed_account_ids: frozenset[int] | None  # None => trusted demo admin sees all
    demo_now: datetime
    coverage_start: datetime
    coverage_end: datetime
    policy: PolicyConfig

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> "Settings":
        source = dict(os.environ)
        if env is not None:
            source.update(env)
        allowed_raw = (source.get("RELAY_ALLOWED_ACCOUNT_IDS") or "").strip()
        if allowed_raw:
            allowed: frozenset[int] | None = frozenset(
                int(part) for part in allowed_raw.split(",") if part.strip()
            )
        else:
            allowed = None
        return cls(
            database_url=source.get("RELAY_DATABASE_URL", DEFAULT_DATABASE_URL),
            admin_database_url=source.get(
                "RELAY_ADMIN_DATABASE_URL", DEFAULT_ADMIN_DATABASE_URL
            ),
            allowed_account_ids=allowed,
            demo_now=_parse_utc_datetime(
                source.get("RELAY_DEMO_NOW") or _iso(DEMO_NOW_DEFAULT), "RELAY_DEMO_NOW"
            ),
            coverage_start=_parse_utc_datetime(
                source.get("RELAY_COVERAGE_START") or _iso(COVERAGE_START_DEFAULT),
                "RELAY_COVERAGE_START",
            ),
            coverage_end=_parse_utc_datetime(
                source.get("RELAY_COVERAGE_END") or _iso(COVERAGE_END_DEFAULT),
                "RELAY_COVERAGE_END",
            ),
            policy=PolicyConfig(),
        )


def _iso(moment: datetime) -> str:
    return moment.isoformat()


def load_env_file(path: Path) -> None:
    """Load a .env file into os.environ without overriding existing values.

    Tiny stand-in for python-dotenv so the demo has one less dependency.
    Only KEY=VALUE lines; comments and blanks are ignored.
    """
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        key = key.strip()
        value = value.strip().strip("'\"")
        if key and key not in os.environ:
            os.environ[key] = value


def validated_timezone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except Exception as exc:  # invalid IANA name stored in the database
        raise ValueError(f"unknown IANA timezone {name!r}") from exc
