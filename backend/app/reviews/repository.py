"""SQLAlchemy adapter behind the ReviewRepository port.

All values are bound parameters; nothing from a request is ever interpolated
into SQL text. Aggregation happens in PostgreSQL; the adapter returns
aggregate DTOs only.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.reviews.ports import AccountRecord, LocationWeekCount

_ACCOUNT_SELECT = text(
    "SELECT id, name, industry, timezone, created_at FROM accounts WHERE id = :account_id"
)
_ACCOUNT_LIST = text(
    "SELECT id, name, industry, timezone, created_at FROM accounts ORDER BY id"
)
_FIRST_OBSERVED = text(
    """
    SELECT location, min(occurred_at) AS first_observed
    FROM activity_events
    WHERE account_id = :account_id AND occurred_at < :before_utc
    GROUP BY location
    ORDER BY location
    """
)
# Local week bucketing: convert the timestamptz to the account's wall clock
# (AT TIME ZONE with a region name handles DST), then truncate to Monday.
_WEEKLY_COUNTS = text(
    """
    SELECT location,
           date_trunc('week', occurred_at AT TIME ZONE CAST(:tz_name AS text))::date AS week_monday,
           count(*)::int AS event_count
    FROM activity_events
    WHERE account_id = :account_id
      AND event_type = :event_type
      AND occurred_at >= :window_start_utc
      AND occurred_at < :window_end_utc
    GROUP BY location, week_monday
    ORDER BY location, week_monday
    """
)
_LAST_OBSERVED = text(
    "SELECT max(occurred_at) AS last_observed FROM activity_events WHERE account_id = :account_id"
)


class SqlReviewRepository:
    def __init__(self, connection: Connection) -> None:
        self._connection = connection

    def get_account(self, account_id: int) -> AccountRecord | None:
        row = self._connection.execute(_ACCOUNT_SELECT, {"account_id": account_id}).mappings().first()
        return AccountRecord(**row) if row is not None else None

    def list_accounts(self) -> list[AccountRecord]:
        rows = self._connection.execute(_ACCOUNT_LIST).mappings().all()
        return [AccountRecord(**row) for row in rows]

    def location_first_observed(
        self, account_id: int, before_utc: datetime
    ) -> dict[str, datetime]:
        result = self._connection.execute(
            _FIRST_OBSERVED, {"account_id": account_id, "before_utc": before_utc}
        )
        return {row.location: row.first_observed for row in result}

    def weekly_counts_by_location(
        self,
        account_id: int,
        event_type: str,
        window_start_utc: datetime,
        window_end_utc: datetime,
        tz_name: str,
    ) -> list[LocationWeekCount]:
        result = self._connection.execute(
            _WEEKLY_COUNTS,
            {
                "account_id": account_id,
                "event_type": event_type,
                "window_start_utc": window_start_utc,
                "window_end_utc": window_end_utc,
                "tz_name": tz_name,
            },
        )
        return [
            LocationWeekCount(row.location, row.week_monday, row.event_count) for row in result
        ]

    def last_observed_event(self, account_id: int) -> datetime | None:
        row = self._connection.execute(_LAST_OBSERVED, {"account_id": account_id}).first()
        return row.last_observed if row is not None else None
