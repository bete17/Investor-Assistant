"""
Tests for market_fetcher.py

Only the normalization layer is tested here - the network fetch
itself isn't worth mocking end to end, but the shaping of yfinance's
famously inconsistent info blob absolutely is. Every bug this catches
is a wrong number rendered confidently on the page.

Run with: pytest tests/test_market_fetcher.py -v
"""

import pytest

from data.market_fetcher import (
    _build_snapshot,
    _coerce_number,
    _position_in_52_week_range,
    _resolve_dividend_yield,
)


# ----------------------------------------------------------
# _coerce_number
# ----------------------------------------------------------

@pytest.mark.parametrize(
    "raw, expected",
    [
        (12.5, 12.5),
        (12, 12.0),
        ("12.5", 12.5),
        (None, None),
        ("", None),
        ("N/A", None),
        (float("nan"), None),
        (float("inf"), None),
        (float("-inf"), None),
        (True, None),  # bools are ints in Python; never a valid price
    ],
)
def test_coerce_number(raw, expected):
    assert _coerce_number(raw) == expected


# ----------------------------------------------------------
# Dividend yield units
# ----------------------------------------------------------

def test_yield_is_computed_from_rate_and_price_when_possible():
    # yfinance has changed dividendYield between a fraction and a
    # percentage across releases, and the ambiguous band around 0.5-1.0
    # can't be resolved by magnitude. Rate over price has unambiguous
    # units, so prefer it whenever both are present.
    snapshot = {"dividend_rate": 1.0, "price": 200.0, "dividend_yield_raw": 999}

    assert _resolve_dividend_yield(snapshot) == pytest.approx(0.5)


def test_yield_falls_back_to_the_reported_field():
    snapshot = {"dividend_rate": None, "price": None, "dividend_yield_raw": 2.4}

    assert _resolve_dividend_yield(snapshot) == 2.4


def test_implausible_reported_yield_is_rejected():
    # A yield over 100% is a unit error, not a real payout.
    snapshot = {"dividend_rate": None, "price": None, "dividend_yield_raw": 250}

    assert _resolve_dividend_yield(snapshot) is None


def test_no_dividend_data_yields_none():
    assert _resolve_dividend_yield({}) is None


def test_zero_price_does_not_divide_by_zero():
    snapshot = {"dividend_rate": 1.0, "price": 0}

    assert _resolve_dividend_yield(snapshot) is None


# ----------------------------------------------------------
# 52-week range position
# ----------------------------------------------------------

def test_range_position_maps_low_to_zero_and_high_to_one_hundred():
    assert _position_in_52_week_range({
        "price": 50, "fifty_two_week_low": 50, "fifty_two_week_high": 150,
    }) == 0.0

    assert _position_in_52_week_range({
        "price": 150, "fifty_two_week_low": 50, "fifty_two_week_high": 150,
    }) == 100.0

    assert _position_in_52_week_range({
        "price": 100, "fifty_two_week_low": 50, "fifty_two_week_high": 150,
    }) == 50.0


def test_price_outside_the_band_is_clamped():
    # An intraday print can exceed the trailing 52-week high before
    # that figure updates; showing "104% of range" would look broken.
    assert _position_in_52_week_range({
        "price": 160, "fifty_two_week_low": 50, "fifty_two_week_high": 150,
    }) == 100.0


def test_degenerate_range_returns_none():
    assert _position_in_52_week_range({
        "price": 100, "fifty_two_week_low": 100, "fifty_two_week_high": 100,
    }) is None


def test_missing_range_data_returns_none():
    assert _position_in_52_week_range({"price": 100}) is None


# ----------------------------------------------------------
# _build_snapshot
# ----------------------------------------------------------

def test_snapshot_normalizes_a_realistic_info_blob():
    info = {
        "longName": "Example Corp",
        "currency": "USD",
        "currentPrice": 110.0,
        "regularMarketPreviousClose": 100.0,
        "marketCap": 500_000_000_000,
        "trailingPE": 25.0,
        "forwardPE": 20.0,
        "priceToSalesTrailing12Months": 6.0,
        "priceToBook": 12.0,
        "dividendRate": 2.2,
        "fiftyTwoWeekHigh": 120.0,
        "fiftyTwoWeekLow": 80.0,
    }

    snapshot = _build_snapshot("exmpl", info)

    assert snapshot["ticker"] == "EXMPL"
    assert snapshot["name"] == "Example Corp"
    assert snapshot["price"] == 110.0
    assert snapshot["price_change"] == pytest.approx(10.0)
    assert snapshot["price_change_percent"] == pytest.approx(10.0)
    assert snapshot["dividend_yield"] == pytest.approx(2.0)
    assert snapshot["range_position"] == pytest.approx(75.0)


def test_snapshot_survives_a_sparse_info_blob():
    # Recent IPOs, ADRs and lossmaking companies legitimately lack
    # most of these fields. A missing field must never raise.
    snapshot = _build_snapshot("NEW", {"shortName": "New Co"})

    assert snapshot["ticker"] == "NEW"
    assert snapshot["name"] == "New Co"
    assert snapshot["price"] is None
    assert snapshot["trailing_pe"] is None
    assert snapshot["price_change"] is None
    assert snapshot["range_position"] is None


def test_snapshot_falls_back_through_price_fields():
    # currentPrice is absent outside market hours for some tickers.
    snapshot = _build_snapshot("TEST", {"previousClose": 42.0})

    assert snapshot["price"] == 42.0


def test_snapshot_discards_the_raw_yield_field():
    # The ambiguous field must not leak into the UI layer, where its
    # units would be guessed at all over again.
    snapshot = _build_snapshot("TEST", {"dividendYield": 1.5})

    assert "dividend_yield_raw" not in snapshot
    assert snapshot["dividend_yield"] == 1.5
