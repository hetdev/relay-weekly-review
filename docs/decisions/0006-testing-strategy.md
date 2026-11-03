# 0006 — Testing: hand-calculated expectations against a real PostgreSQL

Date: 2026-11-03 · Status: implemented as planned (plan.md §10)

## Decision

Every layer has a dedicated evidence type, and expected values are
hand-calculated (or computed by direct SQL independent of the service) —
never by calling the implementation under test:

| Suite | What it proves |
| --- | --- |
| `test_policy.py` | Exact arithmetic, threshold boundaries (5/4 events, exactly 20%), rule order, nullability, ranking determinism |
| `test_calendar.py` | zoneinfo week windows; DST spring (167h) / fall (169h) weeks; UTC/Phoenix/New_York; strict parsing; coverage logic |
| `test_repository_integration.py` | SQL bucketing across both 2026 DST transitions, half-open windows, duplicate ids, nullables, quoted strings, FK enforcement, account scoping, no future-location leaks |
| `test_seed.py` | sha256/size verification, transactional import, idempotent rerun, tamper resistance, marker mismatch, non-UTC session read-back |
| `test_api.py` | Contract shape, every classification reason, population-change suppression, ranking, filters, error envelope + request ids, restricted principal, sibling-account isolation with shared location names |
| `test_reconciliation.py` | Stored literals hand-derived via direct SQL from the fixed seed (account 5: 24,18,19,23,20,13,36,26 → ref 22.375; target 19 = 4+2+7+2+4) plus a full SQL-vs-API sweep |
| frontend `tests/` | URL encode/parse round-trips + invalid recovery, stale-response protection, sorting/`aria-sort`, drilldown, error retry, empty state, OpenAPI contract guard |

The API tests run through the read-only role; migration/seeding tests use the
admin role — least privilege is itself under test.

## Where the tests earned their keep

Real bugs caught before delivery: seed double-unquoting (`"ite "`), a
`first_observed` variable shadowing that crashed the account rollup, missing
location-row filtering under a location filter, both frontend timezone bugs,
and three wrong hand-calculations of mine (Sunday-belonging weeks, EST offset,
Monday count) that the code was right about.
