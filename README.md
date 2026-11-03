# Relay — Weekly Activity Review

Implementation of ticket **DASH-247**: help a customer administrator answer,
on Monday morning, *"is this week's activity normal for us?"* — with an
account summary, a sortable location comparison, and an inspectable
8-week historical series. Every number is traceable to a source aggregate;
a change is presented as a reason to look, never as a verdict or a cause.

The original plan is [`PLAN.md`](PLAN.md). Deviations and discoveries live in
[`docs/decisions/`](docs/decisions/); the honest interaction record lives in
[`ai-log/`](ai-log/).

## Ticket interpretation and assumptions

The ticket asks whether recent activity is normal for the same customer and
which location deserves attention on Monday morning. This implementation
answers that with the last complete local Monday–Sunday week, compared with
its eight preceding weeks. Calls, leads and appointments are separate event
counts; none is presented as unique customers or an attributable funnel.

An account's IANA timezone defines its calendar weeks; UTC is the storage
format. The supplied fixture is assumed to cover the documented recording
interval. Missing events inside it are counted as zero, while the interface
states that inactivity and missing collection cannot be distinguished.
Distinct event IDs remain distinct even when their other fields match.

The mean and observed range describe history, not a forecast or confidence
interval. Low volume, zero reference and insufficient history have explicit
states. First recorded activity is not an opening date; changes in the
observed location population suppress an unsupported account-level label.
A fixed trusted demo principal may inspect all fixture accounts; real
production authentication is outside the exercise.

## Key design decisions and trade-offs

| Choice | Why | Trade-off |
| --- | --- | --- |
| FastAPI modular monolith, pure comparison policy and repository boundary | Keeps HTTP, calculation and storage responsibilities clear while deploying one application | A small amount of interface/DTO code; no distributed services or independent scaling |
| PostgreSQL aggregation through SQLAlchemy Core/text queries; Alembic migrations | Reviewable SQL, parameter binding, relational integrity and real database behavior | Requires PostgreSQL locally; query/schema changes need migration and integration checks |
| Eight-week mean plus visible historical range | Simple to explain and additive across a stable location population | Sensitive to historical outliers; thresholds are product heuristics, not statistical certainty |
| Complete local weeks with timezone-aware UTC boundaries | Makes periods comparable and handles daylight-saving changes | Does not provide a partial-current-week comparison |
| URL parameters as frontend filter state | Reload, sharing and back/forward reproduce the view without a state framework | Requires validation/recovery and stale-request protection; TypeScript interfaces remain manually reviewed |
| Separate read-only API role and explicit verified seed command | Limits application writes and makes setup repeatable; reset/import is atomic | Adds role/grant setup; seed provenance is tied to this exact supplied fixture |
| Real PostgreSQL integration tests plus small independent unit fixtures | Checks SQL, transactions, calendar edges and handwritten expected values | Integration tests require a running dedicated database; the pure subset does not |

Details and later discoveries are in [decision records](docs/decisions/).

## Deliberately deferred

- **LLM briefing:** deterministic labels and drilldown already answer the
  core question. Generated prose would add latency, cost, nondeterminism and
  disclosure/validation work for limited benefit; the original plan explains
  a possible bounded integration.
- **Login/RBAC, notifications and forecasting:** excluded by the ticket.
  The trusted demo principal is not a substitute for production access control.
- **Caching, rollups, extra indexes and background infrastructure:** the
  fixture does not establish a need. Query evidence is kept at fixture scale;
  larger measured workloads should drive optimization.
- **Production hosting and cross-platform packaging:** local execution is
  the verified delivery. Managed deployment, backups and a portable container
  setup require their own validation rather than an unsupported readiness claim.

## Stack

- **Backend**: Python 3.12, FastAPI, SQLAlchemy (Core/`text()` SQL), Alembic,
  PostgreSQL 17 (real database for the app *and* for the tests), pytest.
- **Frontend**: React 18 + TypeScript + Vite; URL search params are the
  canonical filter state; Vitest + Testing Library.
- **No LLM, external credentials, or external service at runtime.**

## Quick start (macOS + Homebrew)

Prerequisites: macOS with Homebrew, GNU Make, Python 3.12, PostgreSQL 17,
and Node.js 24 with npm. The checked-in Makefile defaults to Homebrew's
Apple Silicon paths. This is the verified local platform; Linux and Intel
macOS may require binary-path overrides and have not been validated.
Allow ports 5433 (dedicated database), 8000 (API), and 5173 (UI) on loopback.
Package installation needs Internet access; the running feature does not.

```bash
# 0. Install prerequisites if absent
brew install postgresql@17 python@3.12 node@24
export PATH="$(brew --prefix node@24)/bin:$PATH"

# 1. One-time: dedicated local cluster (port 5433, loopback only, data in var/)
make db-init

# 2. Everything else: venv, migrations, verified seed import, locked npm install
make setup

# 3. Run API (127.0.0.1:8000) and UI (localhost:5173, proxies /api)
make backend-dev   # terminal 1
make frontend-dev  # terminal 2
```

Open <http://localhost:5173>. The fixture demo clock is
**2026-07-28 12:00 UTC**; the default review week is **Jul 20–26, 2026** in
each account's own timezone.

### Verify

```bash
make test            # backend + frontend tests + production build
make backend-unit-test # policy/calendar tests; no running database required
make bootstrap-test  # fresh disposable PostgreSQL cluster; no existing DBs changed
make seed            # re-running is a verified no-op
make sync-openapi    # regenerate the frontend contract snapshot (API running)
```

## What the demo shows

- Account picker (20 fixture accounts), complete-week picker, three metrics
  (calls received / leads created / appointments set — counted separately,
  never summed into "customers"), optional location filter.
- Headline: this week vs the 8-week average, observed range, absolute and
  percent change, and a neutral status label.
- Location table ranked: flagged decreases by absolute shortfall, then flagged
  increases, then everything else; sortable by count/change/name; each row
  expands into its 9-week series (weeks outside the assumed recording interval
  are greyed and never averaged).
- All filters live in the URL: reload, back/forward, and shared links
  reproduce the exact view. Account switches clear incompatible location
  filters; invalid URL state recovers with a visible notice.
- Accessibility: semantic table with caption and sort state (`aria-sort`),
  labeled/focusable controls, skip link, visible focus, status text plus
  shape plus color, keyboard-scrollable table region on narrow screens,
  reduced-motion and forced-colors support, and a React error boundary.
- Fixture transparency: demo date, last recorded event, coverage interval, and
  policy version/thresholds are shown in the UI.

A good demo path: account **Pacific Smiles** (5 locations) → expand **Site A** →
filter to **Site A** → switch metric to **Leads created** → account
**Summit Auto Group** for a 6-location comparison → pick a February week to
see the insufficient-history state.

## Architecture (summary)

Layered modular monolith with a strict inward dependency rule
(`PLAN.md` §4): FastAPI routes → `weekly-review` service → pure comparison
policy (no I/O, versioned) and a repository port implemented by a SQLAlchemy
adapter that aggregates in PostgreSQL. The browser never recomputes business
classifications; the server never interpolates request values into SQL.

```text
backend/
  app/api/        routes, DTOs (wire contract), error envelope, request ids
  app/reviews/    service (orchestration), policy.py (pure rules v1),
                  calendar.py (zoneinfo week windows), repository.py (SQL adapter),
                  seed.py (verified importer), ports.py, errors.py
  app/db/         engine factory
  migrations/     Alembic 0001: supplied schema + seed_import marker + index
  tests/          unit / calendar / repository / seed / API / isolation /
                  reconciliation against the real seed
frontend/
  src/features/review/   typed client + committed OpenAPI snapshot, URL state,
                         stale-safe data hook, components
  tests/                 interaction tests (sorting, drilldown, URL, retry)
data (review-input/)    unmodified starter inputs + provenance
docs/decisions/         short decision records
ai-log/                 implementation interaction record
```

## Safety and operational notes

- Distinct DB roles: `relay_app` (API, SELECT-only) vs `relay_admin`
  (migrations/seeding). No superuser for application operations.
- Seed import verifies SHA-256 + byte size against `review-input/provenance.json`,
  loads transactionally, records a marker, and is idempotent; a mismatched or
  non-empty database fails loudly. `--reset` requires an explicit env flag and
  a `relay_*` database name. The seed is checked before clearing anything;
  clearing and reloading share one transaction, so failures preserve the
  previous data. The CLI reads `backend/.env`; process environment values
  override that file, and `--database-url` overrides both.
- All SQL is parameterized; sort keys are not interpolated; account scope is
  mandatory in every repository method (tested with sibling accounts sharing
  location names and a restricted principal).
- Timestamps are `timestamptz`; the source's documented-UTC interpretation is
  applied at import time and covered by a non-UTC-session test. Week
  boundaries are built with `zoneinfo` per account timezone (DST-safe in both
  Python and the SQL bucketing, tested across spring/fall transitions).
- Loopback only; no CORS reliance; error bodies carry a request id and no
  stack traces; `.env` is gitignored, `.env.example` holds safe samples.

## Known limitations (deliberate)

- No authentication: single trusted demo principal, explicitly out of scope
  per the plan; this is not a production authorization model.
- Thresholds (≥5 events and ≥20% beyond the range edge) are product heuristics
  (policy v1), disclosed in the UI response, not statistical confidence.
- Coverage interval `2026-02-01 … 2026-07-28 UTC` is a documented assumption;
  zero-filled weeks cannot distinguish "no activity" from "not recorded", and
  the UI says so. A location's first recorded activity is not an opening date.
- Performance evidence (`docs/performance-observations.txt`) is fixture-scale
  only; no production scalability claim is made from 12.6k rows.
- The optional LLM briefing layer was evaluated and **deferred** with evidence
  (see `docs/decisions/0007-llm-deferred.md`).

## Verification and walkthrough

See [validation evidence](docs/VALIDATION.md) for measured checks and their
limits, and the [demo walkthrough](docs/DEMO.md) for a short reproducible
review path. Stop the development servers with Ctrl-C; `make db-down`
stops the dedicated database without deleting its data. Restart it with
`make db-up` before returning to development or running integration tests.

## With another day

Confirm the coverage/ingestion contract with Product so a missing event can
be distinguished from missing collection, and clarify location lifecycle
data before inferring openings or closures. Add an automated real-browser
smoke test for the documented walkthrough and a portable container-based
setup after validating it on another OS. Benchmark representative larger
workloads before adding indexes, caching or pre-aggregation. Production
hosting would require real authentication/tenant authorization and a
separately reviewed migration and backup process.
