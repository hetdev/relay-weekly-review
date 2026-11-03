# ai-log — DASH-247 implementation record

This directory records how the implementation was actually produced with AI
assistance, including corrections and rejections — not a cleaned-up one-shot
story. Summaries are labeled as summaries; no unrelated conversations,
personal files, or credentials are included.

## Reading this record

- [Actual implementation transcript](raw/implementation.jsonl): 210
  chronological visible user/assistant records, including tool inputs and
  outputs, exported from the project-specific ZCode session. The first user
  request reviews the plan; the later `implementa el plan` request begins
  implementation. This records the plan-before-code sequence.
- [Planning and review dialogue](raw/planning-and-review.jsonl): actual
  visible dialogue from the Codex planning/review session. Tool outputs are
  represented by the narrower correction logs below rather than a global
  runtime dump.
- [Export notes](raw/export-notes.json): scope, omitted record categories
  and explicit privacy transformations. Neither transcript includes hidden
  reasoning, system instructions, account configuration or unrelated tasks.
- [Review fixes](2026-11-03-review-fixes.md) and
  [unit-test audit](2026-11-03-unit-test-review.md): summaries, exact prompt
  excerpts, decisions and measured verification from the correction sessions.

The implementation history below remains a summary written during those
sessions. Later availability of the original transcript does not change
what was available when the earlier review notes were written.

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

## Code review pass (same day, after delivery)

A deliberate fresh-eyes review of the delivered code found and fixed:

- **Frontend (behavior)**: recovery from URL values that *parse* but are
  unknown to the account (e.g. `?account=999&location=Site+Z`) healed the
  view but never rewrote the URL — reload/shared links would repeat the
  broken state. Fixed with `replaceState` of the recovered filters; covered
  by a new regression test ("rewrites the URL when filters parse fine but
  are unknown").
- **Backend (quality)**: dead symbols removed (`BASELINE_WEEKS`/`TIME` in
  the service, `ReviewServiceDep`/`build_engine` in deps, `REVIEW_TARGET`
  in conftest, an unused import in test_api); `__import__` hacks in the
  reconciliation test replaced with real imports; the internal-error
  handler now logs through `logging` with the traceback instead of `print`.

Noted and deliberately left (documented, low value to change now): table
sort is ascending-only (no `aria-sort="descending"` cycle), `cssSafe` ids
could collide for adversarial location names, the `scope` DTO field is a
loose dict rather than a structured model, and Alembic without env vars
fails with a generic config error. None affects the fixture workflow.

## Follow-up pass (same day, at the user's prompt)

The four "deliberately left" items above were then fixed, plus two smaller
ones found while re-verifying:

- Sort is now bidirectional with honest `aria-sort` (descending by default
  for counts/changes; the original code sorted descending while *labeling*
  it ascending — fixed together). History-row ids are index-based, so
  punctuation-differing location names cannot collide.
- `scope` (and `policy`) became structured models (`ScopeOut`, `PolicyOut`);
  the committed OpenAPI snapshot and the contract test cover their fields.
- Alembic fails with an explicit message when no database URL is set.
- The `no_truncate` pytest marker is registered (warning gone), and a React
  `ErrorBoundary` degrades malformed responses to a message with a reload
  path. The boundary initially sat too low: the crash occurred in `App`'s
  own render, which no descendant boundary can catch — the failing test
  showed a fully unmounted tree; the review body moved into a child
  component inside the boundary.

Frontend suite grew to 23 tests; backend remains at 103, all green.

## Accessibility audit pass (same day, at the user's prompt)

Audited in a real browser (structure, focus CSS, 375px layout) plus the
compiled CSS. Verified present: semantic table with caption/scopes/aria-sort,
all controls labeled, heading hierarchy, lang, aria-expanded/pressed,
role=status/alert states, skip link, :focus-visible outline, text+shape+color
status, tabular numerals. Fixed as a result:

- **Page-wide horizontal overflow at 375px** despite a correct internal
  scroll region. Root cause: the `.sr-only` utility used
  `position: absolute`, and the visually hidden "History" `<th>` had no
  positioned ancestor inside the scroll container — its containing block
  escaped the region's clip and extended the page's scrollable area to
  624px. Replaced with a visible "History" header (simpler and more honest
  for a labeled column) and a clip-path-based sr-only utility that stays in
  layout. Verified: docScrollWidth == viewport, no pan, table scrolls
  internally.
- Table wrapped in a labeled, focusable scroll region (`role="region"`,
  `aria-label`, `tabindex="0"`) so keyboard users can scroll it.
- `prefers-reduced-motion` (spinner animation) and `forced-colors` (bar
  borders, active segment) media queries added.
- Uncovered-week text opacity raised from 0.55 (contrast fail for real
  data) to 0.8.
- Duplicate group semantics removed from the metric control
  (fieldset+legend already names it; the inner `role="group"` made screen
  readers announce it twice).
- Larger touch targets for row-expansion buttons.

Environment limitation, recorded honestly: the in-app browser intercepts
Tab and its webview lacks window focus, so keyboard Tab-order traversal was
verified structurally (native controls in DOM order, focus-visible rules in
the compiled CSS) rather than by watching focus move.

Verified clean during the review (checked, not assumed): parameterization
of every repository query including the timezone used in `AT TIME ZONE`,
account-scope presence in every repository method, no interpolation of
request values into SQL, half-open window handling, error-envelope shapes,
and the population-change suppression paths.

## Redactions

None required: no credentials, personal files, or unrelated conversations
were part of this task's context.
