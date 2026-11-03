"""Ports (interfaces) the application layer depends on.

The service sees aggregate DTOs only — never ORM objects, SQL strings, or
event rows. Every method requires an explicit account scope; there is no
account-optional variant on purpose.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol


@dataclass(frozen=True)
class AccountRecord:
    id: int
    name: str
    industry: str
    timezone: str
    created_at: datetime


@dataclass(frozen=True)
class LocationWeekCount:
    location: str
    week_monday: date  # Monday of the local calendar week (account timezone)
    event_count: int


class ReviewRepository(Protocol):
    def get_account(self, account_id: int) -> AccountRecord | None: ...

    def list_accounts(self) -> list[AccountRecord]: ...

    def location_first_observed(
        self, account_id: int, before_utc: datetime
    ) -> dict[str, datetime]:
        """location -> earliest occurred_at strictly before before_utc.

        Keys are exactly the locations known as of before_utc, so a
        historical review never reveals locations first observed in its
        future.
        """
        ...

    def weekly_counts_by_location(
        self,
        account_id: int,
        event_type: str,
        window_start_utc: datetime,
        window_end_utc: datetime,
        tz_name: str,
    ) -> list[LocationWeekCount]:
        """Grouped counts per (location, local week Monday) over the
        half-open UTC window, aggregated in PostgreSQL."""
        ...

    def last_observed_event(self, account_id: int) -> datetime | None: ...
