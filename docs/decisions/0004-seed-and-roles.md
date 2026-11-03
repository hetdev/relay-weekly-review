# 0004 — Seed import: verified, transactional, idempotent; least-privilege roles

Date: 2026-11-03 · Status: implemented as planned (plan.md §5)

## Decision

- The importer (`app/reviews/seed.py`, an explicit CLI — never an API startup
  side effect) verifies the file's SHA-256 **and** byte size against
  `review-input/provenance.json` before parsing; parsing is strict
  line-regex matching (the file is data; it is never executed); row counts
  must be exactly 20 accounts / 12,626 events.
- Loading is one transaction: accounts → events → `seed_import` marker →
  post-conditions (counts + FK integrity) inside the same transaction.
- Rerun semantics: matching marker + valid counts/integrity = verified no-op;
  anything else = hard failure. Rows are never silently overwritten.
  `--reset` requires `RELAY_ALLOW_RESET=1` and a `relay_*` database name.
- Two database roles: `relay_admin` (migrate/seed) and `relay_app`
  (API, SELECT-only via `scripts/sql/grants.sql`). Tests run the API through
  `relay_app`, so a privilege escalation would fail CI.

## Deviations / discoveries

- First parser version double-unquoted already-unquoted regex groups,
  silently storing `"Site B"` as `"ite "` — caught by eyeballing the smoke
  test, fixed, and covered by regression assertions on names/locations in
  `tests/test_seed.py` (nullability round-trip plus distinct-location checks).
  The tamper/no-op/marker-mismatch paths are all tested.
