# Delivery validation — November 3, 2026

## Scope and method

Validated implementation commit `e368707` from a fresh local Git clone with
its own virtual environment, newly installed declared dependencies and
dedicated empty PostgreSQL cluster. The original development databases and
existing node_modules/virtual environment were not reused. Only the database
and API ports were changed to free loopback ports to isolate the run.

Prerequisite installation is excluded from the timings below. Validation
covers macOS/Apple Silicon with Homebrew Python 3.12, PostgreSQL 17 and
Node.js 24. No Linux, Windows, container or production deployment claim is
made. The final documentation commit does not change application behavior.

| Step | Result | Elapsed |
| --- | --- | --- |
| Fresh clone | Passed | 0.13 s |
| `make db-init` | New roles and all three databases created before grants | 0.79 s |
| `make setup` | New venv, dependency install, migrations, verified seed, read-only grants and locked frontend install | 12.48 s |
| `make seed` again | Verified no-op | 0.30 s |
| `make test` | 104 backend tests, 20 frontend tests, TypeScript and production build passed | 9.63 s |
| `make bootstrap-test` | A second empty temporary cluster initialized; repeated starts preserved its PID | 1.04 s |
| Real HTTP smoke test | Readiness and fixture examples below passed | Not timed separately |

Both temporary database clusters and the temporary API were stopped after
the run. Dependency downloads came from the declared package sources;
frontend installation used `npm ci --ignore-scripts`. The same commands in
the README remain the supported setup path on the verified platform.

## HTTP checks

- `/readyz` returned HTTP 200.
- `/api/v1/accounts` returned 20 fixture accounts through the read-only API role.
- Pacific Smiles, calls, week of July 20: count **19**, reference **22.375**.
- Metro Collision Centers returned **15** location rows for that week.
- Quiet Harbor Spa returned **no_activity_recorded**.

## Unit-test quality

The 47 backend unit cases also passed with the test database URL pointed at
an unreachable port, demonstrating that they need no live PostgreSQL.
These cases are included in the 104 backend cases, not additional to them.

Five intentional defects in disposable copies were detected by the tests:
ignored relative thresholds; null percentages with positive reference;
shifted local-week boundaries; removed API nullability; and disabled stale
response protection. The test-audit log records what changed and why.
These are targeted probes, not an exhaustive mutation-coverage percentage.

## Evidence boundaries

The frontend suite uses jsdom and a mocked API for interactions. The HTTP
smoke test exercises the real backend and database. This final clean-copy
run did not perform a new end-to-end browser/accessibility certification;
earlier manual observations are identified in the interaction record.

The suite emits an existing third-party Starlette/AnyIO deprecation warning
and an expected caught React error in its malformed-response regression.
Neither is a failed test. Fixture-scale query observations remain in
`docs/performance-observations.txt`; these do not prove production scaling.

Before packaging, checked README link casing, excluded local environments,
dependency trees and database files, and scanned tracked text for common
credential/private-key patterns. No such credential material was found.
This check is not an antivirus or a guarantee about future dependencies.
