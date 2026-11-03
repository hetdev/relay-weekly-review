# 0005 — Frontend: URL as canonical state, typed contract, stale-safe fetch

Date: 2026-11-03 · Status: implemented as planned (plan.md §7–8)

## Decision

- **URL search params are the filter state** (`?account=&week=&metric=&location=`).
  Reload, back/forward, and shared links reproduce the view; no state
  framework. Account switches clear incompatible location filters; invalid
  URL values recover to defaults with a visible notice (never a blank screen).
- The **typed client** mirrors the backend DTOs; `npm run sync-openapi`
  commits the served OpenAPI snapshot next to the client, and a contract test
  fails if the two drift (fields, nullability of `reason`, the metric enum).
- **Stale-response protection** is twofold: every filter change aborts the
  in-flight fetch (AbortController) *and* a sequence guard drops late
  responses — tested by making the old request resolve after the new one.
- Accessibility is structural, not bolted on: semantic table with caption and
  `scope`, `aria-sort` on sortable headers, `aria-expanded` drilldown
  buttons, status/live regions for loading and errors, skip link, visible
  focus, text + shape alongside color for status, tabular numerals. React's
  default escaping is the XSS posture; no raw HTML is ever rendered.
- Rounding is display-only (`format.ts`); the API keeps comparisons unrounded.

## Discoveries during testing

- `new Date("2026-07-20").getDay()` validated Mondays in the **browser's
  local timezone**, rejecting valid Mondays in western longitudes — the
  round-trip test caught it; fixed with an explicit `T00:00:00Z` + `getUTCDay()`.
- `Intl.DateTimeFormat` without `timeZone: "UTC"` shifted week labels a day
  in non-UTC test environments — same class of bug, same fix.
- Both are exactly why the Monday check and the labels are pinned to UTC.
