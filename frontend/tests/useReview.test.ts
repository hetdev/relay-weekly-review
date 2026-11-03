import { afterEach, describe, expect, it, vi } from "vitest";
import { act, renderHook, waitFor } from "@testing-library/react";
import { useReview } from "../src/features/review/useReview";

function jsonResponse(body: unknown, status = 200): Response {
  return {
    ok: status < 400,
    status,
    headers: new Headers({ "X-Request-ID": "test" }),
    json: async () => body,
  } as unknown as Response;
}

const accountsBody = [
  { id: 1, name: "Alpha", industry: "X", timezone: "UTC" },
  { id: 2, name: "Beta", industry: "Y", timezone: "UTC" },
];

const optionsBody = (accountId: number) => ({
  account: accountsBody[accountId - 1],
  timezone: "UTC",
  locations: ["Site A"],
  default_week: "2026-07-20",
  available_weeks: ["2026-07-13", "2026-07-20"],
  coverage: {
    coverage_start_utc: "2026-02-01T00:00:00Z",
    coverage_end_utc: "2026-07-28T00:00:00Z",
    demo_now_utc: "2026-07-28T12:00:00Z",
    last_observed_event_utc: null,
    warnings: [],
  },
});

const reviewBody = (week: string) => ({
  request_id: `req-${week}`,
  scope: { account_id: 1, account_name: "Alpha", metric: "call_received", location: null, week_start: week },
  time: {
    timezone: "UTC",
    week_start_local: `${week}T00:00:00Z`,
    week_end_local: `${week}T00:00:00Z`,
    week_start_utc: `${week}T00:00:00Z`,
    week_end_utc: `${week}T00:00:00Z`,
  },
  baseline: { week_count: 8, weeks_covered: 8, start_utc: `${week}T00:00:00Z` },
  policy: { version: "v1", baseline_weeks: 8, low_volume_reference: 5, min_absolute_change: 5, min_relative_change: 0.2 },
  coverage: {
    coverage_start_utc: "2026-02-01T00:00:00Z",
    coverage_end_utc: "2026-07-28T00:00:00Z",
    demo_now_utc: "2026-07-28T12:00:00Z",
    last_observed_event_utc: null,
    warnings: [],
  },
  summary: { count: 1, reference: 1, delta: 0, percent_change: 0, observed_min: 1, observed_max: 1, reason: "no_review_flag", classification_suppressed: false, weeks: [] },
  account_summary: { count: 1, reference: 1, delta: 0, percent_change: 0, observed_min: 1, observed_max: 1, reason: "no_review_flag", classification_suppressed: false, weeks: [] },
  locations: [],
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

describe("useReview stale-response protection", () => {
  it("a slow old response never overwrites a newer one", async () => {
    let weekFetch = 0;
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        const target = new URL(url, "http://localhost");
        if (target.pathname.endsWith("/accounts")) return jsonResponse(accountsBody);
        if (target.pathname.endsWith("/review-options")) return jsonResponse(optionsBody(1));
        // weekly-review: first call slow (old week), second call fast (new week)
        weekFetch += 1;
        const week = target.searchParams.get("week_start");
        if (weekFetch === 1) {
          await new Promise((resolve) => setTimeout(resolve, 150));
          return jsonResponse(reviewBody("2026-07-13"));
        }
        return jsonResponse(reviewBody(week ?? ""));
      }),
    );

    const { result, rerender } = renderHook(({ week }) => useReview({ account: 1, week, metric: "call_received" as const, location: "" }), {
      initialProps: { week: "2026-07-13" },
    });

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.review?.scope.week_start).toBe("2026-07-13");

    // Switch to the newer week; its response arrives BEFORE the old one.
    rerender({ week: "2026-07-20" });
    await waitFor(() => expect(result.current.review?.scope.week_start).toBe("2026-07-20"));

    // The slow old response lands now and must be dropped.
    await new Promise((resolve) => setTimeout(resolve, 250));
    expect(result.current.review?.scope.week_start).toBe("2026-07-20");
    expect(result.current.error).toBeNull();
  });

  it("surfaces ApiError messages with a retry path", async () => {
    let attempts = 0;
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        if (url.includes("weekly-review")) {
          attempts += 1;
          if (attempts === 1) {
            return jsonResponse(
              { error: { code: "internal_error", message: "An internal error occurred.", request_id: "x" } },
              500,
            );
          }
          return jsonResponse(reviewBody("2026-07-20"));
        }
        const target = new URL(url, "http://localhost");
        if (target.pathname.endsWith("/accounts")) return jsonResponse(accountsBody);
        return jsonResponse(optionsBody(1));
      }),
    );

    const { result } = renderHook(() =>
      useReview({ account: 1, week: "2026-07-20", metric: "call_received" as const, location: "" }),
    );
    await waitFor(() => expect(result.current.error?.code).toBe("internal_error"));
    expect(result.current.review).toBeNull();

    act(() => result.current.reload());
    await waitFor(() => expect(result.current.review?.scope.week_start).toBe("2026-07-20"));
    expect(result.current.error).toBeNull();
  });
});
