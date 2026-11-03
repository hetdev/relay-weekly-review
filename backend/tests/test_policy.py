"""Comparison policy unit tests — every expected value hand-calculated."""

from __future__ import annotations

import math

import pytest

from app.reviews.policy import PolicyConfig, classify, rank_key

CONFIG = PolicyConfig()


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

    def test_baseline_mean_excludes_target_week(self):
        # The caller passes only w1..w8; verify no implicit target inclusion
        r = result(1000, [10, 10, 10, 10, 10, 10, 10, 10])
        assert r.reference == 10.0  # not (80+1000)/9
        assert r.percent_change == pytest.approx(100 * 990 / 10)

    def test_percent_is_finite_whenever_reference_positive(self):
        for count in (0, 1, 50):
            r = result(count, [1, 0, 2, 1, 1, 1, 1, 1])
            assert r.percent_change is None or math.isfinite(r.percent_change)


class TestRuleOrder:
    def test_rule2_insufficient_when_fewer_than_eight_covered_weeks(self):
        r = result(50, [10] * 7)
        assert r.reason == "insufficient_history"
        assert r.reference is None and r.delta is None and r.percent_change is None
        assert r.observed_min is None and r.observed_max is None

    def test_rule2_insufficient_when_first_observed_inside_baseline(self):
        r = result(50, [10] * 8, observed=False)
        assert r.reason == "insufficient_history"
        assert r.reference is None

    def test_rule2_precedes_zero_rules(self):
        r = result(0, [0] * 7)
        assert r.reason == "insufficient_history"

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
        # reference 2 < 5; a 10x jump would flag on rules 5/6 but must not
        r = result(10, [2] * 8)
        assert r.reason == "low_volume"
        assert r.percent_change == pytest.approx(100 * 8 / 2)  # arithmetic still shown
        assert r.observed_min == 2 and r.observed_max == 2

    def test_rule5_below_recent_range(self):
        r = result(4, [10] * 8)  # drop 6 >= 5, 60% >= 20%
        assert r.reason == "below_recent_range"
        assert r.reference == 10.0 and r.delta == -6.0

    def test_rule6_above_recent_range(self):
        r = result(20, [10] * 8)  # increase 10 >= 5, 100% >= 20%
        assert r.reason == "above_recent_range"

    def test_rule7_no_review_flag_within_range(self):
        assert result(10, [10] * 8).reason == "no_review_flag"


class TestThresholdBoundaries:
    def test_drop_exactly_five_events_flags(self):
        assert result(5, [10] * 8).reason == "below_recent_range"  # drop exactly 5

    def test_drop_four_events_does_not_flag(self):
        # drop 4 < 5 even though 40% >= 20%
        assert result(6, [10] * 8).reason == "no_review_flag"

    def test_relative_drop_exactly_twenty_percent_flags(self):
        # min(w)=25, c=20: drop 5, relative 5/25 = 20% exactly
        weeks = [25, 30, 30, 30, 30, 30, 30, 30]
        assert result(20, weeks).reason == "below_recent_range"

    def test_relative_increase_exactly_twenty_percent_flags(self):
        weeks = [25, 20, 20, 20, 20, 20, 20, 20]  # max 25
        assert result(30, weeks).reason == "above_recent_range"  # increase 5 = 20% of 25

    def test_below_range_but_small_drop_not_flagged(self):
        # min 10, c 7: drop 3 < 5
        assert result(7, [10, 10, 10, 10, 10, 10, 10, 10]).reason == "no_review_flag"

    def test_reference_exactly_five_is_not_low_volume(self):
        # "below five" — exactly five classifies normally
        assert result(5, [5] * 8).reason == "no_review_flag"


class TestInputValidation:
    def test_more_than_eight_weeks_rejected(self):
        with pytest.raises(ValueError):
            result(1, [1] * 9)

    def test_negative_counts_rejected(self):
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
        assert suppressed[0] == 2  # same group as no_review_flag
