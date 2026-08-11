"""
End-to-end smoke tests for the Streamlit pages.

Streamlit pages are scripts, so nothing about them is exercised by
unit tests - a NameError or a bad f-string in the page body only
shows up when someone loads the page. These run each page headlessly
through Streamlit's AppTest harness and assert it renders without
raising.

Network access is avoided entirely by pre-seeding the on-disk caches
that every fetcher checks first, so these tests describe a realistic
company without ever calling Yahoo Finance.

Run with: pytest tests/test_dashboard_smoke.py -v
"""

import json
import os
from datetime import datetime, timedelta, timezone

import pytest

pytest.importorskip("streamlit.testing.v1", reason="requires Streamlit's test harness")

from streamlit.testing.v1 import AppTest  # noqa: E402

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_DIR = os.path.join(PROJECT_ROOT, "data", "cache")
DASHBOARD = os.path.join(PROJECT_ROOT, "UI", "kpi_dashboard.py")
COMPARE_PAGE = os.path.join(PROJECT_ROOT, "UI", "pages", "1_compare_stocks.py")
STORYLINE_PAGE = os.path.join(PROJECT_ROOT, "UI", "pages", "2_storyline.py")
DISCOVER_PAGE = os.path.join(PROJECT_ROOT, "UI", "pages", "3_discover.py")

# A real ticker, so ticker_fetcher resolves it, with entirely
# synthetic financials behind it.
TICKER = "AAPL"
PEER_TICKER = "MSFT"

# Four quarters plus the year-ago comparison quarter, with a
# deliberately seasonal revenue shape: the holiday quarter is roughly
# double the spring one. On the old sequential basis this company
# reported a ~50% "decline"; year over year it grew 10%.
_QUARTERS = ["2025-03-31", "2024-12-31", "2024-09-30", "2024-06-30", "2024-03-31"]
_REVENUE = [95_000, 190_000, 90_000, 85_000, 86_364]
_NET_INCOME = [20_000, 45_000, 19_000, 18_000, 17_000]


def _series(values):
    return dict(zip(_QUARTERS, values))


def _financials():
    return {
        "income_statement": {
            "Total Revenue": _series(_REVENUE),
            "Net Income": _series(_NET_INCOME),
        },
        "balance_sheet": {
            "Total Debt": _series([100_000] * 5),
            "Stockholders Equity": _series([200_000, 195_000, 190_000, 185_000, 180_000]),
            "Current Assets": _series([150_000] * 5),
            "Current Liabilities": _series([100_000] * 5),
        },
        "cash_flow": {
            "Operating Cash Flow": _series([30_000, 60_000, 28_000, 27_000, 26_000]),
            "Capital Expenditure": _series([-5_000] * 5),
        },
    }


def _market_snapshot(ticker):
    return {
        "ticker": ticker,
        "name": f"{ticker} Test Corp",
        "currency": "USD",
        "price": 110.0,
        "previous_close": 100.0,
        "price_change": 10.0,
        "price_change_percent": 10.0,
        "market_cap": 500_000_000_000,
        "trailing_pe": 25.0,
        "forward_pe": 20.0,
        "price_to_sales": 6.0,
        "price_to_book": 12.0,
        "dividend_rate": 2.2,
        "dividend_yield": 2.0,
        "beta": 1.1,
        "fifty_two_week_high": 120.0,
        "fifty_two_week_low": 80.0,
        "shares_outstanding": 1_000_000_000,
        "trailing_eps": 4.4,
        "range_position": 75.0,
        "fetched_at": 0,
    }


def _seed_caches(ticker, sector="Technology"):
    """Write fresh cache files so no fetcher reaches the network."""
    os.makedirs(CACHE_DIR, exist_ok=True)

    written = []

    def write(name, payload):
        path = os.path.join(CACHE_DIR, name)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle)
        written.append(path)

    write(f"{ticker}_financials.json", _financials())
    write(f"{ticker}_market.json", _market_snapshot(ticker))
    write(
        f"{ticker}_sector.json",
        {
            "ticker": ticker,
            "sector": sector,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        },
    )

    return written


@pytest.fixture
def seeded(tmp_path, monkeypatch):
    """
    Seed caches for the test tickers and point the watchlist at a
    temporary file, so a test run can't touch a real user's list.

    Streamlit's @st.cache_data lives in the process, not in the
    AppTest instance, so it survives between tests and would otherwise
    serve one test's seeded financials to the next one - which silently
    turns the tests that swap the seeded data into no-ops.
    """
    import streamlit as st

    monkeypatch.setenv("INVESTOR_ASSISTANT_WATCHLIST", str(tmp_path / "watchlist.json"))

    st.cache_data.clear()

    written = _seed_caches(TICKER) + _seed_caches(PEER_TICKER)

    yield

    st.cache_data.clear()

    for path in written:
        if os.path.exists(path):
            os.remove(path)


def _run(script, **kwargs):
    app = AppTest.from_file(script, default_timeout=60, **kwargs)
    app.run()
    return app


# ----------------------------------------------------------
# Dashboard
# ----------------------------------------------------------

def test_dashboard_renders_landing_state_without_a_ticker(seeded):
    app = _run(DASHBOARD)

    assert not app.exception


def test_dashboard_renders_a_full_analysis(seeded):
    app = _run(DASHBOARD)
    app.session_state["active_ticker"] = TICKER
    app.run()

    assert not app.exception


def test_dashboard_reports_year_over_year_growth_for_a_seasonal_company(seeded):
    # The regression this whole change exists to prevent: the seeded
    # company's revenue halves sequentially every spring while growing
    # 10% year over year. The page must not call that a decline.
    app = _run(DASHBOARD)
    app.session_state["active_ticker"] = TICKER
    app.run()

    assert not app.exception

    body = " ".join(str(element.value) for element in app.markdown)

    assert "Revenue is growing" in body
    assert "Revenue is declining" not in body


def test_dashboard_shows_valuation_when_market_data_is_present(seeded):
    app = _run(DASHBOARD)
    app.session_state["active_ticker"] = TICKER
    app.run()

    body = " ".join(str(element.value) for element in app.markdown)

    assert "P/E (TTM)" in body
    assert "What the Market Is Paying" in " ".join(
        str(element.value) for element in app.subheader
    )


def test_dashboard_survives_missing_market_data(seeded):
    # A quote fetch failing must degrade to the fundamentals rather
    # than taking the page down.
    os.remove(os.path.join(CACHE_DIR, f"{TICKER}_market.json"))

    with open(os.path.join(CACHE_DIR, f"{TICKER}_market.json"), "w", encoding="utf-8") as handle:
        json.dump({}, handle)

    app = _run(DASHBOARD)
    app.session_state["active_ticker"] = TICKER
    app.run()

    assert not app.exception


def test_dashboard_handles_a_company_with_no_history(seeded):
    # One quarter only: every TTM figure has to fall back, and growth
    # can't be computed at all. The page still has to render.
    single_quarter = {
        "income_statement": {
            "Total Revenue": {"2025-03-31": 95_000},
            "Net Income": {"2025-03-31": 20_000},
        },
        "balance_sheet": {
            "Total Debt": {"2025-03-31": 100_000},
            "Stockholders Equity": {"2025-03-31": 200_000},
            "Current Assets": {"2025-03-31": 150_000},
            "Current Liabilities": {"2025-03-31": 100_000},
        },
        "cash_flow": {
            "Operating Cash Flow": {"2025-03-31": 30_000},
            "Capital Expenditure": {"2025-03-31": -5_000},
        },
    }

    path = os.path.join(CACHE_DIR, f"{TICKER}_financials.json")
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(single_quarter, handle)

    app = _run(DASHBOARD)
    app.session_state["active_ticker"] = TICKER
    app.run()

    assert not app.exception


def test_dashboard_handles_a_lossmaking_company(seeded):
    # A loss in the year-ago quarter means earnings growth has no
    # meaningful percentage - the page must describe the swing instead
    # of rendering an inverted number or crashing.
    financials = _financials()
    financials["income_statement"]["Net Income"] = _series(
        [20_000, 45_000, 19_000, 18_000, -17_000]
    )

    path = os.path.join(CACHE_DIR, f"{TICKER}_financials.json")
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(financials, handle)

    app = _run(DASHBOARD)
    app.session_state["active_ticker"] = TICKER
    app.run()

    assert not app.exception

    body = " ".join(str(element.value) for element in app.markdown)

    assert "Swung from a loss to a profit" in body


# ----------------------------------------------------------
# Compare page
# ----------------------------------------------------------

def test_compare_page_renders_landing_state(seeded):
    app = _run(COMPARE_PAGE)

    assert not app.exception


def test_compare_page_renders_a_full_comparison(seeded):
    app = _run(COMPARE_PAGE)
    app.session_state["compare_tickers"] = (TICKER, PEER_TICKER)
    app.run()

    assert not app.exception

    body = " ".join(str(element.value) for element in app.markdown)

    assert "P/E (TTM)" in body
    assert "Net Profit Margin (TTM)" in body


def test_compare_page_marks_no_winner_on_valuation_rows(seeded):
    # A lower P/E is not a win - and a negative one would take the
    # "lowest wins" crown while describing a company with no profits.
    peer_market = _market_snapshot(PEER_TICKER)
    peer_market["trailing_pe"] = -12.0

    with open(os.path.join(CACHE_DIR, f"{PEER_TICKER}_market.json"), "w", encoding="utf-8") as handle:
        json.dump(peer_market, handle)

    app = _run(COMPARE_PAGE)
    app.session_state["compare_tickers"] = (TICKER, PEER_TICKER)
    app.run()

    assert not app.exception

    # The negative P/E must not be rendered as the winning value.
    winning_cells = [
        str(element.value)
        for element in app.markdown
        if "compare-winner" in str(element.value)
    ]

    assert not any("-12.00" in cell for cell in winning_cells)


# ----------------------------------------------------------
# Other pages
# ----------------------------------------------------------

def test_discover_page_renders(seeded):
    app = _run(DISCOVER_PAGE)

    assert not app.exception


def test_storyline_page_renders(seeded):
    app = _run(STORYLINE_PAGE)

    assert not app.exception


def test_storyline_page_explains_setup_instead_of_crashing(seeded, monkeypatch):
    # A missing EDGAR_IDENTITY used to raise at import time, so the
    # page died with a raw Python traceback. The instructions were
    # inside the exception text, but a stack trace is not how you tell
    # someone to set an environment variable.
    monkeypatch.delenv("EDGAR_IDENTITY", raising=False)

    app = _run(STORYLINE_PAGE)

    assert not app.exception

    warnings = " ".join(str(element.value) for element in app.warning)
    body = " ".join(str(element.value) for element in app.markdown)

    assert "setup" in warnings.lower()
    assert "EDGAR_IDENTITY" in body
