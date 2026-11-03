// Typed API client. Types mirror the backend contract (backend/app/api/dtos.py);
// `npm run sync-openapi` regenerates src/features/review/openapi.json from the
// running API. A backend test checks snapshot freshness against the live
// schema; these handwritten TypeScript interfaces still require review.

export type Metric = "call_received" | "lead_created" | "appointment_set";

export type Reason =
  | "no_activity_recorded"
  | "insufficient_history"
  | "no_recent_activity"
  | "activity_after_zero_baseline"
  | "low_volume"
  | "below_recent_range"
  | "above_recent_range"
  | "no_review_flag";

export interface Account {
  id: number;
  name: string;
  industry: string;
  timezone: string;
}

export interface WeekPoint {
  week_start: string; // YYYY-MM-DD (Monday)
  covered: boolean;
  count: number;
}

export interface Comparison {
  count: number;
  reference: number | null;
  delta: number | null;
  percent_change: number | null;
  observed_min: number | null;
  observed_max: number | null;
  reason: Reason | null;
  classification_suppressed: boolean;
  weeks: WeekPoint[];
}

export interface LocationRow {
  location: string;
  first_observed_utc: string | null;
  view: Comparison;
}

export interface ReviewResponse {
  request_id: string;
  scope: {
    account_id: number;
    account_name: string;
    metric: Metric;
    location: string | null;
    week_start: string;
  };
  time: {
    timezone: string;
    week_start_local: string;
    week_end_local: string;
    week_start_utc: string;
    week_end_utc: string;
  };
  baseline: { week_count: number; weeks_covered: number; start_utc: string };
  policy: {
    version: string;
    baseline_weeks: number;
    low_volume_reference: number;
    min_absolute_change: number;
    min_relative_change: number;
  };
  coverage: {
    coverage_start_utc: string;
    coverage_end_utc: string;
    demo_now_utc: string;
    last_observed_event_utc: string | null;
    warnings: string[];
  };
  summary: Comparison;
  account_summary: Comparison;
  locations: LocationRow[];
}

export interface ReviewOptions {
  account: Account;
  timezone: string;
  locations: string[];
  default_week: string;
  available_weeks: string[];
  coverage: {
    coverage_start_utc: string;
    coverage_end_utc: string;
    demo_now_utc: string;
    last_observed_event_utc: string | null;
    warnings: string[];
  };
}

export class ApiError extends Error {
  constructor(
    readonly code: string,
    message: string,
    readonly requestId: string | null,
    readonly status: number,
  ) {
    super(message);
  }
}

async function request<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(path, { signal, headers: { Accept: "application/json" } });
  if (!response.ok) {
    let code = "http_error";
    let message = `Request failed with status ${response.status}`;
    let requestId: string | null = response.headers.get("X-Request-ID");
    try {
      const body = await response.json();
      if (body?.error) {
        code = body.error.code ?? code;
        message = body.error.message ?? message;
        requestId = body.error.request_id ?? requestId;
      }
    } catch {
      // non-JSON error body; keep defaults
    }
    throw new ApiError(code, message, requestId, response.status);
  }
  return (await response.json()) as T;
}

export function fetchAccounts(signal?: AbortSignal): Promise<Account[]> {
  return request<Account[]>("/api/v1/accounts", signal);
}

export function fetchReviewOptions(
  accountId: number,
  signal?: AbortSignal,
): Promise<ReviewOptions> {
  return request<ReviewOptions>(
    `/api/v1/accounts/${accountId}/review-options`,
    signal,
  );
}

export interface ReviewQuery {
  accountId: number;
  weekStart: string;
  metric: Metric;
  location: string | null;
}

export function fetchWeeklyReview(
  query: ReviewQuery,
  signal?: AbortSignal,
): Promise<ReviewResponse> {
  const params = new URLSearchParams({
    week_start: query.weekStart,
    metric: query.metric,
  });
  if (query.location) params.set("location", query.location);
  return request<ReviewResponse>(
    `/api/v1/accounts/${query.accountId}/weekly-review?${params.toString()}`,
    signal,
  );
}
