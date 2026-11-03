# Final delivery corrections — November 3, 2026

This is a summary of the correction session, not a raw transcript.
Tool: Codex. The original implementation and edited planning exports remain unchanged.

## User requests (verbatim)

> ultima revision antes de entregar todo

> dale corrigelos y genera el output nuevamente

> continua

## Accepted corrections and verification

1. Updated Vite 5.4.11 to 7.3.7, Vitest 2.1.8 to 4.1.12 and the React
   plugin to 4.7.0; regenerated the npm lockfile. Removed the obsolete
   esbuild-specific allowScripts metadata. Installation used
   `npm ci --ignore-scripts`; no dependency lifecycle scripts were enabled.
   Kept the existing bundler family and React version. `npm audit` now
   reports zero frontend vulnerabilities at the time of this check.
2. Initial load and browser history now share URL recovery. Invalid values
   produce a visible notice and replace the URL while preserving valid
   filters, the path and fragment. Two interaction regressions verify both
   entry paths, unchanged history length, selected metric and clean reload.
3. Rebuild the delivered checkout by cloning the bundle, then verify its
   own `.git`, exact top-level directory, commit and clean status. The prior
   folder was only a source copy: Git had discovered the parent repository.
   Packaging now validates this boundary explicitly before declaring success.

Verification: 113 backend tests, 22 frontend tests, TypeScript checking and
production build passed. The existing third-party deprecation warning and
intentional malformed-response error output remain nonfatal.

A temporary Vite check verified untrusted and opaque origins receive no
CORS access, untrusted Host returns 403, and an untrusted tokenless HMR
WebSocket returns 400. Local source/HTML, the API proxy and token-authenticated
HMR still work. The first harness expected 403 for the WebSocket and hung
while closing keep-alive connections; its expectation was corrected against
Vite's implementation and cleanup bounded. All final assertions passed.
Dependency optimization cancellation during test shutdown is not a build failure.

The independent investigator could not run because credits were unavailable;
the parent performed the separate boundary and compatibility passes. No
publication, external messages, or production deployment were performed.
The backend dependency advisories noted in the review were not relabeled as
fixed: those matches concern paths absent from this application or local
pytest temporary-directory handling. The zero-advisory result above is npm only.

## Deliberately unchanged

The original PLAN.md, original implementation log, business rules, backend,
and migrations were preserved. No new OS/browser certification or repeat
full backend dependency installation is claimed. The earlier fresh-clone
setup remains a dated record; frontend dependencies were installed afresh.

Final compatibility pass: the application mounts under React Strict Mode.
The initial recovery now retains its notice across effect replay; actual
history navigation still clears an obsolete notice. Both new interaction
cases run under Strict Mode, matching the real entry point.
