# 0003 — Comparison policy v1: mean of 8, thresholds, suppression rules

Date: 2026-11-03 · Status: implemented as planned (plan.md §6)

## Decision

`reference` = mean of the 8 preceding complete weeks (target excluded; mean
chosen for its additive property — location references sum to the account
reference under the same population). Percent change is `100·(c−ref)/ref`,
`null` when `ref = 0` (never infinity). Rules in order: no activity recorded →
insufficient history (<8 covered weeks or first observation inside the
baseline window) → zero-baseline pair → low volume (reference < 5/week;
arithmetic shown, swings not labeled) → below/above recent range (flag only
when the move beyond the range edge is **≥5 events and ≥20% of that edge**) →
no review flag.

Two guardrails beyond the plan text:

1. **Population-change suppression**: when a location first appears inside or
   after the baseline window, the account-level classification is suppressed
   (`reason: null`, warning `population_change`) while totals stay visible —
   comparing a week that contains a new location against a baseline that does
   not would manufacture a "change".
2. Uncovered fixture weeks are never averaged in; they are displayed greyed
   with `covered: false`.

Thresholds live in `PolicyConfig` (versioned, disclosed in every response,
rendered in the UI footnotes). Not tuned against the seed.

## Evidence

`tests/test_policy.py` — hand-calculated arithmetic, exact threshold
boundaries (drop = 5 flags, 4 does not; exactly 20% flags), rule ordering,
`insufficient_history` nullability, ranking determinism.
`tests/test_api.py` exercises every reason against synthetic data with one
location per rule.
