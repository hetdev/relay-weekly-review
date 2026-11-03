# Relay — Weekly Activity Review

Status: pre-implementation plan. Written on November 3, 2026, before application implementation.

This document records the initial design and assumptions. Subsequent discoveries and deviations will be recorded separately in decision notes and the README; this plan will not be rewritten to imply that those discoveries were known in advance.

## 1. Product outcome

A customer administrator reviewing the dashboard on Monday should be able to answer:

1. How did last week's activity compare with our own recent history?
2. Which locations changed enough to deserve investigation?
3. Which numbers and historical periods support that conclusion?

Build a weekly review with an account summary, a sortable location comparison, and an inspectable historical series. Each conclusion must be traceable to source aggregates. A change in activity is a reason to investigate, not evidence of its cause or of business success/failure.

The main workflow must work without an LLM, external credentials, or an external service at runtime. Work will proceed by acceptance gates rather than fixed implementation durations; adding features is conditional on correctness and clarity of the existing workflow.

## 2. Scope

### Core delivery

- Python API performing real PostgreSQL aggregation over the supplied data.
- React/TypeScript dashboard, with account context, complete-week selection, event metric selection, and optional location filtering.
- Three separately counted metrics using one aggregation path: calls received, leads created, and appointments set. Calls are the default. Never sum these into a count of unique customers or assume an attributable conversion funnel.
- Comparison with the preceding eight complete weeks for the same account, location, and metric.
- Explicit states for no activity, missing history, low volume, and zero reference values.
- URL-persisted filters, inspectable comparison rules, and accessible loading/error/empty states.
- Versioned migrations, a reproducible seed import, meaningful automated tests, and documented local setup.
- An honest implementation log and reviewable technical decisions.

### Deliberate exclusions

Authentication/login, notifications, forecasts, arbitrary report builders, background job infrastructure, customer-specific thresholds, live third-party data synchronization, and a production deployment are outside the initial feature. Authentication is omitted under the trusted-admin exercise assumption; this is not a production authorization model.

Do not introduce a location hierarchy, graph database, message broker, vector store, microservices, or Kubernetes without a concrete need in the implemented workflow.

## 3. Questions and working assumptions

| Question | Working assumption and consequence |
| --- | --- |
| What does a week mean? | Monday 00:00 to the following Monday 00:00 in the account's IANA timezone. Use half-open intervals. |
| What is recent activity? | The last completed local calendar week, with earlier complete weeks selectable. Never compare a partial week with full weeks. |
| What does normal mean? | A transparent descriptive comparison with the account/location's own recent weekly history. No statistical significance or forecast is claimed. |
| Is more activity necessarily better? | No. Use neutral labels such as above/below recent range. Do not assign a cause or recommend personnel decisions. |
| Does a missing row mean zero? | For the static fixture, assume recording coverage inside a documented observation interval. Zero-fill weeks under that assumption. Show the limitation; missing records cannot distinguish inactivity from an ingestion outage. |
| When did each location open? | Unknown. First observed activity is not an opening date. Before enough observed history exists, suppress classification rather than silently manufacture a full baseline. |
| Are identical event attributes duplicates? | Distinct event IDs remain distinct records. Do not deduplicate by timestamp or payload without a business key. |
| Are outcomes and durations always valid? | Preserve nullable and unusual source values. The core feature counts event IDs and does not depend on duration or outcome. |
| Who can see each account? | A fixed trusted demo administrator is explicitly allowed to inspect the fixture accounts. Account switching is demo behavior; every query still requires an explicit account scope. |
| What date should the fixture show? | Use an explicit, documented demo clock so the historical fixture remains useful and reproducible. Never imply that July data is current live data. |

If an assumption proves incorrect, preserve the original decision here, add a dated decision note, update affected tests, and explain the resulting behavior.

## 4. Technology and architecture

Use **Python + FastAPI + PostgreSQL**, with **SQLAlchemy and Alembic** for persistence and migrations, and **React + TypeScript + Vite** for the UI. Pin supported versions after checking official package sources, compatibility, installation behavior, and security advisories; do not use floating `latest` tags.

FastAPI provides a typed HTTP contract and OpenAPI documentation. PostgreSQL provides explicit timestamp semantics, relational constraints, and inspectable query plans. SQLAlchemy manages connections and parameter binding; aggregation may use readable SQL/Core expressions rather than loading events into Python. Alembic keeps schema changes reviewable. React holds presentation state; URL search parameters are the canonical shareable filter state. Avoid a global state framework until the application needs one.

Use a **modular monolith** with a strict inward dependency rule. Layers communicate through explicit contracts, and inner layers never import outer ones:

```text
presentation   React view -> typed API client -> FastAPI route
                     |  typed DTOs; OpenAPI generated from the same models
application    weekly-review service (account scope, time windows, assembly)
                     |  plain calls; depends on ports only
domain         pure comparison policy (no I/O, versioned rules)
persistence    repository port -> SQLAlchemy adapter -> PostgreSQL
```

The only allowed dependencies are presentation -> application -> domain, plus application -> persistence port. The domain layer imports nothing: no framework, no ORM, no HTTP constructs. All wiring happens once in a composition root at startup.

Routes validate requests and translate errors. The service resolves account context and time boundaries, assembles aggregates, and applies comparison rules. Repository functions require account scope and return aggregate DTOs (week counts), never ORM objects or event rows; this keeps account scoping enforceable in one place. The comparison policy is pure and independently testable. The browser never recomputes business classifications.

### Architectural patterns

Each pattern is adopted for a concrete need in this workflow, not for compliance:

- **Layered modular monolith** (over microservices): one deployable and one database give transactional consistency for free; module boundaries are chosen so extraction stays possible if a concrete need ever appears.
- **Repository (port/adapter)**: the service depends on a repository interface that returns aggregate DTOs. PostgreSQL is an adapter behind that interface. This is what makes the service testable without a database.
- **Policy/strategy, versioned**: classification v1 is a pure function of the target count, the eight baseline counts, and the thresholds. The policy version is part of the API response; a future policy is a new registered version, not an in-place edit that consumers must detect.
- **Adapter with stub default** (LLM summary, if built): a provider-neutral port where the deterministic stub is a full implementation of the same contract, so the optional feature degrades to it on outage.
- **DTO/contract-first**: the Pydantic API models are the single source of truth for the wire contract; the TypeScript client is typed against the generated OpenAPI schema, so client and server cannot silently diverge.
- **Composition root with constructor injection**: dependencies are injected at one startup location. No global singletons, no service locator, no hidden imports of concrete infrastructure inside business logic.

### SOLID, as applied here

A principle counts as satisfied only when a concrete decision implements it:

| Principle | Decision that satisfies it |
| --- | --- |
| Single responsibility | One reason to change per module: routes change with the HTTP contract, the service with orchestration, the repository with SQL/schema, the policy with product thresholds. |
| Open/closed | New metrics or sort keys arrive as new enum values; a comparison policy v2 is registered alongside v1. Consumers read a `policy_version` field instead of diffing behavior. |
| Liskov substitution | The repository contract is explicit — mandatory account scope, zero-filled weeks, aggregate DTOs only — so any substitute (test double, future read replica) must honor it or fail its tests. |
| Interface segregation | Small role-specific ports (`ReviewRepository`, optional `SummaryProvider`) instead of one god interface; routes see only the service, never a repository. |
| Dependency inversion | Service and policy depend on abstractions owned by the application/domain layer; SQLAlchemy, FastAPI, and any LLM SDK are outer details injected at startup. |

### KISS, as applied here

- One aggregation path for all three metrics (already non-negotiable in section 2); no per-metric code branches.
- SQL-first aggregation: PostgreSQL counts, Python applies comparison rules. No event rows cross into application memory.
- No state-management framework while URL plus server state suffice.
- No abstraction with only one real implementation and no second one foreseen; the LLM port is the deliberate exception, justified by isolation and outage testing.
- Prefer deferring a feature (section 9) over shipping a configuration option for it.

### Scalability posture

State what scales now, what the levers are, and what would trigger them; build none of them speculatively:

- The API is stateless (the URL is the filter state; no server-side sessions), so replicas can run horizontally behind one origin and any replica can serve any request.
- One bounded aggregation query per review request, never one query per location; the response size is bounded by the account's location count.
- Database connections go through a configured pool per process; the pool size is documented with the setup.
- The composite index in section 5 is the first scaling step; further indexes only on measured query-plan evidence.
- Documented levers with trigger conditions, not implementations: a weekly pre-aggregation table (trigger: on-demand aggregation exceeds the response budget at real volume), read replicas or HTTP caching (trigger: read traffic), response caching keyed by account/week/metric/location/policy version/data revision. None is justified at fixture scale, and section 10 already forbids inferring production scalability from 12.6k rows.

Suggested layout:

```text
backend/
  app/api/             # request/response models and routes
  app/reviews/         # service, pure comparison policy, repository port + SQL adapter
  app/db/              # connection/session configuration
  migrations/          # Alembic revisions
  tests/               # unit and real-PostgreSQL integration tests
frontend/
  src/features/review/ # view, query state, typed API client
  tests/               # interaction and end-to-end tests
data/                  # exact reviewed seed and provenance/checksums
docs/decisions/        # consequential decisions and later deviations
ai-log/                # task-specific interaction record
PLAN.md
README.md
```

## 5. Data model and safe loading

Preserve the supplied account/event identities and all source rows. Retain the two domain tables rather than inventing unsupported location metadata. Derive known locations from events at or before the selected review period; a historical review must not reveal locations first observed in its future.

1. Translate the schema into an initial Alembic revision with PK, FK, and required-field semantics preserved.
2. Store timestamps as PostgreSQL `timestamptz`. The source timestamps have no offset but are documented as UTC: make that interpretation explicit during import, independent of the machine/session timezone. Validate this with a non-UTC session test.
3. Profile source domains before adding further constraints. Do not reject provided records merely because an example comment omits an observed outcome. Unknown outcomes must not break event counts.
4. Use a separate seed command, not a hidden API startup side effect. Verify the reviewed seed hash, load transactionally, and verify 20 accounts and 12,626 events plus foreign-key integrity.
5. Make reruns predictable: a matching import marker plus valid counts/integrity means a no-op; nonempty inconsistent data or a different hash means a clear failure. Never silently overwrite rows or reset an existing database. A reset must be an explicit command restricted to the disposable demo database.
6. Keep import provenance in a small operational record: source revision, seed digest, import time and fixture observation assumptions. This is not fabricated activity data.
7. Use distinct migration/import and read-only API roles. The API cannot create tables, modify events, or import arbitrary files. Do not use a database superuser for application operations.

Start with an index on `(account_id, event_type, occurred_at)` and inspect actual query plans. Add a location-oriented index only if the measured access path needs it. Document read benefit, index size, and write cost instead of adding overlapping indexes speculatively.

For an existing production table, adding indexes and changing timestamp representations would require a separately planned migration: explicit UTC interpretation, bounded backfill where necessary, lock/statement timeouts, validation, and a compatible application rollout. The empty-demo initialization does not demonstrate a zero-downtime production migration.

## 6. Time and comparison contract

### Observation and clock

Record fixture coverage assumptions separately from the minimum and maximum observed event timestamps. A last event timestamp is a freshness signal, not proof that ingestion completed.

Proposed fixture configuration: an assumed recording interval beginning `2026-02-01T00:00:00Z` and ending `2026-07-28T00:00:00Z`, and a demo clock of `2026-07-28T12:00:00Z`. Verify these against the import profile. The default completed week is July 20–26 in the fixture timezones. Surface the demo date, selected local interval, timezone, and last observed event in the UI. Coverage boundaries are documented assumptions, not inferred service guarantees.

Construct each local Monday boundary with Python's `zoneinfo`, then convert it to an aware UTC instant. Do not construct calendar weeks by subtracting fixed 168-hour durations in UTC; daylight-saving transitions can change their elapsed length.

Reject malformed dates, non-Monday week starts, future/incomplete weeks, and windows outside supported fixture coverage. Valid early weeks may be displayed with insufficient baseline history.

### Aggregation and baseline

Let `c` be the event count for the selected complete week and `w1 ... w8` the counts for its eight preceding complete weeks. The target week is excluded from its own baseline.

```text
reference = (w1 + ... + w8) / 8
delta = c - reference
percent_change = 100 * delta / reference, if reference > 0
observed_range = [min(w1 ... w8), max(w1 ... w8)]
```

Eight weeks provide more context than one prior week while keeping the calculation easy to explain. The mean has a useful additive property: with the same population/window, location references sum to the account reference. It remains sensitive to unusual historical weeks, so show the individual weeks and observed range. The range is descriptive, not a prediction interval.

Build zero-filled week buckets using calendar boundaries and known locations, then left-join grouped event counts. Do not calculate averages only over weeks that happen to contain events. Aggregate in PostgreSQL, keep comparisons unrounded, and round only for display. Global percentage changes come from global counts, never an average of location percentages.

For filtered views, the headline explicitly refers to the selected population. The full-account rollup is computed from all account events; it must not silently exclude locations with insufficient history. If new locations make the comparison population unstable, return a population-change warning and suppress a misleading overall classification while still showing totals.

### Classification policy v1

Apply these rules in order and return both a machine-readable reason and its inputs:

1. Account with no observed events: `no_activity_recorded`; no meaningful percentage or classification.
2. Fewer than eight covered preceding weeks, or a location first observed after the baseline begins: `insufficient_history`. Available weekly counts remain visible; no partial-history value is presented as the full baseline.
3. Full baseline with zero events: `no_recent_activity` if `c = 0`, otherwise `activity_after_zero_baseline`. Percentage is `null`, never infinity.
4. Reference below five events/week: `low_volume`. Show counts and arithmetic where defined, but do not label a percentage swing as unusual.
5. `below_recent_range` if `c < min(w)`, the drop is at least five events, and the relative drop is at least 20%.
6. `above_recent_range` if `c > max(w)`, the increase is at least five events, and the relative increase is at least 20%.
7. Otherwise `no_review_flag`; explain that this means the explicit review thresholds were not met, not that the business is healthy or the result statistically normal.

The five-event and 20% thresholds are initial product heuristics, not fitted statistical confidence. Keep them centralized and versioned, disclose them, and examine examples before finalizing. Do not tune them to produce a visually impressive answer on the seed.

Rank flagged decreases by absolute shortfall, followed by flagged increases and then other states, with deterministic ties. Allow sorting by count and change. Keep insufficient-history states visible rather than assigning them a healthy green status.

## 7. API and error contract

Proposed endpoints:

- `GET /api/v1/accounts`: only accounts permitted by the explicit demo principal.
- `GET /api/v1/accounts/{account_id}/review-options`: timezone, known locations, supported complete weeks, fixture/freshness metadata.
- `GET /api/v1/accounts/{account_id}/weekly-review?week_start=YYYY-MM-DD&metric=call_received&location=Site%20A`: optional location filter; server-owned baseline length and policy version.
- Separate liveness and database-readiness checks that expose no configuration or secrets.

The review response includes request scope; local and UTC boundaries; baseline window; comparison policy/version; freshness/coverage warnings; account/filtered totals; per-location weekly counts, reference, range, absolute/percentage changes and reason; and a stable request ID. Use explicit `null` values for unavailable quantities, not fabricated zeros.

Validate account IDs, metric enums, date bounds, string lengths, and location membership. All SQL values are parameterized; sort keys, where supported, come from a fixed allowlist. Do not interpolate SQL identifiers from requests. Keep account scope in metadata, history, totals, and detail queries, including sibling queries that might otherwise omit it.

Use consistent errors for invalid input, unknown account/location and unavailable storage. Internal errors return a safe message and request ID; detailed traces remain in development/server logs. Fetch cancellation or stale-response protection prevents a slow old request from replacing a newer filter selection. Bound query windows and result sizes; avoid one database query per location.

## 8. Dashboard interaction

The initial screen shows the selected complete week, timezone and metric, total activity against its reference, and a location table with current count, reference, observed range, delta and reason. Users can expand a location to inspect the target plus eight baseline weeks.

The date/metric/location state lives in the URL so reload, back/forward and sharing reproduce the same view. Account changes clear incompatible location filters. Invalid URL state produces a clear recovery path. The server remains authoritative for calculation and validation.

Use semantic tables, keyboard-accessible controls, visible focus, text in addition to color, sensible numeric alignment, and a useful narrow-screen layout. A chart may complement the table but must not hide the underlying values. Provide distinct states for loading, no events, no matching location, insufficient history, API error and retry. Escape all source-derived labels; do not render raw HTML or model-supplied Markdown.

## 9. Where would an LLM fit?

The comparison itself is deterministic. An LLM could help summarize several already-verified location changes into a short weekly briefing, but cannot establish their cause, calculate the numbers, decide access, or replace missing data.

Start with a deterministic summary. After the core acceptance gates pass, evaluate whether an optional language layer improves clarity enough to justify nondeterminism, latency, cost, and information disclosure. It is acceptable to defer it with evidence.

If implemented, use an isolated provider-neutral adapter with a default stub and committed real prompts. Send only necessary aggregate facts and opaque location/fact IDs, not raw events, credentials, or unrestricted database access. Treat source labels and provider output as untrusted text.

Prefer a bounded structured response selecting supported fact IDs and approved explanation categories. Validate schema, ID membership, size and allowed claims; render numeric statements from trusted server facts. Arbitrary fluent text cannot be made factual merely by validating JSON, so unsupported claims must be rejected or replaced with the deterministic explanation.

Use a strict timeout, bounded output, explicit failure behavior and optional caching by account scope, period, metric, data revision, prompt/model version and filters. Record actual latency/usage where provided. Test malformed responses, invented IDs, instructions embedded in labels, outages and timeouts. The normal dashboard must remain usable throughout. No model integration is required for local startup.

## 10. Verification strategy

Use small, hand-calculated synthetic fixtures in tests, separate from the unmodified supplied demonstration dataset. Avoid deriving expected values by calling the same calculation implementation under test.

| Layer | Evidence required |
| --- | --- |
| Comparison unit tests | Exact totals, mean, range and deltas; threshold boundaries; low volume; all-zero reference; positive activity after zero; insufficient history; deterministic ordering; no NaN/infinity. |
| Calendar tests | Local midnight boundaries, DST spring/fall transitions, UTC and Phoenix, month/year boundaries, exclusion of target/future events from baseline, and Monday interpretation. |
| PostgreSQL integration | Real migration/schema behavior, FK enforcement, parameter binding, UTC import under a non-UTC session, zero-filled buckets, duplicate payloads with distinct IDs, nullable fields, seed rerun/failure behavior and transaction rollback. |
| Account isolation | Same location names in two accounts; every totals/history/options/detail query returns only the requested permitted account; unauthorized account rejected using a restricted test principal. |
| API contract | Valid responses and nullability; invalid input, SQL-like values, unknown locations, bounded windows, database failures and safe error bodies. |
| Frontend/E2E | Reload and back/forward preserve filters; account switch clears invalid location; out-of-order requests cannot overwrite current state; empty/error/retry behavior and keyboard access. |
| Seed reconciliation | Assert row counts and FK integrity; independently calculate selected account/location/week examples from the fixed seed, store expectations with their calculation notes, and reconcile totals. |
| Performance | Save representative SQL and actual EXPLAIN (ANALYZE, BUFFERS) observations for one-location and 15-location accounts. Record environment, timings and query count; do not infer production scalability from 12.6k rows. |

Keep the performance work evidence-driven. A sequential scan on this small fixture is not automatically a problem. If larger-scale behavior needs assessment, use a separately identified synthetic performance fixture, never replace or extend the submitted demonstration seed or present synthetic results as source data.

## 11. Operational and dependency boundaries

- Use a dedicated project environment and database. Do not inherit unrelated project credentials or mount a user's home directory or Docker socket.
- Review package identities, versions, transitive dependencies and installation scripts before execution. Commit lockfiles and checksum/provenance metadata; a clean vulnerability scan is useful evidence, not a malware guarantee.
- Restrict the local application to loopback. If using Compose, pin trusted images, publish only necessary ports to `127.0.0.1`, avoid privileged containers, and keep the database on a private internal network by default.
- Provide `.env.example` containing only safe sample values. Exclude secrets, local databases, caches and personal logs from version control. No frontend secrets.
- For a deployed demo, serve frontend/API from one origin and restrict allowed origins/hosts. Do not rely on CORS as authentication. Public hosting requires a separate access-control decision and is outside this plan's local-delivery scope.
- Use request IDs, structured logs and timing fields without logging credentials, raw records or provider prompts by default. Ensure failure diagnostics are useful and response bodies do not expose stack traces.
- Document a possible stateless API plus managed PostgreSQL deployment, readiness checks, secret management, backup/restore and one controlled migration job. These are design notes, not claims of an AWS deployment or operational readiness. Build infrastructure only when there is a concrete deployment requirement.

## 12. Implementation sequence and exit criteria

1. **Record the starting contract.** Commit this plan and task-specific agent instructions before application code. Start the interaction log and capture the important assumptions and comparison examples. Exit: the planned user workflow, inputs, outputs and edge cases are unambiguous.
2. **Establish persistence.** Set up the reviewed dependencies, database roles, migrations and seed command. Exit: a fresh dedicated database loads exactly; a repeat is safe; failure rolls back; UTC and integrity checks pass.
3. **Implement the calculation.** Build time-window functions, SQL aggregation and the pure comparison policy. Exit: hand-calculated tests and real-PostgreSQL integration tests pass, including tenant/location siblings and zero-filled history.
4. **Expose the contract.** Add the API models, bounded input validation, options endpoint, safe errors and request IDs. Exit: API integration tests and an independent reconciliation against the source fixture pass.
5. **Deliver the user workflow.** Build the dashboard, URL persistence, drilldown and accessible states. Exit: the main review flow is usable and tested through reload/back-forward and failures.
6. **Review correctness and performance.** Inspect diffs, migration effects and query plans; challenge assumptions and agent output. Exit: remaining limitations are explicit, security checks pass, no unsupported interpretation appears in the UI, and all material findings are resolved or clearly documented.
7. **Evaluate optional explanation.** Compare a deterministic briefing against an isolated stubbed LLM adapter. Ship the latter only if its purpose, validation, fallback and tests are convincing; otherwise document the deferral.
8. **Reproduce and package.** Run documented setup from an empty directory/database using only declared prerequisites. Exit: README steps work, tests/build succeed, logs contain no secrets, and the demo can be reproduced without a live model key.

## 13. Agent working discipline and delivery

Give agents bounded tasks with explicit contracts and expected checks. Review generated SQL, migrations, timezone conversions, account scoping and error handling directly. Use independent expectations to challenge plausible-looking output. Record genuine acceptance, rejection or redirection with reasons; do not manufacture mistakes or rewrite the log as a clean one-shot story.

Keep real prompts/responses where export is available and identify tools/models and their actual roles. Label summaries as summaries and any secret redactions explicitly. Include task-specific context artifacts used during implementation. Never include unrelated conversations, personal files, credentials or global configuration in a public interaction log.

The final repository should contain implementation, migrations, the unmodified seed/provenance, this original plan, README, meaningful tests, task-specific agent context and the interaction record. The README will distinguish implemented behavior, assumptions, known limitations and next steps. A compact decision record should explain consequential choices rather than narrate every edit.

Prepare a short reproducible demo: a 15-location comparison, one flagged change with its supporting weeks, a sparse/no-history case, the empty account, and persistence after reload. Each number shown must have a traceable calculation. The application is ready for delivery when the complete workflow is correct, understandable and reproducible—not when an optional feature list is exhausted.
