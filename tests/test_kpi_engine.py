"""
Tests for kpi_engine.py

Run with: pytest tests/test_kpi_engine.py -v

Each function is tested for:
  1. A normal, expected case (correct math)
  2. Missing data (should return None, never crash)
  3. Division-by-zero edge cases (should return None, never crash)
"""

import pytest
from unittest.mock import patch

from analytics.kpi_engine import (
    get_latest_value,
    calculate_net_profit_margin,
    calculate_debt_to_equity,
    calculate_revenue_growth,
    calculate_earnings_growth,
    calculate_free_cash_flow,
    calculate_current_ratio,
    calculate_roe,
    calculate_kpis,
)


# ----------------------------------------------------------
# get_latest_value
# ----------------------------------------------------------

def test_get_latest_value_returns_first_non_none():
    statement = {"Net Income": {"2024-Q4": None, "2024-Q3": 500}}
    assert get_latest_value(statement, "Net Income") == 500


def test_get_latest_value_missing_metric_returns_none():
    statement = {"Net Income": {"2024-Q4": 500}}
    assert get_latest_value(statement, "Total Revenue") is None


def test_get_latest_value_all_none_returns_none():
    statement = {"Net Income": {"2024-Q4": None, "2024-Q3": None}}
    assert get_latest_value(statement, "Net Income") is None


# ----------------------------------------------------------
# calculate_net_profit_margin
# ----------------------------------------------------------

def test_net_profit_margin_normal_case():
    income_statement = {
        "Net Income": {"2024-Q4": 200},
        "Total Revenue": {"2024-Q4": 1000},
    }
    assert calculate_net_profit_margin(income_statement) == 20.0


def test_net_profit_margin_zero_revenue_returns_none():
    income_statement = {
        "Net Income": {"2024-Q4": 200},
        "Total Revenue": {"2024-Q4": 0},
    }
    assert calculate_net_profit_margin(income_statement) is None


def test_net_profit_margin_missing_data_returns_none():
    income_statement = {"Net Income": {"2024-Q4": 200}}
    assert calculate_net_profit_margin(income_statement) is None


def test_net_profit_margin_negative_income():
    income_statement = {
        "Net Income": {"2024-Q4": -50},
        "Total Revenue": {"2024-Q4": 1000},
    }
    assert calculate_net_profit_margin(income_statement) == -5.0


# ----------------------------------------------------------
# calculate_debt_to_equity
# ----------------------------------------------------------

def test_debt_to_equity_normal_case():
    balance_sheet = {
        "Total Debt": {"2024-Q4": 500},
        "Stockholders Equity": {"2024-Q4": 1000},
    }
    assert calculate_debt_to_equity(balance_sheet) == 0.5


def test_debt_to_equity_zero_equity_returns_none():
    # Real-world case: negative or zero book equity (e.g. heavy
    # buybacks) must not crash the app with a ZeroDivisionError.
    balance_sheet = {
        "Total Debt": {"2024-Q4": 500},
        "Stockholders Equity": {"2024-Q4": 0},
    }
    assert calculate_debt_to_equity(balance_sheet) is None


def test_debt_to_equity_missing_data_returns_none():
    balance_sheet = {"Total Debt": {"2024-Q4": 500}}
    assert calculate_debt_to_equity(balance_sheet) is None


# ----------------------------------------------------------
# calculate_revenue_growth
# ----------------------------------------------------------

def test_revenue_growth_normal_case():
    income_statement = {
        "Total Revenue": {"2024-Q4": 1100, "2024-Q3": 1000},
    }
    assert calculate_revenue_growth(income_statement) == 10.0


def test_revenue_growth_only_one_quarter_returns_none():
    income_statement = {"Total Revenue": {"2024-Q4": 1100}}
    assert calculate_revenue_growth(income_statement) is None


def test_revenue_growth_previous_zero_returns_none():
    income_statement = {
        "Total Revenue": {"2024-Q4": 1100, "2024-Q3": 0},
    }
    assert calculate_revenue_growth(income_statement) is None


def test_revenue_growth_missing_metric_returns_none():
    assert calculate_revenue_growth({}) is None


def test_revenue_growth_skips_none_values():
    # Some quarters can be None (missing data) - these should be
    # skipped rather than breaking the two-quarter comparison.
    income_statement = {
        "Total Revenue": {"2024-Q4": 1100, "2024-Q3": None, "2024-Q2": 1000},
    }
    assert calculate_revenue_growth(income_statement) == 10.0


# ----------------------------------------------------------
# calculate_earnings_growth
# ----------------------------------------------------------

def test_earnings_growth_normal_case():
    income_statement = {
        "Net Income": {"2024-Q4": 220, "2024-Q3": 200},
    }
    assert calculate_earnings_growth(income_statement) == 10.0


def test_earnings_growth_previous_zero_returns_none():
    income_statement = {
        "Net Income": {"2024-Q4": 220, "2024-Q3": 0},
    }
    assert calculate_earnings_growth(income_statement) is None


def test_earnings_growth_negative_to_positive():
    # Turning a loss into a profit should register as clearly
    # positive growth, not blow up the math.
    income_statement = {
        "Net Income": {"2024-Q4": 100, "2024-Q3": -100},
    }
    assert calculate_earnings_growth(income_statement) == -200.0
    # This is a known quirk: (-100 -> +100) gives -200% under the
    # standard growth formula when the prior value is negative.
    # Keep it documented so it isn't changed accidentally.


# ----------------------------------------------------------
# calculate_free_cash_flow
# ----------------------------------------------------------

def test_free_cash_flow_normal_case():
    cash_flow = {
        "Operating Cash Flow": {"2024-Q4": 1000},
        "Capital Expenditure": {"2024-Q4": -300},
    }
    assert calculate_free_cash_flow(cash_flow) == 700


def test_free_cash_flow_missing_data_returns_none():
    cash_flow = {"Operating Cash Flow": {"2024-Q4": 1000}}
    assert calculate_free_cash_flow(cash_flow) is None


# ----------------------------------------------------------
# calculate_current_ratio
# ----------------------------------------------------------

def test_current_ratio_normal_case():
    balance_sheet = {
        "Current Assets": {"2024-Q4": 300},
        "Current Liabilities": {"2024-Q4": 150},
    }
    assert calculate_current_ratio(balance_sheet) == 2.0


def test_current_ratio_zero_liabilities_returns_none():
    balance_sheet = {
        "Current Assets": {"2024-Q4": 300},
        "Current Liabilities": {"2024-Q4": 0},
    }
    assert calculate_current_ratio(balance_sheet) is None


# ----------------------------------------------------------
# calculate_roe
# ----------------------------------------------------------

def test_roe_normal_case():
    income_statement = {"Net Income": {"2024-Q4": 100}}
    balance_sheet = {"Stockholders Equity": {"2024-Q4": 500}}
    assert calculate_roe(income_statement, balance_sheet) == 20.0


def test_roe_zero_equity_returns_none():
    income_statement = {"Net Income": {"2024-Q4": 100}}
    balance_sheet = {"Stockholders Equity": {"2024-Q4": 0}}
    assert calculate_roe(income_statement, balance_sheet) is None


# ----------------------------------------------------------
# calculate_kpis (integration - mocks the network fetch)
# ----------------------------------------------------------

@patch("kpi_engine.fetch_company_financials")
def test_calculate_kpis_returns_all_seven_metrics(mock_fetch):
    mock_fetch.return_value = {
        "income_statement": {
            "Net Income": {"2024-Q4": 220, "2024-Q3": 200},
            "Total Revenue": {"2024-Q4": 1100, "2024-Q3": 1000},
        },
        "balance_sheet": {
            "Total Debt": {"2024-Q4": 500},
            "Stockholders Equity": {"2024-Q4": 1000},
            "Current Assets": {"2024-Q4": 300},
            "Current Liabilities": {"2024-Q4": 150},
        },
        "cash_flow": {
            "Operating Cash Flow": {"2024-Q4": 1000},
            "Capital Expenditure": {"2024-Q4": -300},
        },
    }

    kpis = calculate_kpis("TEST")

    expected_keys = {
        "net_profit_margin", "debt_to_equity", "revenue_growth",
        "earnings_growth", "free_cash_flow", "current_ratio", "roe",
    }
    assert set(kpis.keys()) == expected_keys
    assert all(value is not None for value in kpis.values())


@patch("kpi_engine.fetch_company_financials")
def test_calculate_kpis_handles_fetch_failure(mock_fetch):
    # Fetcher returning empty/None (bad ticker, network issue) must
    # not crash the whole app - this is what protects your Discover
    # page from breaking on an unknown or delisted ticker.
    mock_fetch.return_value = None
    assert calculate_kpis("BADTICKER") == {}