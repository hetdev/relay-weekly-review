# 0007 — Optional LLM briefing layer: deferred, with evidence

Date: 2026-11-03 · Status: evaluated and deferred (plan.md §9 explicitly
allows deferral "with evidence")

## Decision

Ship the deterministic summary only; do not build the optional LLM briefing
in this iteration.

## Why

- The core acceptance gates (correct workflow, traceable numbers, tested
  behavior) are met without it; the ticket's outcome is "answer *is this
  normal for us* at a glance", which the neutral labels + drilldown deliver.
- The comparison is deterministic by design. An LLM cannot establish cause,
  calculate the numbers, decide access, or fill missing data — its only
  candidate value is compressing several already-verified location changes
  into a paragraph, at the cost of nondeterminism, latency, provider
  credentials, and an information-disclosure surface (even aggregate-only).
- Every number in an LLM paragraph would still have to be rendered from
  trusted server facts and claims validated against approved categories —
  i.e. the interesting engineering the plan describes — for marginal clarity
  gain at 15 locations.

## If it is ever built

The seam is already defined: a provider-neutral `SummaryProvider` port with
the deterministic summary as the default implementation, constructed with
aggregate facts and opaque ids only, strict schema/ID-membership validation,
bounded output, timeout + stub fallback, and caching keyed by account/week/
metric/location/policy-version/data-revision. No part of the current workflow
depends on it, and local startup requires no model key.
