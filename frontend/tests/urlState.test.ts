import { describe, expect, it } from "vitest";
import {
  DEFAULT_METRIC,
  filtersToSearch,
  parseUrlFilters,
  type UrlFilters,
} from "../src/features/review/urlState";

describe("parseUrlFilters", () => {
  it("parses a fully-specified valid URL", () => {
    const { filters, invalid } = parseUrlFilters(
      "?account=5&week=2026-07-20&metric=lead_created&location=Site%20B",
    );
    expect(filters).toEqual({
      account: 5,
      week: "2026-07-20",
      metric: "lead_created",
      location: "Site B",
    });
    expect(invalid).toEqual([]);
  });

  it("defaults when nothing is set", () => {
    const { filters } = parseUrlFilters("");
    expect(filters).toEqual({
      account: null,
      week: null,
      metric: DEFAULT_METRIC,
      location: "",
    });
  });

  it("recovers from invalid values with a report", () => {
    const { filters, invalid } = parseUrlFilters(
      "?account=abc&week=2026-07-21&metric=churn",
    );
    expect(filters.account).toBeNull();
    expect(filters.week).toBeNull();
    expect(filters.metric).toBe(DEFAULT_METRIC);
    expect(invalid).toEqual(["account=abc", "week=2026-07-21", "metric=churn"]);
  });

  it("rejects non-Monday weeks even when well-formed", () => {
    const { filters, invalid } = parseUrlFilters("?week=2026-07-22");
    expect(filters.week).toBeNull();
    expect(invalid).toEqual(["week=2026-07-22"]);
  });
});

describe("filtersToSearch", () => {
  it("round-trips through parse", () => {
    const filters: UrlFilters = {
      account: 12,
      week: "2026-07-20",
      metric: "appointment_set",
      location: "Site F",
    };
    const search = filtersToSearch(filters);
    expect(parseUrlFilters(search).filters).toEqual(filters);
    expect(search).toBe("?account=12&week=2026-07-20&metric=appointment_set&location=Site+F");
  });

  it("omits defaults for shareable minimal URLs", () => {
    expect(filtersToSearch({ account: 5, week: null, metric: DEFAULT_METRIC, location: "" })).toBe(
      "?account=5",
    );
  });

  it("produces an empty string for fully-default state", () => {
    expect(
      filtersToSearch({ account: null, week: null, metric: DEFAULT_METRIC, location: "" }),
    ).toBe("");
  });
});
