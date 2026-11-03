// Filter controls. All changes write to the URL; the server stays
// authoritative for validation and every derived number.

import type { Account, Metric, ReviewOptions } from "../api";
import { METRIC_LABELS, formatWeekRange } from "../format";
import { METRICS } from "../urlState";

interface ControlsProps {
  accounts: Account[];
  options: ReviewOptions | null;
  accountId: number | null;
  week: string;
  metric: Metric;
  location: string;
  onAccountChange: (id: number) => void;
  onWeekChange: (week: string) => void;
  onMetricChange: (metric: Metric) => void;
  onLocationChange: (location: string) => void;
}

const fieldStyle = { display: "flex", flexDirection: "column", gap: "0.25rem" } as const;

export function Controls({
  accounts,
  options,
  accountId,
  week,
  metric,
  location,
  onAccountChange,
  onWeekChange,
  onMetricChange,
  onLocationChange,
}: ControlsProps) {
  return (
    <form className="controls" onSubmit={(event) => event.preventDefault()}>
      <label style={fieldStyle}>
        Account
        <select
          value={accountId ?? ""}
          onChange={(event) => onAccountChange(Number(event.target.value))}
          disabled={accounts.length === 0}
        >
          {accounts.map((account) => (
            <option key={account.id} value={account.id}>
              {account.name}
            </option>
          ))}
        </select>
      </label>

      <label style={fieldStyle}>
        Week (complete weeks only)
        <select
          value={week}
          onChange={(event) => onWeekChange(event.target.value)}
          disabled={!options}
        >
          {options
            ? [...options.available_weeks].reverse().map((monday) => (
                <option key={monday} value={monday}>
                  {formatWeekRange(monday)}
                </option>
              ))
            : null}
        </select>
      </label>

      <fieldset className="metric-fieldset">
        <legend>Metric</legend>
        <div className="segmented" role="group" aria-label="Metric">
          {METRICS.map((candidate) => (
            <button
              key={candidate}
              type="button"
              aria-pressed={candidate === metric}
              className={candidate === metric ? "segment active" : "segment"}
              onClick={() => onMetricChange(candidate)}
            >
              {METRIC_LABELS[candidate]}
            </button>
          ))}
        </div>
      </fieldset>

      <label style={fieldStyle}>
        Location
        <select
          value={location}
          onChange={(event) => onLocationChange(event.target.value)}
          disabled={!options}
        >
          <option value="">All locations</option>
          {options
            ? options.locations.map((name) => (
                <option key={name} value={name}>
                  {name}
                </option>
              ))
            : null}
        </select>
      </label>
    </form>
  );
}
