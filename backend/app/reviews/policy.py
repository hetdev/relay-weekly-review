"""Comparison policy v1 — pure, deterministic, independently testable.

Rules and their order are the contract in PLAN.md section 6
("Classification policy v1"). The policy is a pure function of the target
count, the covered baseline counts, and whether the subject was observed at
or before the baseline window began. It performs no I/O and knows nothing
about SQL, HTTP, or timezones.

Threshold semantics (centralized here, versioned, disclosed in responses):
- "drop" / "increase" measure distance from the observed *range edge*
  (min/max of the baseline weeks), not from the mean.
- "relative" is that distance divided by the range edge.
- Uncovered baseline weeks are never treated as zeros; callers pass only the
  covered weeks and classification is suppressed when fewer than eight are
  available (rule 2).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Sequence

Reason = Literal[
    "no_activity_recorded",
    "insufficient_history",
    "no_recent_activity",
    "activity_after_zero_baseline",
    "low_volume",
    "below_recent_range",
    "above_recent_range",
    "no_review_flag",
]


@dataclass(frozen=True)
class PolicyConfig:
    """Product heuristics — initial values, deliberately centralized."""

    version: str = "v1"
    baseline_weeks: int = 8
    low_volume_reference: float = 5.0  # events/week; strictly below => low volume
    min_absolute_change: int = 5  # events, measured against the range edge
    min_relative_change: float = 0.20  # 20%, measured against the range edge


@dataclass(frozen=True)
class PolicyResult:
    reason: Reason
    reference: float | None  # mean of the 8 covered baseline weeks, when classified
    delta: float | None  # count - reference
    percent_change: float | None  # 100 * delta / reference; null when reference is 0
    observed_min: int | None  # min of the covered baseline weeks, when classified
    observed_max: int | None  # max of the covered baseline weeks, when classified


def classify(
    config: PolicyConfig,
    *,
    count: int,
    covered_baseline_counts: Sequence[int],
    first_observed_before_baseline: bool,
) -> PolicyResult:
    """Apply classification rules v1 in order (PLAN.md section 6)."""
    weeks = tuple(covered_baseline_counts)
    if len(weeks) > config.baseline_weeks or any(w < 0 for w in weeks):
        raise ValueError(
            f"expected at most {config.baseline_weeks} non-negative baseline weeks, got {weeks}"
        )

    # Rule 2 — suppressed classification rather than a manufactured baseline.
    if len(weeks) < config.baseline_weeks or not first_observed_before_baseline:
        return PolicyResult("insufficient_history", None, None, None, None, None)

    reference = sum(weeks) / len(weeks)
    observed_min = min(weeks)
    observed_max = max(weeks)
    delta = count - reference

    # Rule 3 — full baseline, zero reference. Percentage is null, never infinity.
    if reference == 0:
        if count == 0:
            return PolicyResult("no_recent_activity", 0.0, 0.0, None, 0, 0)
        return PolicyResult("activity_after_zero_baseline", 0.0, float(count), None, 0, 0)

    percent_change = 100.0 * delta / reference

    # Rule 4 — low volume: show the arithmetic, do not label swings unusual.
    if reference < config.low_volume_reference:
        return PolicyResult(
            "low_volume", reference, delta, percent_change, observed_min, observed_max
        )

    # Rule 5 — below the recent range.
    drop = observed_min - count
    if (
        count < observed_min
        and drop >= config.min_absolute_change
        and drop / observed_min >= config.min_relative_change
    ):
        return PolicyResult(
            "below_recent_range", reference, delta, percent_change, observed_min, observed_max
        )

    # Rule 6 — above the recent range.
    increase = count - observed_max
    if (
        count > observed_max
        and increase >= config.min_absolute_change
        and increase / observed_max >= config.min_relative_change
    ):
        return PolicyResult(
            "above_recent_range", reference, delta, percent_change, observed_min, observed_max
        )

    # Rule 7 — explicit thresholds were not met (not a health claim).
    return PolicyResult(
        "no_review_flag", reference, delta, percent_change, observed_min, observed_max
    )


def rank_key(
    location: str,
    reason: str | None,
    count: int,
    observed_min: int | None,
    observed_max: int | None,
) -> tuple[int, float, str]:
    """Deterministic ordering: flagged decreases by absolute shortfall,
    then flagged increases, then everything else; ties broken by name.

    Ranking works on classified rows only; unclassified rows
    (reason None / insufficient_history) sort last within "other states".
    """
    if reason == "below_recent_range" and observed_min is not None:
        group, primary = 0, -float(observed_min - count)
    elif reason == "above_recent_range" and observed_max is not None:
        group, primary = 1, -float(count - observed_max)
    else:
        group, primary = 2, 0.0
    return (group, primary, location)
