"""
Tests for health_score.py

This was previously the largest untested module in the project, and
also the one carrying the most weight in the UI - it produces the
single headline number on three of the four pages.

Run with: pytest tests/test_health_score.py -v
"""

import pytest

from analytics.health_score import (
    calculate_health_score,
    coverage_label,
    explain_score,
    get_score_label,
    score_coverage,
)


# A company scoring at the top of the default range on everything.
STRONG_KPIS = {
    "net_profit_margin": 25.0,
    "roe": 25.0,
    "revenue_growth": 20.0,
    "earnings_growth": 20.0,
    "debt_to_equity": 0.0,
    "current_ratio": 3.0,
    "fcf_margin": 20.0,
}

# The same company at the bottom of every range.
WEAK_KPIS = {
    "net_profit_margin": 0.0,
    "roe": 0.0,
    "revenue_growth": -10.0,
    "earnings_growth": -10.0,
    "debt_to_equity": 1.5,
    "current_ratio": 0.0,
    "fcf_margin": 0.0,
}


# ----------------------------------------------------------
# Scoring basics
# ----------------------------------------------------------

def test_best_case_scores_100():
    score, _ = calculate_health_score(STRONG_KPIS)
    assert score == 100.0


def test_worst_case_scores_0():
    score, _ = calculate_health_score(WEAK_KPIS)
    assert score == 0.0


def test_no_usable_data_returns_none():
    score, breakdown = calculate_health_score({})

    assert score is None
    assert breakdown == []


def test_values_outside_the_range_are_clamped_not_extrapolated():
    # An extraordinary metric shouldn't be able to drag the whole
    # score past 100 or paper over weakness elsewhere.
    extreme = dict(STRONG_KPIS, net_profit_margin=5000.0)
    score, _ = calculate_health_score(extreme)

    assert score == 100.0


def test_leverage_is_inverted_so_less_debt_scores_higher():
    low_debt = calculate_health_score({"debt_to_equity": 0.1})[0]
    high_debt = calculate_health_score({"debt_to_equity": 1.4})[0]

    assert low_debt > high_debt


def test_missing_metrics_are_renormalized_rather_than_scored_zero():
    # A company with only profitability data available should be
    # scored on what's known, not penalized for the gaps.
    score, breakdown = calculate_health_score({"net_profit_margin": 25.0})

    assert score == 100.0
    assert len(breakdown) == 1


# ----------------------------------------------------------
# Sector awareness
# ----------------------------------------------------------

def test_the_same_margin_scores_differently_across_sectors():
    kpis = {"net_profit_margin": 15.0}

    tech = calculate_health_score(kpis, sector="Technology")[0]
    consumer = calculate_health_score(kpis, sector="Consumer Cyclical")[0]

    # 15% margin is mid-range for tech (-5 to 30) and near the top for
    # consumer cyclical (-5 to 15).
    assert consumer > tech


def test_unknown_sector_falls_back_to_default_ranges():
    kpis = {"net_profit_margin": 12.5}

    unknown = calculate_health_score(kpis, sector="Not A Real Sector")[0]
    default = calculate_health_score(kpis, sector=None)[0]

    assert unknown == default


# ----------------------------------------------------------
# Cash generation
# ----------------------------------------------------------

def test_cash_generation_is_scored_on_margin_not_a_coin_flip():
    # Previously any positive FCF scored 100 and any negative scored
    # 0, so a business converting 20% of revenue to cash was rated
    # identically to one converting 0.5%.
    strong = calculate_health_score({"fcf_margin": 20.0})[0]
    thin = calculate_health_score({"fcf_margin": 0.5})[0]

    assert strong > thin


def test_cash_generation_falls_back_to_sign_without_revenue():
    positive = calculate_health_score({"free_cash_flow": 1_000_000})[0]
    negative = calculate_health_score({"free_cash_flow": -1_000_000})[0]

    assert positive == 100.0
    assert negative == 0.0


def test_fcf_margin_takes_precedence_over_the_raw_dollar_amount():
    kpis = {"free_cash_flow": 1_000_000, "fcf_margin": 0.0}

    # The dollar figure is positive, which the old rule scored as a
    # perfect 100; the margin says cash conversion is nil.
    score, breakdown = calculate_health_score(kpis)

    assert score == 0.0
    assert len(breakdown) == 1


# ----------------------------------------------------------
# Labels
# ----------------------------------------------------------

@pytest.mark.parametrize(
    "score, expected",
    [
        (95, "Excellent"),
        (70, "Strong"),
        (55, "Moderate"),
        (40, "Weak"),
        (10, "Poor"),
        (None, "N/A"),
    ],
)
def test_score_labels(score, expected):
    assert get_score_label(score)[0] == expected


# ----------------------------------------------------------
# Coverage
# ----------------------------------------------------------

def test_full_data_reports_complete_coverage():
    _, breakdown = calculate_health_score(STRONG_KPIS)

    assert score_coverage(breakdown) == pytest.approx(1.0)
    assert coverage_label(score_coverage(breakdown))[0] == "Complete data"


def test_thin_data_reports_low_coverage():
    # A score built from one metric is a much weaker claim than one
    # built from seven, even though both render as a number out of 100.
    _, breakdown = calculate_health_score({"net_profit_margin": 25.0})
    coverage = score_coverage(breakdown)

    assert coverage == pytest.approx(0.20)
    assert coverage_label(coverage)[0] == "Sparse data"


def test_coverage_of_nothing_is_zero():
    assert score_coverage([]) == 0.0


# ----------------------------------------------------------
# explain_score
# ----------------------------------------------------------

def test_explanation_names_the_weakest_metrics_as_drags():
    kpis = dict(STRONG_KPIS, debt_to_equity=1.5, current_ratio=0.0)
    _, breakdown = calculate_health_score(kpis)

    explanation = explain_score(breakdown)
    drag_metrics = [row["metric"] for row in explanation["drags"]]

    assert "debt_to_equity" in drag_metrics
    assert "current_ratio" in drag_metrics


def test_explanation_names_the_strongest_metrics_as_strengths():
    kpis = {"net_profit_margin": 25.0, "debt_to_equity": 1.5}
    _, breakdown = calculate_health_score(kpis)

    explanation = explain_score(breakdown)

    assert [row["metric"] for row in explanation["strengths"]] == ["net_profit_margin"]
    assert [row["metric"] for row in explanation["drags"]] == ["debt_to_equity"]


def test_a_perfect_company_has_no_drags():
    _, breakdown = calculate_health_score(STRONG_KPIS)
    explanation = explain_score(breakdown)

    assert explanation["drags"] == []
    assert explanation["strengths"]


def test_contributions_sum_to_the_score():
    score, breakdown = calculate_health_score(
        {"net_profit_margin": 20.0, "roe": 10.0, "current_ratio": 1.5}
    )
    explanation = explain_score(breakdown, limit=10)

    total = sum(
        row["contribution"]
        for row in explanation["strengths"] + explanation["drags"]
    )
    assert total == pytest.approx(score, abs=0.05)


def test_explanation_carries_display_labels():
    _, breakdown = calculate_health_score({"net_profit_margin": 25.0})
    explanation = explain_score(breakdown)

    assert explanation["strengths"][0]["label"] == "Profit Margin"


def test_explaining_an_empty_breakdown_is_safe():
    explanation = explain_score([])

    assert explanation == {"strengths": [], "drags": [], "coverage": 0.0}
