"""
Tests for the TTM / year-over-year conventions in kpi_engine.py.

These cover the behaviour that makes the KPI numbers trustworthy
rather than merely present:

  - level metrics are trailing-twelve-month, not one quarter
  - growth compares against the same quarter a year earlier, so a
    seasonal business isn't reported as declining every year
  - a percentage is withheld where it would invert the meaning

Run with: pytest tests/test_kpi_periods.py -v
"""

import pytest

from analytics.kpi_engine import (
    calculate_earnings_growth,
    calculate_earnings_swing,
    calculate_fcf_margin,
    calculate_free_cash_flow,
    calculate_net_profit_margin,
    calculate_revenue_growth,
    calculate_revenue_growth_detailed,
    calculate_roe,
    describe_swing,
    get_ttm_value,
)


# A seasonal business modelled on a consumer hardware company: the
# holiday quarter is roughly double the spring quarter, every year.
# Sequential growth calls this a collapse; year-over-year calls it
# the 10% growth it actually is.
SEASONAL_REVENUE = {
    "Total Revenue": {
        "2025-03-31": 95_000,   # latest: spring
        "2024-12-31": 190_000,  # prior: holiday
        "2024-09-30": 90_000,
        "2024-06-30": 85_000,
        "2024-03-31": 86_364,   # same quarter, prior year
        "2023-12-31": 175_000,
    }
}


# ----------------------------------------------------------
# get_ttm_value
# ----------------------------------------------------------

def test_ttm_sums_four_quarters():
    statement = {
        "Revenue": {
            "2025-03-31": 100,
            "2024-12-31": 200,
            "2024-09-30": 300,
            "2024-06-30": 400,
            "2024-03-31": 999,  # fifth quarter must be excluded
        }
    }
    assert get_ttm_value(statement, "Revenue") == (1000, "ttm")


def test_ttm_falls_back_to_latest_quarter_when_history_is_short():
    statement = {"Revenue": {"2025-03-31": 100, "2024-12-31": 200}}
    value, basis = get_ttm_value(statement, "Revenue")

    assert value == 100
    assert basis == "quarter"


def test_ttm_with_no_data_returns_none():
    assert get_ttm_value({}, "Revenue") == (None, None)


def test_ttm_ignores_missing_quarters():
    statement = {
        "Revenue": {
            "2025-03-31": 100,
            "2024-12-31": None,
            "2024-09-30": 300,
        }
    }
    value, basis = get_ttm_value(statement, "Revenue")

    assert value == 100
    assert basis == "quarter"


# ----------------------------------------------------------
# Year-over-year growth
# ----------------------------------------------------------

def test_revenue_growth_is_year_over_year_not_sequential():
    # Sequential would report -50% for this seasonal business. The
    # honest answer is +10% against the same quarter last year.
    growth = calculate_revenue_growth(SEASONAL_REVENUE)

    assert growth == pytest.approx(10.0, abs=0.01)


def test_revenue_growth_reports_yoy_basis():
    _, basis = calculate_revenue_growth_detailed(SEASONAL_REVENUE)
    assert basis == "yoy"


def test_growth_falls_back_to_sequential_without_a_year_of_history():
    statement = {"Total Revenue": {"2025-03-31": 110, "2024-12-31": 100}}
    value, basis = calculate_revenue_growth_detailed(statement)

    assert value == pytest.approx(10.0)
    assert basis == "sequential"


def test_growth_falls_back_to_sequential_when_dates_are_unparseable():
    # Fake/opaque period keys can't support a date-delta comparison,
    # so we must not silently claim a year-over-year read.
    statement = {"Total Revenue": {"2024-Q4": 110, "2024-Q3": 100}}
    value, basis = calculate_revenue_growth_detailed(statement)

    assert value == pytest.approx(10.0)
    assert basis == "sequential"


def test_growth_tolerates_a_shifted_fiscal_calendar():
    # 52/53-week fiscal years mean the "same" quarter can land a
    # couple of weeks either side of a clean 365 days.
    statement = {
        "Total Revenue": {
            "2025-03-29": 110,
            "2024-12-28": 500,
            "2024-09-28": 400,
            "2024-06-29": 300,
            "2024-03-30": 100,  # 364 days back
        }
    }
    value, basis = calculate_revenue_growth_detailed(statement)

    assert value == pytest.approx(10.0)
    assert basis == "yoy"


def test_growth_skips_a_missing_year_ago_quarter():
    statement = {
        "Total Revenue": {
            "2025-03-31": 110,
            "2024-12-31": 500,
            "2024-09-30": 400,
            "2024-06-30": 300,
            "2024-03-31": None,  # dropped, so no year-ago match exists
        }
    }
    _, basis = calculate_revenue_growth_detailed(statement)

    assert basis == "sequential"


# ----------------------------------------------------------
# Growth off a negative base
# ----------------------------------------------------------

def test_earnings_growth_withholds_a_percentage_after_a_loss():
    # -100 -> +100 yields -200% under the standard formula, which the
    # UI would render as "earnings are declining" for unambiguously
    # good news. No percentage is better than an inverted one.
    statement = {
        "Net Income": {
            "2025-03-31": 100,
            "2024-12-31": 50,
            "2024-09-30": 40,
            "2024-06-30": 30,
            "2024-03-31": -100,
        }
    }
    assert calculate_earnings_growth(statement) is None


def test_earnings_swing_describes_what_the_percentage_cannot():
    statement = {
        "Net Income": {
            "2025-03-31": 100,
            "2024-12-31": 50,
            "2024-09-30": 40,
            "2024-06-30": 30,
            "2024-03-31": -100,
        }
    }
    assert calculate_earnings_swing(statement) == "Swung from a loss to a profit"


def test_earnings_swing_is_silent_when_a_percentage_works():
    statement = {"Net Income": {"2025-03-31": 110, "2024-12-31": 100}}
    assert calculate_earnings_swing(statement) is None


@pytest.mark.parametrize(
    "current, previous, expected",
    [
        (100, -50, "Swung from a loss to a profit"),
        (-20, -80, "Still lossmaking, but the loss narrowed"),
        (-80, -20, "Loss widened"),
        (-50, -50, "Loss unchanged"),
        (-10, 0, "Prior period was breakeven"),
        (10, 0, "Turned profitable from a breakeven prior period"),
        (110, 100, None),
    ],
)
def test_describe_swing_covers_every_sign_combination(current, previous, expected):
    assert describe_swing(current, previous) == expected


# ----------------------------------------------------------
# TTM level metrics
# ----------------------------------------------------------

def test_net_profit_margin_uses_trailing_twelve_months():
    statement = {
        "Net Income": {
            "2025-03-31": 25, "2024-12-31": 25,
            "2024-09-30": 25, "2024-06-30": 25,
        },
        "Total Revenue": {
            "2025-03-31": 100, "2024-12-31": 100,
            "2024-09-30": 100, "2024-06-30": 100,
        },
    }
    # 100 / 400 == 25%, same as any single quarter here - the point is
    # that both sides are summed over the same four quarters.
    assert calculate_net_profit_margin(statement) == pytest.approx(25.0)


def test_net_profit_margin_refuses_to_mix_periods():
    # Four quarters of income over one quarter of revenue would report
    # a ~4x inflated margin. Better to report nothing.
    statement = {
        "Net Income": {
            "2025-03-31": 25, "2024-12-31": 25,
            "2024-09-30": 25, "2024-06-30": 25,
        },
        "Total Revenue": {"2025-03-31": 100},
    }
    assert calculate_net_profit_margin(statement) is None


def test_roe_uses_ttm_income_against_average_equity():
    income_statement = {
        "Net Income": {
            "2025-03-31": 100, "2024-12-31": 100,
            "2024-09-30": 100, "2024-06-30": 100,
        }
    }
    balance_sheet = {
        "Stockholders Equity": {
            "2025-03-31": 2200,
            "2024-12-31": 2100,
            "2024-09-30": 2000,
            "2024-06-30": 1900,
            "2024-03-31": 1800,
        }
    }
    # TTM income 400 / average equity ((2200 + 1800) / 2 = 2000) = 20%.
    # Scoring one quarter (100) against the latest balance would have
    # produced 4.5%, against sector ranges built from annual data.
    assert calculate_roe(income_statement, balance_sheet) == pytest.approx(20.0)


def test_roe_returns_none_on_negative_book_equity():
    # Buyback-heavy companies can carry negative book equity. Positive
    # earnings over negative equity produces a large negative ROE that
    # reads as catastrophic when it's an accounting artifact.
    income_statement = {"Net Income": {"2025-03-31": 100}}
    balance_sheet = {"Stockholders Equity": {"2025-03-31": -500}}

    assert calculate_roe(income_statement, balance_sheet) is None


def test_free_cash_flow_is_trailing_twelve_months():
    cash_flow = {
        "Operating Cash Flow": {
            "2025-03-31": 1000, "2024-12-31": 1000,
            "2024-09-30": 1000, "2024-06-30": 1000,
        },
        "Capital Expenditure": {
            "2025-03-31": -300, "2024-12-31": -300,
            "2024-09-30": -300, "2024-06-30": -300,
        },
    }
    assert calculate_free_cash_flow(cash_flow) == 2800


def test_free_cash_flow_refuses_to_mix_periods():
    cash_flow = {
        "Operating Cash Flow": {
            "2025-03-31": 1000, "2024-12-31": 1000,
            "2024-09-30": 1000, "2024-06-30": 1000,
        },
        "Capital Expenditure": {"2025-03-31": -300},
    }
    assert calculate_free_cash_flow(cash_flow) is None


def test_fcf_margin_expresses_cash_conversion():
    cash_flow = {
        "Operating Cash Flow": {
            "2025-03-31": 300, "2024-12-31": 300,
            "2024-09-30": 300, "2024-06-30": 300,
        },
        "Capital Expenditure": {
            "2025-03-31": -100, "2024-12-31": -100,
            "2024-09-30": -100, "2024-06-30": -100,
        },
    }
    income_statement = {
        "Total Revenue": {
            "2025-03-31": 1000, "2024-12-31": 1000,
            "2024-09-30": 1000, "2024-06-30": 1000,
        }
    }
    # TTM FCF 800 on TTM revenue 4000 = 20% cash conversion.
    assert calculate_fcf_margin(cash_flow, income_statement) == pytest.approx(20.0)


def test_fcf_margin_returns_none_without_revenue():
    cash_flow = {
        "Operating Cash Flow": {"2025-03-31": 300},
        "Capital Expenditure": {"2025-03-31": -100},
    }
    assert calculate_fcf_margin(cash_flow, {}) is None
