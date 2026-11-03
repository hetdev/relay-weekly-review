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
type SortDir = "asc" | "desc";

interface SortState {
  key: SortKey;
  dir: SortDir;
}

// Natural first direction per column: counts/changes read best high-to-low,
// names low-to-high. Repeated clicks toggle.
const DEFAULT_DIR: Record<Exclude<SortKey, "review">, SortDir> = {
  location: "asc",
  count: "desc",
  change: "desc",
};

interface LocationTableProps {
  rows: LocationRow[];
  weekStart: string;
}

export function LocationTable({ rows, weekStart }: LocationTableProps) {
  const [sort, setSort] = useState<SortState>({ key: "review", dir: "asc" });
  const [expanded, setExpanded] = useState<string | null>(null);

  const sortedRows = useMemo(() => {
    if (sort.key === "review") return rows; // server ranking (flags first)
    const copy = [...rows];
    const direction = sort.dir === "asc" ? 1 : -1;
    if (sort.key === "location") {
      copy.sort((a, b) => a.location.localeCompare(b.location) * direction);
    } else if (sort.key === "count") {
      copy.sort(
        (a, b) => (a.view.count - b.view.count) * direction ||
          a.location.localeCompare(b.location),
      );
    } else {
      copy.sort(
        (a, b) =>
          ((a.view.delta ?? -Infinity) - (b.view.delta ?? -Infinity)) * direction ||
          a.location.localeCompare(b.location),
      );
    }
    return copy;
  }, [rows, sort]);

  const onHeaderClick = (key: SortKey) => {
    if (key === "review") {
      setSort({ key, dir: "asc" });
    } else if (sort.key === key) {
      setSort({ key, dir: sort.dir === "asc" ? "desc" : "asc" });
    } else {
      setSort({ key, dir: DEFAULT_DIR[key] });
    }
  };

  // ARIA allows exactly these aria-sort values; keep the literal union.
  const ariaSort = (key: SortKey): "none" | "ascending" | "descending" | "other" =>
    sort.key !== key ? "none" : key === "review" ? "other" : sort.dir === "asc" ? "ascending" : "descending";

  const header = (key: SortKey, label: string, alignClass = "num") => (
    <th scope="col" aria-sort={ariaSort(key)} className={alignClass}>
      <button type="button" className="sort-button" onClick={() => onHeaderClick(key)}>
        {label}
        <span aria-hidden="true">
          {sort.key === key && key !== "review" ? (sort.dir === "asc" ? " ▲" : " ▼") : " ↕"}
        </span>
      </button>
    </th>
  );

  return (
    // A labeled, focusable scroll region: keyboard users can scroll the
    // table on narrow screens and screen readers announce it as such.
    <div
      className="table-scroll"
      role="region"
      aria-label="Location comparison table"
      tabIndex={0}
    >
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
          <th scope="col" className="text">History</th>
        </tr>
      </thead>
      <tbody>
        {sortedRows.map((row, index) => (
          // Index-based ids cannot collide across locations with names that
          // differ only in punctuation ("Site A" vs "Site-A").
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
                  aria-controls={`history-row-${index}`}
                  onClick={() =>
                    setExpanded((current) => (current === row.location ? null : row.location))
                  }
                >
                  {expanded === row.location ? "Hide history" : "Show history"}
                </button>
              </td>
            </tr>
            {expanded === row.location ? (
              <tr className="history-row" id={`history-row-${index}`}>
                <td colSpan={7}>
                  <WeekHistory row={row} />
                </td>
              </tr>
            ) : null}
          </Fragment>
        ))}
        </tbody>
      </table>
    </div>
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
