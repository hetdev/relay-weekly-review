"""Comparison policy unit tests — every expected value hand-calculated."""

from __future__ import annotations

import pytest

from app.reviews.policy import PolicyConfig, classify, rank_key

CONFIG = PolicyConfig()
pytestmark = pytest.mark.unit


def result(count, weeks, observed=True):
    return classify(
        CONFIG,
        count=count,
        covered_baseline_counts=tuple(weeks),
        first_observed_before_baseline=observed,
    )


class TestCoreArithmetic:
    def test_exact_mean_range_delta_percent(self):
        # weeks 4,6,8,10,12,14,16,18 -> sum 88, mean 11, range [4,18]
        r = result(15, [4, 6, 8, 10, 12, 14, 16, 18])
        assert r.reason == "no_review_flag"
        assert r.reference == 11.0
        assert r.delta == 4.0
        assert r.percent_change == pytest.approx(100 * 4 / 11)
        assert r.observed_min == 4
        assert r.observed_max == 18

    @pytest.mark.parametrize("count, expected_percent", [(0, -100.0), (50, 4900.0)])
    def test_zero_baseline_buckets_contribute_to_the_average(self, count, expected_percent):
        # Sum 8 / eight weeks = 1, including the zero week. A positive
        # reference must produce a number, not merely 'None or finite'.
        r = result(count, [1, 0, 2, 1, 1, 1, 1, 1])
        assert r.reference == 1.0
        assert r.percent_change == expected_percent


class TestRuleOrder:
    @pytest.mark.parametrize("count, weeks, observed", [
        (50, [10] * 7, True),
        (0, [], True),
        (0, [0] * 7, True),  # insufficient history precedes the zero rule
        (50, [10] * 8, False),
    ])
    def test_incomplete_or_unobserved_history_suppresses_comparison(self, count, weeks, observed):
        r = result(count, weeks, observed)
        assert r.reason == "insufficient_history"
        assert r.reference is None and r.delta is None and r.percent_change is None
        assert r.observed_min is None and r.observed_max is None

    def test_rule3_no_recent_activity(self):
        r = result(0, [0] * 8)
        assert r.reason == "no_recent_activity"
        assert r.percent_change is None  # never 0/0
        assert r.reference == 0.0 and r.delta == 0.0

    def test_rule3_activity_after_zero_baseline(self):
        r = result(7, [0] * 8)
        assert r.reason == "activity_after_zero_baseline"
        assert r.percent_change is None  # never infinity
        assert r.delta == 7.0

    def test_rule4_low_volume_precedes_range_rules(self):
        # reference 2 < 5; a fivefold jump would otherwise meet range thresholds
        r = result(10, [2] * 8)
        assert r.reason == "low_volume"
        assert r.percent_change == pytest.approx(100 * 8 / 2)  # arithmetic still shown
        assert r.observed_min == 2 and r.observed_max == 2


class TestThresholdBoundaries:
    @pytest.mark.parametrize("count, expected_reason", [
        (5, "below_recent_range"),
        (6, "no_review_flag"),
        (14, "no_review_flag"),
        (15, "above_recent_range"),
    ])
    def test_absolute_threshold_both_directions(self, count, expected_reason):
        # Every move exceeds 20%; only the five-event boundary decides.
        assert result(count, [10] * 8).reason == expected_reason

    @pytest.mark.parametrize("count, weeks, expected_reason", [
        (20, [25] + [30] * 7, "below_recent_range"),  # exactly 20% of min
        (25, [30] + [35] * 7, "no_review_flag"),      # five events, below 20%
        (30, [25] + [20] * 7, "above_recent_range"), # exactly 20% of max
        (35, [30] + [20] * 7, "no_review_flag"),     # five events, below 20%
    ])
    def test_relative_threshold_uses_range_edge_not_mean(self, count, weeks, expected_reason):
        assert result(count, weeks).reason == expected_reason

    def test_reference_exactly_five_is_not_low_volume(self):
        # "below five" — exactly five classifies normally
        assert result(5, [5] * 8).reason == "no_review_flag"


class TestInputValidation:
    def test_more_than_eight_weeks_rejected(self):
        with pytest.raises(ValueError):
            result(1, [1] * 9)

    def test_negative_baseline_counts_rejected(self):
        with pytest.raises(ValueError):
            result(1, [1, -1, 1, 1, 1, 1, 1, 1])


class TestRanking:
    def test_decreases_before_increases_before_others(self):
        below = rank_key("Zeta", "below_recent_range", 4, 10, 10)
        above = rank_key("Alpha", "above_recent_range", 20, 10, 10)
        other = rank_key("Beta", "no_review_flag", 10, 10, 10)
        assert below < above < other

    def test_decreases_ordered_by_absolute_shortfall(self):
        big_drop = rank_key("B", "below_recent_range", 0, 20, 20)  # shortfall 20
        small_drop = rank_key("A", "below_recent_range", 8, 10, 10)  # shortfall 2
        assert big_drop < small_drop

    def test_increases_ordered_by_absolute_rise(self):
        big_rise = rank_key("B", "above_recent_range", 40, 10, 10)
        small_rise = rank_key("A", "above_recent_range", 15, 10, 10)
        assert big_rise < small_rise

    def test_ties_broken_deterministically_by_name(self):
        assert rank_key("A", "no_review_flag", 1, 1, 1) < rank_key("B", "no_review_flag", 1, 1, 1)

    def test_unclassified_rows_sort_within_others(self):
        suppressed = rank_key("C", None, 99, None, None)
        normal = rank_key("B", "no_review_flag", 10, 10, 10)
        flagged = rank_key("Z", "above_recent_range", 20, 10, 10)
        assert flagged < normal < suppressed
