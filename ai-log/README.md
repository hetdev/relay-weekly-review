# ai-log — DASH-247 implementation record

This directory records how the implementation was actually produced with AI
assistance, including corrections and rejections — not a cleaned-up one-shot
story. Summaries are labeled as summaries; no unrelated conversations,
personal files, or credentials are included.

## Session of 2026-11-03 (the implementation session)

**Model/tool**: ZCode (agent) driven by GLM-5.3, planning-model-assisted
plan.md authored earlier the same day in the same session. The user directed:
review the plan for SOLID/patterns/KISS/scalability (plan §4 was extended
accordingly, in English), then "implementa el plan".

**Genuine corrections the agent had to make** (each verified by a failing
test or visible defect first, then fixed; none are invented):

1. Seed parser double-unquoted already-unquoted regex groups → every location
   stored as `"ite "` and names truncated. Caught by smoke-testing the API
   against the seeded database; fixed; covered by regression checks.
2. `first_observed = first_observed.get(location)` shadowed the dict inside
   the location loop and crashed the account rollup (`TypeError`). Caught by
   the smoke test; fixed by renaming.
3. `locations` in the response was not filtered when a location filter was
   active. Caught by an API contract test; fixed in the service.
4. Frontend Monday validation used the browser's local timezone
   (`new Date("2026-07-20").getDay()`), rejecting valid Mondays west of UTC;
   caught by the URL round-trip test. Fixed with UTC-pinned parsing.
5. Frontend week labels used `Intl.DateTimeFormat` without `timeZone: "UTC"`,
   shifting labels by a day in non-UTC environments; caught by the render
   test. Fixed the same way.
6. Test-fixture and expectation errors the *code* was right about (recorded
   because reviewing agent output cuts both ways): synthetic data lacked
   pre-baseline anchor events (policy correctly said `insufficient_history`),
   Sunday-belongs-to-previous-week bucketing intuitions, an EST-offset
   literal, a Monday-count arithmetic slip, and two overly-broad mock fetch
   routes in tests.
7. Environment notes: `pytest -W error::DeprecationWarning` failed on
   third-party (anyio/starlette) deprecations → scoped to `app.*`/`tests.*`;
   `ALTER DEFAULT PRIVILEGES` is per-database, so grants moved into the test
   fixtures; npm blocked esbuild's postinstall (approved explicitly).

**What the agent did not do**: invent metrics beyond the ticket, add
auth/notifications/forecasting (explicit exclusions), tune thresholds against
the seed, or pre-build speculative infrastructure (caching, replicas,
pre-aggregation). The LLM briefing layer was evaluated and deferred
(docs/decisions/0007-llm-deferred.md) — the plan permits deferral with
evidence, and this log is that evidence.

**Verification trail**: 103 backend tests + 20 frontend tests + production
build, all green; seed reconciliation literals derived via direct SQL; browser
verification (render, filters, URL persistence, back/forward, drilldown) with
a screenshot; EXPLAIN (ANALYZE, BUFFERS) evidence in
docs/performance-observations.txt.

## Redactions

None required: no credentials, personal files, or unrelated conversations
were part of this task's context.
