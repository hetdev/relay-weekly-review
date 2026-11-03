// Application shell: URL is the canonical filter state (reload / back /
// forward / sharing reproduce the same view); the server is authoritative
// for every calculation.

import { useCallback, useEffect, useMemo, useState } from "react";
import { Controls } from "./features/review/components/Controls";
import { LocationTable } from "./features/review/components/LocationTable";
import { SummaryCard } from "./features/review/components/SummaryCard";
import { EmptyState, ErrorState, LoadingState } from "./features/review/components/States";
import type { Metric } from "./features/review/api";
import { formatUtcTimestamp } from "./features/review/format";
import { useReview } from "./features/review/useReview";
import { filtersToSearch, parseUrlFilters, type UrlFilters } from "./features/review/urlState";

export default function App() {
  const [filters, setFilters] = useState<UrlFilters>(() => {
    const { filters: parsed } = parseUrlFilters(window.location.search);
    return parsed;
  });
  const [urlNotice, setUrlNotice] = useState<string | null>(null);

  const pushFilters = useCallback((next: UrlFilters, replace = false) => {
    setFilters(next);
    const search = filtersToSearch(next);
    if (replace) {
      window.history.replaceState(null, "", search || window.location.pathname);
    } else {
      window.history.pushState(null, "", search || window.location.pathname);
    }
  }, []);

  // Back/forward reproduce earlier views.
  useEffect(() => {
    const onPopState = () => {
      const { filters: parsed, invalid } = parseUrlFilters(window.location.search);
      setFilters(parsed);
      setUrlNotice(
        invalid.length > 0
          ? `Some URL parameters were invalid and reset to defaults: ${invalid.join(", ")}`
          : null,
      );
    };
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  const { accounts, options, review, loading, error, reload } = useReview(filters);

  // When the loaded data disagrees with the URL (unknown account/week/location),
  // recover to valid values and surface a clear notice.
  useEffect(() => {
    if (!options || loading || error) return;
    const patches: Partial<UrlFilters> = {};
    if (filters.account !== null && filters.account !== options.account.id) {
      patches.account = options.account.id;
    }
    if (filters.week !== null && filters.week !== review?.scope.week_start) {
      patches.week = review?.scope.week_start ?? null;
    }
    if (
      filters.location &&
      !options.locations.includes(filters.location)
    ) {
      patches.location = "";
    }
    if (Object.keys(patches).length > 0) {
      setFilters((current) => ({ ...current, ...patches }));
      setUrlNotice("Some filters in the URL were not valid for this account and were reset.");
    }
  }, [options, review, loading, error, filters]);

  const currentAccount = useMemo(
    () => accounts.find((account) => account.id === (filters.account ?? options?.account.id)),
    [accounts, filters.account, options],
  );

  const onAccountChange = (id: number) => {
    // Locations belong to an account; switching clears an incompatible filter.
    pushFilters({ ...filters, account: id, location: "" });
  };
  const onWeekChange = (week: string) => pushFilters({ ...filters, week });
  const onMetricChange = (metric: Metric) => pushFilters({ ...filters, metric });
  const onLocationChange = (location: string) => pushFilters({ ...filters, location });

  return (
    <div className="app">
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <header className="app-header">
        <h1>Relay · Weekly activity review</h1>
        <p className="demo-clock">
          Fixture demo date: {formatUtcTimestamp(review?.coverage.demo_now_utc ?? options?.coverage.demo_now_utc)}
          {review?.coverage.last_observed_event_utc
            ? ` · last recorded event ${formatUtcTimestamp(review.coverage.last_observed_event_utc)}`
            : null}
        </p>
      </header>

      <main id="main">
        <Controls
          accounts={accounts}
          options={options}
          accountId={currentAccount?.id ?? filters.account}
          week={review?.scope.week_start ?? filters.week ?? ""}
          metric={filters.metric}
          location={filters.location}
          onAccountChange={onAccountChange}
          onWeekChange={onWeekChange}
          onMetricChange={onMetricChange}
          onLocationChange={onLocationChange}
        />

        {urlNotice ? (
          <p className="notice" role="status">
            {urlNotice}
          </p>
        ) : null}

        {error ? (
          <ErrorState message={error.message} onRetry={reload} />
        ) : loading ? (
          <LoadingState label="Loading weekly review…" />
        ) : !review ? (
          <EmptyState message="No accounts are available to this principal." />
        ) : review.summary.reason === "no_activity_recorded" &&
          review.locations.length === 0 ? (
          <EmptyState
            message={`No activity has been recorded for ${review.scope.account_name} as of this week.`}
          />
        ) : (
          <>
            <SummaryCard review={review} />
            <LocationTable rows={review.locations} weekStart={review.scope.week_start} />
            <footer className="footnotes">
              <p>
                “8-week average” is the mean of the eight preceding complete weeks
                (this week excluded). Change thresholds: flagged only when the move
                beyond the recent range is ≥{review.policy.min_absolute_change} events
                and ≥{Math.round(review.policy.min_relative_change * 100)}% of the
                range edge — policy {review.policy.version}. “Within recent range”
                means those explicit thresholds were not met; it is not a judgement
                of business health.
              </p>
              <p>
                Weeks shown in grey fall outside the assumed fixture recording
                interval ({formatUtcTimestamp(review.coverage.coverage_start_utc)} to{" "}
                {formatUtcTimestamp(review.coverage.coverage_end_utc)}) and are never
                averaged in. All boundaries are local Mondays in{" "}
                {review.time.timezone}. Request {review.request_id}.
              </p>
            </footer>
          </>
        )}
      </main>
    </div>
  );
}
