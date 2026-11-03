// Interaction tests over a mocked API: render, URL-driven state, sorting,
// drilldown, and accessibility structure.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import App from "../src/App";

function jsonResponse(body: unknown, status = 200): Response {
  return {
    ok: status < 400,
    status,
    headers: new Headers({ "X-Request-ID": "test" }),
    json: async () => body,
  } as unknown as Response;
}

const account = { id: 5, name: "Pacific Smiles", industry: "Dental", timezone: "America/Los_Angeles" };

const optionsBody = {
  account,
  timezone: "America/Los_Angeles",
  locations: ["Site A", "Site B"],
  default_week: "2026-07-20",
  available_weeks: ["2026-07-13", "2026-07-20"],
  coverage: {
    coverage_start_utc: "2026-02-01T00:00:00Z",
    coverage_end_utc: "2026-07-28T00:00:00Z",
    demo_now_utc: "2026-07-28T12:00:00Z",
    last_observed_event_utc: "2026-07-27T22:20:34Z",
    warnings: [],
  },
};

function reviewBody(overrides: Record<string, unknown> = {}) {
  return {
    request_id: "abc123",
    scope: { account_id: 5, account_name: "Pacific Smiles", metric: "call_received", location: null, week_start: "2026-07-20" },
    time: {
      timezone: "America/Los_Angeles",
      week_start_local: "2026-07-20T00:00:00-07:00",
      week_end_local: "2026-07-27T00:00:00-07:00",
      week_start_utc: "2026-07-20T07:00:00Z",
      week_end_utc: "2026-07-27T07:00:00Z",
    },
    baseline: { week_count: 8, weeks_covered: 8, start_utc: "2026-05-25T07:00:00Z" },
    policy: { version: "v1", baseline_weeks: 8, low_volume_reference: 5, min_absolute_change: 5, min_relative_change: 0.2 },
    coverage: optionsBody.coverage,
    summary: {
      count: 19,
      reference: 22.4,
      delta: -3.4,
      percent_change: -15.1,
      observed_min: 13,
      observed_max: 36,
      reason: "no_review_flag",
      classification_suppressed: false,
      weeks: [],
    },
    account_summary: {
      count: 19, reference: 22.4, delta: -3.4, percent_change: -15.1,
      observed_min: 13, observed_max: 36, reason: "no_review_flag",
      classification_suppressed: false, weeks: [],
    },
    locations: [
      {
        location: "Site A",
        first_observed_utc: "2026-01-28T18:00:00Z",
        view: {
          count: 4, reference: 10, delta: -6, percent_change: -60,
          observed_min: 10, observed_max: 10, reason: "below_recent_range",
          classification_suppressed: false,
          weeks: [
            { week_start: "2026-05-25", covered: true, count: 10 },
            { week_start: "2026-06-01", covered: true, count: 10 },
            { week_start: "2026-06-08", covered: true, count: 10 },
            { week_start: "2026-06-15", covered: true, count: 10 },
            { week_start: "2026-06-22", covered: true, count: 10 },
            { week_start: "2026-06-29", covered: true, count: 10 },
            { week_start: "2026-07-06", covered: true, count: 10 },
            { week_start: "2026-07-13", covered: true, count: 10 },
            { week_start: "2026-07-20", covered: true, count: 4 },
          ],
        },
      },
      {
        location: "Site B",
        first_observed_utc: "2026-01-30T18:00:00Z",
        view: {
          count: 15, reference: 10, delta: 5, percent_change: 50,
          observed_min: 10, observed_max: 10, reason: "above_recent_range",
          classification_suppressed: false,
          weeks: [],
        },
      },
    ],
    ...overrides,
  };
}

function installFetch(bodies: { review?: unknown; failOnce?: boolean } = {}) {
  const calls: string[] = [];
  let reviewCalls = 0;
  const fetchMock = vi.fn(async (url: string) => {
    calls.push(url);
    // Route most-specific first: every path contains /accounts.
    if (url.includes("weekly-review")) {
      reviewCalls += 1;
      if (bodies.failOnce && reviewCalls === 1) {
        return jsonResponse(
          { error: { code: "internal_error", message: "An internal error occurred.", request_id: "x" } },
          500,
        );
      }
      return jsonResponse(bodies.review ?? reviewBody());
    }
    if (url.includes("review-options")) return jsonResponse(optionsBody);
    return jsonResponse([account]);
  });
  vi.stubGlobal("fetch", fetchMock);
  return { calls, fetchMock };
}

beforeEach(() => {
  window.history.replaceState(null, "", "/");
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("App", () => {
  it("does not describe an unflagged value outside the range as within it", async () => {
    const body = reviewBody();
    const comparison = {
      ...body.summary, count: 24, reference: 20, delta: 4,
      percent_change: 20, observed_min: 20, observed_max: 20,
    };
    installFetch({ review: reviewBody({
      summary: comparison,
      locations: [{ ...body.locations[0], view: comparison }],
    }) });
    render(<App />);
    await waitFor(() => expect(screen.getAllByText("Review thresholds not met").length).toBe(2));
    expect(screen.queryByText("Within recent range")).toBeNull();
    expect(screen.getAllByText("20–20").length).toBe(2);
  });

  it("describes first recorded activity without claiming a location opened", async () => {
    const body = reviewBody();
    installFetch({ review: reviewBody({
      coverage: { ...body.coverage, warnings: ["population_change"] },
      summary: { ...body.summary, reason: null, classification_suppressed: true },
    }) });
    render(<App />);
    await waitFor(() => expect(screen.getByText(/Locations were first recorded/)).toBeTruthy());
    expect(screen.queryByText(/New locations opened/)).toBeNull();
  });

  it("renders the summary and accessible location table from the API", async () => {
    installFetch();
    render(<App />);

    await waitFor(() => expect(screen.getByText("19")).toBeTruthy());
    const heading = screen.getByRole("heading", { level: 2 }).textContent ?? "";
    expect(heading).toContain("Calls received");
    expect(heading).toContain("week of Jul 20–Jul 26, 2026");
    expect(heading).toContain("America/Los_Angeles");
    // Table semantics
    const table = screen.getByRole("table");
    expect(table.querySelector("caption")?.textContent).toContain("Location comparison");
    expect(table.querySelectorAll("th[scope='col']").length).toBeGreaterThanOrEqual(5);
    // Neutral status text alongside color
    expect(screen.getByText("Below recent range")).toBeTruthy();
    expect(screen.getByText("Above recent range")).toBeTruthy();
    // Fixture clock surfaced
    expect(screen.getByText(/Fixture demo date:/)).toBeTruthy();
    expect(screen.getByText(/last recorded event/)).toBeTruthy();
  });

  it("writes filters to the URL and reads them back on reload", async () => {
    installFetch();
    render(<App />);
    await waitFor(() => expect(screen.getByText("19")).toBeTruthy());

    await act(async () => {
      fireEvent.change(screen.getByLabelText("Location"), { target: { value: "Site A" } });
    });
    expect(window.location.search).toContain("location=Site+A");

    // Simulate reload: a fresh render picks the URL up and re-fetches with it.
    cleanup();
    render(<App />);
    await waitFor(() => {
      const fetchMock = vi.mocked(globalThis.fetch);
      const reviewCalls = fetchMock.mock.calls
        .flat()
        .map(String)
        .filter((url) => url.includes("weekly-review"));
      expect(reviewCalls.length).toBeGreaterThan(1);
      expect(reviewCalls[reviewCalls.length - 1]).toContain("location=Site+A");
    });
  });

  it("clears an incompatible location filter when the account changes", async () => {
    const secondAccount = { id: 7, name: "Desert Springs Plumbing", industry: "Home Services", timezone: "America/Phoenix" };
    const fetchMock = vi.fn(async (url: string) => {
      if (url.includes("weekly-review")) return jsonResponse(reviewBody());
      if (url.includes("review-options")) {
        return jsonResponse(url.includes("/5/") ? optionsBody : { ...optionsBody, account: secondAccount, locations: ["Site Z"] });
      }
      return jsonResponse([account, secondAccount]);
    });
    vi.stubGlobal("fetch", fetchMock);
    window.history.replaceState(null, "", "?location=Site+A");

    render(<App />);
    await waitFor(() => expect(screen.getByText("19")).toBeTruthy());

    await act(async () => {
      fireEvent.change(screen.getByLabelText("Account"), { target: { value: "7" } });
    });
    expect(window.location.search).not.toContain("location=");
  });

  it("rewrites the URL when filters parse fine but are unknown to the account", async () => {
    installFetch();
    // account=999 is a positive int (parses) but unknown; Site Z parses but
    // is not a known location for account 5.
    window.history.replaceState(null, "", "?account=999&location=Site+Z");
    render(<App />);

    await waitFor(() => expect(screen.getByText("19")).toBeTruthy());
    // The recovered view is served under a corrected URL, so reload and
    // shared links carry valid state.
    await waitFor(() => {
      expect(window.location.search).toContain("account=5");
      expect(window.location.search).not.toContain("Site+Z");
    });
    expect(screen.getByText(/not valid for this account/)).toBeTruthy();
  });

  it("exposes an accessible scroll region and a single metric group", async () => {
    installFetch();
    render(<App />);
    await waitFor(() => expect(screen.getByText("19")).toBeTruthy());

    // Narrow screens scroll the table inside a labeled, focusable region.
    const region = screen.getByRole("region", { name: "Location comparison table" });
    expect((region as HTMLElement).tabIndex).toBe(0);

    // The metric control is named once (fieldset+legend), not twice.
    expect(document.querySelectorAll('[role="group"]').length).toBe(0);
    expect(document.querySelectorAll("fieldset").length).toBe(1);
    expect(screen.getByRole("group", { name: "Metric" })).toBeTruthy();
  });

  it("sorts by count with an honest aria-sort and toggles direction", async () => {
    installFetch();
    render(<App />);
    await waitFor(() => expect(screen.getByText("19")).toBeTruthy());

    const sortButton = screen.getByRole("button", { name: /^This week/ });
    // First click: descending (highest first) and labeled as such.
    await act(async () => {
      fireEvent.click(sortButton);
    });
    expect(sortButton.closest("th")?.getAttribute("aria-sort")).toBe("descending");
    let rows = screen.getAllByRole("row").slice(1);
    expect(rows[0].querySelector("th")?.textContent).toBe("Site B"); // 15 > 4

    // Second click: ascending, order reverses, label follows.
    await act(async () => {
      fireEvent.click(sortButton);
    });
    expect(sortButton.closest("th")?.getAttribute("aria-sort")).toBe("ascending");
    rows = screen.getAllByRole("row").slice(1);
    expect(rows[0].querySelector("th")?.textContent).toBe("Site A"); // 4 < 15
  });

  it("expands a location into its 9-week history", async () => {
    installFetch();
    render(<App />);
    await waitFor(() => expect(screen.getByText("19")).toBeTruthy());

    const expand = screen.getAllByRole("button", { name: "Show history" })[0];
    await act(async () => {
      fireEvent.click(expand);
    });
    expect(expand.getAttribute("aria-expanded")).toBe("true");
    expect(screen.getByText(/First recorded activity: 2026-01-28/)).toBeTruthy();
    const historyItems = document.querySelectorAll(".week-history li");
    expect(historyItems.length).toBe(9);
  });

  it("shows an error state with retry that recovers", async () => {
    const { fetchMock } = installFetch({ failOnce: true });
    render(<App />);

    await waitFor(() => expect(screen.getByRole("alert")).toBeTruthy());
    expect(screen.getByRole("alert").textContent).toContain("internal error occurred");

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    });
    await waitFor(() => expect(screen.getByText("19")).toBeTruthy());
    expect(fetchMock.mock.calls.length).toBeGreaterThan(3);
  });

  it("degrades to the error boundary on a malformed response", async () => {
    // A 200 whose body is missing required fields must not blank the app.
    installFetch({ review: { ...reviewBody(), summary: undefined } });
    render(<App />);
    await waitFor(() =>
      expect(screen.getByRole("alert").textContent).toContain(
        "Something went wrong while displaying the review.",
      ),
    );
    expect(screen.getByRole("button", { name: "Reload the page" })).toBeTruthy();
  });

  it("renders the empty-account state without a table", async () => {
    installFetch({
      review: reviewBody({
        summary: { count: 0, reference: null, delta: null, percent_change: null, observed_min: null, observed_max: null, reason: "no_activity_recorded", classification_suppressed: false, weeks: [] },
        account_summary: { count: 0, reference: null, delta: null, percent_change: null, observed_min: null, observed_max: null, reason: "no_activity_recorded", classification_suppressed: false, weeks: [] },
        locations: [],
      }),
    });
    render(<App />);
    await waitFor(() =>
      expect(screen.getByText(/No activity has been recorded for Pacific Smiles/)).toBeTruthy(),
    );
    expect(screen.queryByRole("table")).toBeNull();
  });
});


it.each(["initial load", "history navigation"])("repairs invalid filters on %s", async (entry) => {
  installFetch();
  if (entry === "history navigation") {
    render(<App />);
    await waitFor(() => expect(screen.getByText("19")).toBeTruthy());
  }
  window.history.replaceState(null, "", "/?account=5&metric=garbage&location=Site+A#main");
  const historyLength = window.history.length;
  if (entry === "initial load") render(<App />);
  else await act(async () => window.dispatchEvent(new PopStateEvent("popstate")));
  await waitFor(() => expect(screen.getByText(/parameters were invalid and reset/)).toBeTruthy());
  expect(window.location.search).toBe("?account=5&location=Site+A");
  expect(window.location.hash).toBe("#main");
  expect(window.history.length).toBe(historyLength);
  await waitFor(() => expect(screen.getByText("19")).toBeTruthy());
  expect(screen.getByRole("button", { name: "Calls received" }).getAttribute("aria-pressed")).toBe("true");
  cleanup();
  render(<App />);
  await waitFor(() => expect(screen.getByText("19")).toBeTruthy());
  expect(screen.queryByText(/parameters were invalid/)).toBeNull();
});
