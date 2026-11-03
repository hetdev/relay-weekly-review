"""Domain errors raised by the application layer.

The API layer maps these onto the HTTP error envelope; application code never
imports FastAPI.
"""

from __future__ import annotations


class ReviewError(Exception):
    code = "review_error"
    message = "Unexpected review error"

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.message)
        if message:
            self.message = message


class AccountNotFound(ReviewError):
    code = "account_not_found"
    message = "Account not found or not permitted for this principal"


class InvalidWeek(ReviewError):
    code = "invalid_week"
    message = "Requested week is not a supported complete week"


class UnknownLocation(ReviewError):
    code = "unknown_location"
    message = "Requested location is not known for this account"


class DataQualityError(ReviewError):
    code = "data_quality"
    message = "Stored data failed a consistency expectation"
