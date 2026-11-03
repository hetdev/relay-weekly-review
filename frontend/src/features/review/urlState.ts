// URL search parameters are the canonical shareable filter state.
// Reload, back/forward, and shared links must reproduce the same view.

import type { Metric } from "./api";

export const METRICS: readonly Metric[] = [
  "call_received",
  "lead_created",
  "appointment_set",
];

export const DEFAULT_METRIC: Metric = "call_received";

export interface UrlFilters {
  account: number | null; // null => pick the first account
  week: string | null; // null => options default week
  metric: Metric;
  location: string; // "" => all locations
}

export function parseUrlFilters(
  search: string,
): { filters: UrlFilters; invalid: string[] } {
  const params = new URLSearchParams(search);
  const invalid: string[] = [];

  let account: number | null = null;
  const rawAccount = params.get("account");
  if (rawAccount !== null) {
    const parsed = Number.parseInt(rawAccount, 10);
    if (Number.isFinite(parsed) && parsed > 0 && String(parsed) === rawAccount) {
      account = parsed;
    } else {
      invalid.push(`account=${rawAccount}`);
    }
  }

  let week: string | null = null;
  const rawWeek = params.get("week");
  if (rawWeek !== null) {
    // Monday check must be timezone-independent: interpret as UTC.
    const monday = new Date(`${rawWeek}T00:00:00Z`);
    if (/^\d{4}-\d{2}-\d{2}$/.test(rawWeek) && !Number.isNaN(monday.getTime()) && monday.getUTCDay() === 1) {
      week = rawWeek;
    } else {
      invalid.push(`week=${rawWeek}`);
    }
  }

  let metric: Metric = DEFAULT_METRIC;
  const rawMetric = params.get("metric");
  if (rawMetric !== null) {
    if ((METRICS as readonly string[]).includes(rawMetric)) {
      metric = rawMetric as Metric;
    } else {
      invalid.push(`metric=${rawMetric}`);
    }
  }

  const location = params.get("location") ?? "";
  if (location.length > 80) {
    invalid.push("location");
  }

  return {
    filters: { account, week, metric, location: location.slice(0, 80) },
    invalid,
  };
}

export function filtersToSearch(filters: UrlFilters): string {
  const params = new URLSearchParams();
  if (filters.account !== null) params.set("account", String(filters.account));
  if (filters.week !== null) params.set("week", filters.week);
  if (filters.metric !== DEFAULT_METRIC) params.set("metric", filters.metric);
  if (filters.location) params.set("location", filters.location);
  const encoded = params.toString();
  return encoded ? `?${encoded}` : "";
}
