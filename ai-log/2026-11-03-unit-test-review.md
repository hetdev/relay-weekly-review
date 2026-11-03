# Unit-test review — November 3, 2026

Tool/model: Codex with GPT-6.1 Sol for inspection, test changes and verification.

## User request (verbatim)

> revisa que los unit tests tengan sentido y no sean repetidos

## Assistant's initial response (verbatim)

> Voy a revisar qué comportamiento comprueba cada test, si las expectativas son independientes del código y cuáles repiten el mismo caso. Ajustaré los redundantes y conservaré los que cubren límites o regresiones distintas.

## Review and changes (summary)

- The stale-response test previously awaited completion of the old request
  before changing weeks. It did not test a race. It now controls a pending
  promise, completes the new request first, then releases the old one while
  deliberately ignoring abort. No arbitrary sleeps remain.
- Removed duplicate small-drop, baseline-exclusion and URL weekday checks.
  Grouped distinct absolute/relative threshold boundaries in parameterized
  tests, including below-threshold cases in both directions.
- Replaced a permissive `None or finite` percentage assertion with exact
  expected values for a positive reference that includes a zero week.
- Removed a calendar test that compared against the same helper the code
  calls; strengthened month/year expectations with literal UTC instants and
  added equality at the fixture coverage boundaries.
- Removed five frontend tests that inspected only a committed OpenAPI JSON
  file, including a truthiness check that did not prove nullability. Added
  one database-free backend comparison between the actual generated API
  schema and the snapshot. Handwritten TypeScript compatibility remains a
  review concern, not something this schema test automatically proves.
- Kept retry coverage in the visible App interaction and replaced the hook's
  repeated retry scenario with the no-permitted-accounts short circuit.
- Preserved integration tests: checking a rule in isolation and checking
  SQL aggregation/API wiring against that rule protect different failures.

## Verification (summary, not a full raw transcript)

Commands included the complete backend suite, `pytest -m unit` with an
unreachable test database URL, the frontend suite and its TypeScript/build
command. Actual result excerpts:

```text
47 passed, 57 deselected, 1 warning in 0.07s
104 passed, 1 warning in 6.71s
Tests  20 passed (20)
✓ built in 292ms
```

Tests decreased from 26 to 20 on the frontend. The removed schema checks
were replaced with one stronger backend test, raising backend cases from
103 to 104. Counting tests was not the optimization criterion.

Five targeted mutation probes were performed in disposable copies, never
in the reviewed source tree. Each intentional defect was detected:

| Temporary defect | Result |
| --- | --- |
| Ignore relative change thresholds | Two tests failed |
| Return a null percentage with a positive reference | Four tests failed |
| Shift the start of the local week by one day | Five tests failed |
| Remove `reference` nullability from the API DTO | Contract test failed |
| Disable the stale-response sequence guard | Race test failed |

The first frontend mutation probe failed to start because its copy helper
excluded every directory named `dist`, including dependency code. That was
a probe setup error, not a detected product mutation. The copy rule was
corrected to exclude only the application's build output before rerunning.
No package installation or production-logic change was needed.

The existing Starlette/AnyIO deprecation warning remains. Raw transcripts
from earlier implementation sessions were not fabricated. No secrets were
included in these excerpts.
