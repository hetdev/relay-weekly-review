// Display-only formatting. Comparisons stay unrounded end to end; rounding
// happens exactly here, at the edge.

const numberFormat = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 });
const decimalFormat = new Intl.NumberFormat("en-US", {
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
});

export function formatCount(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return numberFormat.format(value);
}

export function formatReference(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return decimalFormat.format(value);
}

export function formatDelta(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  const rounded = decimalFormat.format(Math.abs(value));
  const sign = value > 0 ? "+" : value < 0 ? "−" : "";
  return `${sign}${rounded}`;
}

export function formatPercent(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  const rounded = decimalFormat.format(Math.abs(value));
  const sign = value > 0 ? "+" : value < 0 ? "−" : "";
  return `${sign}${rounded}%`;
}

export function formatRange(
  min: number | null | undefined,
  max: number | null | undefined,
): string {
  if (min === null || min === undefined || max === null || max === undefined) {
    return "—";
  }
  return `${numberFormat.format(min)}–${numberFormat.format(max)}`;
}

// Week labels are constructed from UTC-midnight Mondays, so the formatter
// must pin UTC too — otherwise the browser's local timezone shifts the label
// by a day.
const weekLabel = new Intl.DateTimeFormat("en-US", {
  month: "short",
  day: "numeric",
  timeZone: "UTC",
});

/** "Jul 20–Jul 26, 2026" for a week starting on the given Monday.
 * Month appears on both sides so month-crossing weeks stay unambiguous
 * ("Jun 29–Jul 5, 2026"). */
export function formatWeekRange(mondayIso: string): string {
  const start = new Date(`${mondayIso}T00:00:00Z`);
  const end = new Date(start.getTime() + 6 * 24 * 3600 * 1000);
  const startYear = start.getUTCFullYear();
  const endYear = end.getUTCFullYear();
  const startText = weekLabel.format(start);
  const endText = weekLabel.format(end);
  if (startYear === endYear) {
    return `${startText}–${endText}, ${startYear}`;
  }
  return `${startText}, ${startYear}–${endText}, ${endYear}`;
}

export function formatUtcTimestamp(iso: string | null | undefined): string {
  if (!iso) return "—";
  const moment = new Date(iso);
  return new Intl.DateTimeFormat("en-US", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "UTC",
  }).format(moment);
}

export const METRIC_LABELS: Record<string, string> = {
  call_received: "Calls received",
  lead_created: "Leads created",
  appointment_set: "Appointments set",
};

export const REASON_LABELS: Record<string, string> = {
  no_activity_recorded: "No activity recorded",
  insufficient_history: "Not enough history yet",
  no_recent_activity: "No activity this week",
  activity_after_zero_baseline: "Activity after weeks of none",
  low_volume: "Low volume",
  below_recent_range: "Below recent range",
  above_recent_range: "Above recent range",
  no_review_flag: "Within recent range",
};
