"""
Tests for valuation.py

The important behaviours here are the ones that stop the app from
saying something financially wrong:

  - a negative P/E is "no earnings", never "cheap"
  - a multiple is judged against its own sector, not a fixed number
  - reads with no data behind them are omitted, not rendered blank

Run with: pytest tests/test_valuation.py -v
"""

import pytest

from analytics.valuation import (
    build_valuation_reads,
    classify_pe,
    describe_range_position,
    earnings_yield,
    get_pe_band,
    growth_adjusted_read,
    market_cap_tier,
)


# ----------------------------------------------------------
# classify_pe
# ----------------------------------------------------------

def test_negative_pe_is_reported_as_no_earnings_not_cheap():
    # The single most important case in this module: a lossmaking
    # company has the lowest possible P/E, and calling that "cheap"
    # would invert the meaning entirely.
    label, status, explanation = classify_pe(-14.0, "Technology")

    assert label == "No earnings"
    assert status == "warning"
    assert "not the same as being cheap" in explanation


def test_zero_pe_is_treated_the_same_as_negative():
    label, _, _ = classify_pe(0, "Technology")
    assert label == "No earnings"


def test_missing_pe_reports_unavailable():
    label, status, _ = classify_pe(None, "Technology")

    assert label == "Not available"
    assert status == "neutral"


def test_same_pe_is_judged_differently_by_sector():
    # 25x is ordinary for software and expensive for a bank. A single
    # fixed threshold would call one of those wrong.
    tech_label, _, _ = classify_pe(25.0, "Technology")
    bank_label, _, _ = classify_pe(25.0, "Financial Services")

    assert tech_label == "In line with sector"
    assert bank_label in ("Above sector norm", "Richly valued")


def test_low_pe_flags_below_sector_norm():
    label, status, _ = classify_pe(10.0, "Technology")

    assert label == "Below sector norm"
    assert status == "positive"


def test_extreme_pe_flags_richly_valued():
    label, status, _ = classify_pe(200.0, "Technology")

    assert label == "Richly valued"
    assert status == "negative"


def test_unknown_sector_falls_back_to_a_general_band():
    assert get_pe_band("Nonexistent Sector") == get_pe_band(None)

    label, _, _ = classify_pe(18.0, None)
    assert label == "In line with sector"


# ----------------------------------------------------------
# earnings_yield
# ----------------------------------------------------------

def test_earnings_yield_inverts_the_multiple():
    assert earnings_yield(20.0) == pytest.approx(5.0)


def test_earnings_yield_undefined_without_earnings():
    assert earnings_yield(None) is None
    assert earnings_yield(-10.0) is None
    assert earnings_yield(0) is None


# ----------------------------------------------------------
# market_cap_tier
# ----------------------------------------------------------

@pytest.mark.parametrize(
    "market_cap, expected",
    [
        (3_000_000_000_000, "Mega cap"),
        (50_000_000_000, "Large cap"),
        (5_000_000_000, "Mid cap"),
        (900_000_000, "Small cap"),
        (100_000_000, "Micro cap"),
    ],
)
def test_market_cap_tiers(market_cap, expected):
    assert market_cap_tier(market_cap) == expected


def test_market_cap_tier_handles_missing_data():
    assert market_cap_tier(None) is None
    assert market_cap_tier(0) is None


# ----------------------------------------------------------
# describe_range_position
# ----------------------------------------------------------

def test_range_position_descriptions_are_descriptive_not_predictive():
    assert describe_range_position(95) == "Trading near its 52-week high"
    assert describe_range_position(5) == "Trading near its 52-week low"
    assert describe_range_position(50) == "Around the middle of its 52-week range"
    assert describe_range_position(None) is None


# ----------------------------------------------------------
# growth_adjusted_read
# ----------------------------------------------------------

def test_high_multiple_on_high_growth_is_not_penalized():
    label, status, _ = growth_adjusted_read(40.0, 60.0)

    assert label == "Growth exceeds the multiple"
    assert status == "positive"


def test_high_multiple_on_flat_growth_is_flagged():
    label, status, _ = growth_adjusted_read(40.0, 3.0)

    assert label == "Multiple runs ahead of growth"
    assert status == "warning"


def test_paying_a_multiple_for_shrinking_revenue_is_flagged():
    label, status, _ = growth_adjusted_read(30.0, -5.0)

    assert label == "Paying up without growth"
    assert status == "warning"


def test_growth_adjusted_read_needs_both_inputs():
    assert growth_adjusted_read(None, 20.0) is None
    assert growth_adjusted_read(20.0, None) is None
    assert growth_adjusted_read(-5.0, 20.0) is None


# ----------------------------------------------------------
# build_valuation_reads
# ----------------------------------------------------------

def test_reads_omit_observations_with_no_data_behind_them():
    # A page of "N/A" rows reads as broken. A shorter page reads as
    # honest, so anything unsupported is left out entirely.
    snapshot = {"ticker": "TEST", "trailing_pe": 20.0}
    reads = build_valuation_reads(snapshot, sector="Technology", kpis={})

    titles = [read["title"] for read in reads]

    assert "Price to earnings" in titles
    assert "Dividend" not in titles
    assert "52-week range" not in titles


def test_reads_include_every_supported_observation():
    snapshot = {
        "ticker": "TEST",
        "trailing_pe": 20.0,
        "forward_pe": 16.0,
        "dividend_yield": 2.5,
        "range_position": 80.0,
    }
    reads = build_valuation_reads(
        snapshot, sector="Technology", kpis={"revenue_growth": 15.0}
    )

    titles = [read["title"] for read in reads]

    assert titles == [
        "Price to earnings",
        "Multiple vs. growth",
        "Forward expectations",
        "Dividend",
        "52-week range",
    ]


def test_forward_multiple_below_trailing_signals_expected_growth():
    snapshot = {"trailing_pe": 25.0, "forward_pe": 18.0}
    reads = build_valuation_reads(snapshot, sector="Technology")

    forward = next(r for r in reads if r["title"] == "Forward expectations")

    assert forward["label"] == "Earnings expected to rise"
    assert forward["status"] == "positive"


def test_forward_multiple_above_trailing_signals_expected_decline():
    snapshot = {"trailing_pe": 18.0, "forward_pe": 25.0}
    reads = build_valuation_reads(snapshot, sector="Technology")

    forward = next(r for r in reads if r["title"] == "Forward expectations")

    assert forward["label"] == "Earnings expected to fall"


def test_reit_pe_carries_an_ffo_caveat():
    snapshot = {"trailing_pe": 30.0}
    reads = build_valuation_reads(snapshot, sector="Real Estate")

    assert "funds from operations" in reads[0]["explanation"]


def test_empty_snapshot_produces_no_reads():
    assert build_valuation_reads({}) == []
    assert build_valuation_reads(None) == []
