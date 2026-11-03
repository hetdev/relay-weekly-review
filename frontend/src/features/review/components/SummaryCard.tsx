// Headline: this week vs the account's (or filtered location's) own recent
// history. Neutral language only — a change is a reason to look, not a
// verdict.

import type { Comparison, ReviewResponse } from "../api";
import {
  METRIC_LABELS,
  REASON_LABELS,
  formatCount,
  formatDelta,
  formatPercent,
  formatRange,
  formatReference,
  formatWeekRange,
} from "../format";

export function SummaryCard({ review }: { review: ReviewResponse }) {
  const summary: Comparison = review.summary;
  const filtered = review.scope.location !== null;
  const population = filtered ? ` — ${review.scope.location} only` : "";

  return (
    <section className="summary-card" aria-labelledby="summary-heading">
      <h2 id="summary-heading">
        {METRIC_LABELS[review.scope.metric] ?? review.scope.metric}
        <span className="summary-sub">
          {" "}
          · week of {formatWeekRange(review.scope.week_start)} · {review.time.timezone}
          {population}
        </span>
      </h2>

      <div className="summary-grid">
        <div className="summary-stat">
          <span className="stat-label">This week</span>
          <span className="stat-value">{formatCount(summary.count)}</span>
        </div>
        <div className="summary-stat">
          <span className="stat-label">8-week average</span>
          <span className="stat-value">{formatReference(summary.reference)}</span>
        </div>
        <div className="summary-stat">
          <span className="stat-label">Recent range</span>
          <span className="stat-value">
            {formatRange(summary.observed_min, summary.observed_max)}
          </span>
        </div>
        <div className="summary-stat">
          <span className="stat-label">Change vs average</span>
          <span className="stat-value">
            {formatDelta(summary.delta)} ({formatPercent(summary.percent_change)})
          </span>
        </div>
        <div className="summary-stat">
          <span className="stat-label">Status</span>
          <span
            className={
              summary.reason === "below_recent_range"
                ? "stat-value status-down"
                : summary.reason === "above_recent_range"
                  ? "stat-value status-up"
                  : "stat-value"
            }
          >
            {summaryLabel(summary)}
          </span>
        </div>
      </div>

      {review.coverage.warnings.includes("population_change") ? (
        <p className="warning" role="status">
          ⚠ New locations opened during the comparison window, so the overall
          classification is hidden. Totals still include every location.
        </p>
      ) : null}
      {summary.reason === "insufficient_history" ? (
        <p className="notice" role="status">
          Not enough recorded history for this week to form an 8-week baseline.
          Weekly counts are still shown.
        </p>
      ) : null}
    </section>
  );
}

function summaryLabel(summary: Comparison): string {
  if (summary.classification_suppressed) return "Classification hidden (population changed)";
  if (summary.reason === null) return "—";
  return REASON_LABELS[summary.reason] ?? summary.reason;
}
