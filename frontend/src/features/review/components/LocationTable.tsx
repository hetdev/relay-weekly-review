// Location comparison table: sortable within the bounded server response,
// with an expandable 9-week history per row. The browser never recomputes
// classifications — sorting and labels only.

import { Fragment, useMemo, useState } from "react";
import type { LocationRow } from "../api";
import {
  REASON_LABELS,
  formatCount,
  formatDelta,
  formatPercent,
  formatRange,
  formatReference,
  formatWeekRange,
} from "../format";

type SortKey = "review" | "location" | "count" | "change";

interface LocationTableProps {
  rows: LocationRow[];
  weekStart: string;
}

export function LocationTable({ rows, weekStart }: LocationTableProps) {
  const [sortKey, setSortKey] = useState<SortKey>("review");
  const [expanded, setExpanded] = useState<string | null>(null);

  const sortedRows = useMemo(() => {
    if (sortKey === "review") return rows; // server ranking (flags first)
    const copy = [...rows];
    if (sortKey === "location") copy.sort((a, b) => a.location.localeCompare(b.location));
    if (sortKey === "count")
      copy.sort((a, b) => b.view.count - a.view.count || a.location.localeCompare(b.location));
    if (sortKey === "change")
      copy.sort(
        (a, b) =>
          (b.view.delta ?? -Infinity) - (a.view.delta ?? -Infinity) ||
          a.location.localeCompare(b.location),
      );
    return copy;
  }, [rows, sortKey]);

  const header = (key: SortKey, label: string, alignClass = "num") => {
    const isSorted = sortKey === key;
    return (
      <th
        scope="col"
        aria-sort={isSorted ? "ascending" : "none"}
        className={alignClass}
      >
        {key === "review" ? (
          label
        ) : (
          <button type="button" className="sort-button" onClick={() => setSortKey(key)}>
            {label}
            <span aria-hidden="true">{isSorted ? " ▲" : " ↕"}</span>
          </button>
        )}
      </th>
    );
  };

  return (
    <table className="location-table">
      <caption>
        Location comparison · week of {formatWeekRange(weekStart)} · flags are ranked:
        decreases by shortfall, then increases, then other states
      </caption>
      <thead>
        <tr>
          {header("location", "Location", "text")}
          {header("count", "This week")}
          <th scope="col" className="num">8-week average</th>
          <th scope="col" className="num">Recent range</th>
          {header("change", "Change")}
          <th scope="col" className="text">Status</th>
          <th scope="col" className="sr-only">History</th>
        </tr>
      </thead>
      <tbody>
        {sortedRows.map((row) => (
          <Fragment key={row.location}>
            <tr>
              <th scope="row" className="text">
                {row.location}
              </th>
              <td className="num">{formatCount(row.view.count)}</td>
              <td className="num">{formatReference(row.view.reference)}</td>
              <td className="num">
                {formatRange(row.view.observed_min, row.view.observed_max)}
              </td>
              <td className="num">
                {formatDelta(row.view.delta)}{" "}
                <span className="percent">
                  ({formatPercent(row.view.percent_change)})
                </span>
              </td>
              <td className="text">
                <span
                  className={
                    row.view.reason === "below_recent_range"
                      ? "status status-down"
                      : row.view.reason === "above_recent_range"
                        ? "status status-up"
                        : "status"
                  }
                >
                  {row.view.reason ? (REASON_LABELS[row.view.reason] ?? row.view.reason) : "—"}
                </span>
              </td>
              <td className="num">
                <button
                  type="button"
                  className="expand-button"
                  aria-expanded={expanded === row.location}
                  aria-controls={`history-${cssSafe(row.location)}`}
                  onClick={() =>
                    setExpanded((current) => (current === row.location ? null : row.location))
                  }
                >
                  {expanded === row.location ? "Hide history" : "Show history"}
                </button>
              </td>
            </tr>
            {expanded === row.location ? (
              <tr className="history-row" id={`history-${cssSafe(row.location)}`}>
                <td colSpan={7}>
                  <WeekHistory row={row} />
                </td>
              </tr>
            ) : null}
          </Fragment>
        ))}
      </tbody>
    </table>
  );
}

function WeekHistory({ row }: { row: LocationRow }) {
  const weeks = row.view.weeks;
  const max = Math.max(1, ...weeks.map((point) => point.count));
  const firstObserved = row.first_observed_utc
    ? new Date(row.first_observed_utc).toISOString().slice(0, 10)
    : null;
  return (
    <div className="week-history">
      <ol>
        {weeks.map((point) => (
          <li
            key={point.week_start}
            className={point.covered ? "covered" : "uncovered"}
          >
            <span className="week-label">{formatWeekRange(point.week_start)}</span>
            <span
              className="week-bar"
              aria-hidden="true"
              style={{ width: `${Math.round((point.count / max) * 100)}%` }}
            />
            <span className="week-count">{formatCount(point.count)}</span>
          </li>
        ))}
      </ol>
      <p className="history-note">
        {firstObserved
          ? `First recorded activity: ${firstObserved} (not an opening date). `
          : "No recorded activity in this window. "}
        Grey weeks fall outside the assumed fixture recording interval and are
        not used in the average.
      </p>
    </div>
  );
}

function cssSafe(name: string): string {
  return name.replace(/[^a-zA-Z0-9_-]/g, "_");
}
