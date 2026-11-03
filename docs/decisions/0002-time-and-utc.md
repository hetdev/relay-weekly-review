# 0002 — Weeks, timezones, and the UTC interpretation of source timestamps

Date: 2026-11-03 · Status: implemented as planned (plan.md §5–6)

## Decision

- A week is Monday 00:00 → next Monday 00:00 **local** (account's IANA
  timezone), half-open. Boundaries are constructed with `zoneinfo` per local
  midnight and converted to UTC instants; never by subtracting 168-hour spans.
- SQL bucketing mirrors this: `date_trunc('week', occurred_at AT TIME ZONE
  <tz>)` — the same wall-clock semantics, DST-safe, aggregated in PostgreSQL.
- Source `TIMESTAMP`s (no offset, documented UTC) become `timestamptz`; the
  UTC interpretation is applied **in the importer** by parsing into aware
  datetimes, independent of session/machine timezone. A test pins the session
  to Asia/Tokyo and asserts the stored instants.

## Evidence

`tests/test_calendar.py` (UTC / Phoenix / New_York, spring-forward 167h and
fall-back 169h weeks, month/year boundaries, Monday validation),
`tests/test_repository_integration.py` (bucketing across both 2026 DST
transitions, half-open window endpoints), `tests/test_seed.py`
(non-UTC session read-back).

## Consequence

An uncovered nuance found while testing: weeks **start** Monday, so Sunday
belongs to the *previous* week — first intuition during test-writing had it
backwards; the implementation was right and the test literals were corrected.
Recorded here because it is exactly the class of mistake this decision exists
to prevent.
