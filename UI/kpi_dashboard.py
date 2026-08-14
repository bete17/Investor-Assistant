# ==========================================================
# IMPORTS
# ==========================================================

import html
import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st


# ==========================================================
# PROJECT PATH
# ==========================================================

# kpi_dashboard.py is inside:
# Investor-Assistant/UI/kpi_dashboard.py
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Add project root so Python can find kpi_engine and data modules.
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))


# ==========================================================
# PROJECT IMPORTS
# ==========================================================

from analytics.kpi_engine import calculate_kpis
from analytics.health_score import (
    calculate_health_score,
    coverage_label,
    explain_score,
    get_score_label,
)
from analytics.sector_lookup import get_sector
from analytics.valuation import build_valuation_reads, earnings_yield
from analytics.change_engine import summarize as summarize_changes
from analytics.change_engine import TRACKED_FIELDS
from analytics import watchlist as watchlist_store

from data.financials_fetcher import fetch_company_financials
from data.market_fetcher import fetch_market_snapshot
from data.snapshot_store import fetch_history
from data.ticker_fetcher import find_valid_ticker
from utils import (
    format_percent,
    format_ratio,
    format_money,
)
from skeletons import skeleton_card, skeleton_card_row, skeleton_chart
from components import (
    coverage_note,
    driver_row,
    price_header,
    range_bar,
    valuation_read,
    valuation_stats,
)
from change_panel import change_panel


# ==========================================================
# PAGE CONFIGURATION
# ==========================================================

st.set_page_config(
    page_title="Investor Assistant",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# ==========================================================
# LOAD CUSTOM CSS
# ==========================================================

css_path = Path(__file__).resolve().parent / "styles.css"

if css_path.exists():
    css = css_path.read_text(encoding="utf-8")
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


# ==========================================================
# CACHED DATA LOADERS
# ==========================================================
# Streamlit reruns the whole script on any widget interaction, so
# these are cached to avoid re-fetching on every rerun.

@st.cache_data(ttl=300, show_spinner=False)
def load_kpis(ticker):
    return calculate_kpis(ticker)


@st.cache_data(ttl=300, show_spinner=False)
def load_financials(ticker):
    return fetch_company_financials(ticker)


@st.cache_data(ttl=3600, show_spinner=False)  # sector changes rarely, cache longer
def load_sector(ticker):
    return get_sector(ticker)


@st.cache_data(ttl=300, show_spinner=False)  # quotes go stale fast
def load_market(ticker):
    return fetch_market_snapshot(ticker)


# ==========================================================
# HELPER FUNCTIONS
# ==========================================================


def get_metric_values(statement, metric):
    """
    Pull one metric's history out of a statement dict and drop
    None values (some quarters may be missing data).
    """

    if metric not in statement:
        return {}

    values = statement[metric]

    if not isinstance(values, dict):
        return {}

    clean_values = {}

    for date, value in values.items():
        if value is not None:
            clean_values[date] = value

    return clean_values


def parse_date(date):
    """Convert a date string to a Pandas datetime, or NaT on failure."""

    try:
        return pd.to_datetime(date)
    except Exception:
        return pd.NaT


def create_quarter_label(date):
    """e.g. "2025-09-30" -> "Q3 2025" """

    parsed = parse_date(date)

    if pd.isna(parsed):
        return str(date)

    quarter = ((parsed.month - 1) // 3) + 1
    return f"Q{quarter} {parsed.year}"


# profit_margin and roe share identical thresholds, so we define
# them once instead of duplicating the if/elif chain.
_PERCENT_THRESHOLDS = [
    (20, "Strong", "positive"),
    (10, "Healthy", "positive"),
    (0, "Positive", "neutral"),
]


def get_status(value, metric):

    #Map a KPI value to a (label, css_class) pair


    if value is None: # check if there's no number at all
        return "N/A", "neutral"

    # Net Profit Margin / ROE
    if metric in ("profit_margin", "roe"): # check we're looking at the right kind of metric

        for minimum, label, css_class in _PERCENT_THRESHOLDS:
            if value >= minimum:
                return label, css_class

        return "Negative", "negative"


    # Growth
    if metric == "growth":

        if value >= 10:
            return "Strong Growth", "positive"
        elif value > 0:
            return "Growing", "positive"
        elif value == 0:
            return "Flat", "neutral"
        else:
            return "Declining", "negative"

    # Debt-to-Equity (lower is better, unlike the metrics above)
    if metric == "debt":

        if value < 0.5:
            return "Low Leverage", "positive"
        elif value < 1:
            return "Moderate", "neutral"
        else:
            return "Elevated", "warning"

    # Current Ratio
    if metric == "liquidity":

        if value >= 1.5:
            return "Strong", "positive"
        elif value >= 1:
            return "Healthy", "positive"
        else:
            return "Below 1.0", "negative"

    # Free Cash Flow
    if metric == "cash_flow":

        if value > 0:
            return "Positive", "positive"
        elif value < 0:
            return "Negative", "negative"
        else:
            return "Neutral", "neutral"

    return "N/A", "neutral"


def metric_card(
    title,
    value,
    raw_value,
    metric_type,
    description,
):
    """Render one KPI card (custom HTML, since native st.metric can't do this layout)."""

    status, status_class = get_status(
        raw_value,
        metric_type,
    )

    # html.escape guards against XSS since some of this content
    # ultimately traces back to user input (the ticker).
    st.markdown(
        f"""
<div class="kpi-card">
    <div class="kpi-title">{html.escape(str(title))}</div>
    <div class="kpi-value">{html.escape(str(value))}</div>
    <div class="kpi-status {status_class}">
        <span class="status-dot"></span>
        {status}
    </div>
    <div class="kpi-description">{html.escape(str(description))}</div>
</div>
""",
        unsafe_allow_html=True,
    )


def health_score_card(score, label, css_class, sector):
    """
    Render the headline sector-aware Health Score, matching the card
    used on Compare Stocks. This is the single-number synthesis of
    the KPIs above - it's shown here on the main dashboard too, not
    just on Compare Stocks, since most people never leave this page.
    """

    display_score = "N/A" if score is None else str(score)
    sector_note = (
        f"Weighted score benchmarked against {sector} sector norms."
        if sector
        else "Weighted score benchmarked against a general-purpose "
        "range (sector unknown for this ticker)."
    )

    st.markdown(
        f"""
<div class="kpi-card">
    <div class="kpi-title">FINANCIAL HEALTH SCORE</div>
    <div class="kpi-value">{html.escape(display_score)}</div>
    <div class="kpi-status {css_class}">
        <span class="status-dot"></span>
        {label}
    </div>
    <div class="kpi-description">{html.escape(sector_note)}</div>
</div>
""",
        unsafe_allow_html=True,
    )


def insight_card(
    status,
    title,
    description,
):
    """Render one row in the Key Insights section."""

    st.markdown(
        f"""
<div class="insight-card">
    <div class="insight-indicator {status}"></div>
    <div class="insight-content">
        <div class="insight-title">{html.escape(str(title))}</div>
        <div class="insight-description">{html.escape(str(description))}</div>
    </div>
</div>
""",
        unsafe_allow_html=True,
    )


def create_financial_chart(
    dates,
    values,
    title,
    chart_type="bar",
):
    """Build a Plotly bar/line chart styled to match the dark theme."""

    labels = [create_quarter_label(date) for date in dates]

    fig = go.Figure()

    if chart_type == "bar":

        fig.add_trace(
            go.Bar(
                x=labels,
                y=values,
                name=title,
                marker_color="#C9974A",
                hovertemplate=(
                    "<b>%{x}</b><br>"
                    + title
                    + ": $%{y:,.0f}"
                    + "<extra></extra>"
                ),
            )
        )

    else:

        fig.add_trace(
            go.Scatter(
                x=labels,
                y=values,
                mode="lines+markers",
                name=title,
                line=dict(width=3, color="#10B981"),
                marker=dict(size=9, color="#10B981"),
                hovertemplate=(
                    "<b>%{x}</b><br>"
                    + title
                    + ": $%{y:,.0f}"
                    + "<extra></extra>"
                ),
            )
        )

    # Transparent background so the chart blends into the page
    # instead of showing Plotly's default white canvas.
    fig.update_layout(
        height=390,
        margin=dict(l=10, r=10, t=20, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
        hovermode="x unified",
        font=dict(color="#8B93A3", family="Inter"),
    )

    fig.update_xaxes(
        showgrid=False,
        zeroline=False,
        title=None,
        color="#8B93A3",
    )

    fig.update_yaxes(
        showgrid=True,
        gridcolor="rgba(255,255,255,0.08)",
        zeroline=False,
        tickprefix="$",
        tickformat="~s",
        title=None,
        color="#8B93A3",
    )

    return fig


def growth_bar(
    label,
    value,
):
    """Horizontal slider-style growth viz; center = 0%, left = decline, right = growth."""

    if value is None:
        st.markdown(
            f"""
<div class="growth-row">
    <div class="growth-header">
        <span>{html.escape(str(label))}</span>
        <strong>N/A</strong>
    </div>
    <div class="growth-track">
        <div class="growth-zero"></div>
    </div>
</div>
""",
            unsafe_allow_html=True,
        )

        return

    # Clamp to the -50%..+50% visual range so extreme values don't
    # push the marker off the track.
    visual_value = max(-50, min(50, value))
    clamped = visual_value != value

    # Map -50..+50 to 0..100 for CSS "left: X%" positioning.
    position = 50 + visual_value

    status_class = "positive" if value >= 0 else "negative"
    formatted_value = format_percent(value)

    if clamped:
        formatted_value += " *"

    st.markdown(
        f"""
<div class="growth-row">
    <div class="growth-header">
        <span>{html.escape(str(label))}</span>
        <strong class="{status_class}">{html.escape(formatted_value)}</strong>
    </div>
    <div class="growth-track">
        <div class="growth-zero"></div>
        <div class="growth-marker {status_class}" style="left:{position}%;">
            <div class="growth-dot"></div>
        </div>
    </div>
    <div class="growth-scale">
        <span>Decline</span>
        <span>0%</span>
        <span>Growth</span>
    </div>
</div>
""",
        unsafe_allow_html=True,
    )

    if clamped:
        st.caption("* value exceeds the +/-50% display range and has been clamped")


# ==========================================================
# PAGE HEADER
# ==========================================================

st.markdown(
    """
<div class="dashboard-header">
    <div class="eyebrow">INVESTOR ASSISTANT</div>
    <h1>Fundamental Analysis</h1>
    <p>Understand company profitability, growth, financial health and quarterly performance.</p>
</div>
""",
    unsafe_allow_html=True,
)


# ==========================================================
# SESSION STATE
# ==========================================================
# st.button() only returns True on the run where it was clicked;
# any later rerun (e.g. opening the reference expander) resets it
# to False. Persist the ticker in session_state so the dashboard
# survives reruns instead of disappearing.

if "active_ticker" not in st.session_state:
    st.session_state.active_ticker = None


def open_ticker(symbol):
    """Switch the dashboard to a ticker and redraw."""
    st.session_state.active_ticker = symbol
    st.rerun()


# ==========================================================
# COMPANY SEARCH
# ==========================================================

st.markdown(
    '<div class="section-label">COMPANY SEARCH</div>',
    unsafe_allow_html=True,
)

with st.form("company_search", clear_on_submit=False):
    search_col, button_col = st.columns([5, 1])

    with search_col:
        ticker_input = st.text_input(
            "Ticker Symbol",
            value=st.session_state.active_ticker or "AAPL",
            placeholder="Ticker or company name, e.g. AAPL or Apple",
            label_visibility="collapsed",
        ).strip()

    with button_col:
        analyze = st.form_submit_button(
            "Analyze",
            use_container_width=True,
            type="primary",
        )

if analyze:

    if not ticker_input:
        st.warning("Please enter a ticker symbol or company name.")
        st.stop()

    resolved = find_valid_ticker(ticker_input)
    if not resolved:
        st.error("Couldn't find a matching company. Try a ticker (AAPL) or name (Apple).")
        st.stop()

    st.session_state.active_ticker = resolved

ticker = st.session_state.active_ticker


# ==========================================================
# BEFORE ANALYSIS
# ==========================================================

if not ticker:

    st.markdown(
        """
<div class="welcome-card">
    <div class="welcome-icon">↗</div>
    <div>
        <h3>Start your analysis</h3>
        <p>Enter a stock ticker to explore financial KPIs, valuation multiples,
        quarterly trends and automated financial insights.</p>
    </div>
</div>
""",
        unsafe_allow_html=True,
    )

    # A returning user should land on their own list rather than an
    # empty box. This is the whole point of the watchlist existing:
    # without it, every visit starts from nothing and there's no
    # reason to come back.
    saved_tickers = watchlist_store.get_tickers()

    if saved_tickers:
        st.markdown('<div class="section-spacer"></div>', unsafe_allow_html=True)
        st.markdown('<div class="section-label">YOUR WATCHLIST</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="watchlist-intro">Pick up where you left off.</div>',
            unsafe_allow_html=True,
        )

        # Fixed-width rows rather than one column per ticker, so a
        # long list wraps instead of shrinking every button to nothing.
        for start in range(0, len(saved_tickers), 6):
            row = saved_tickers[start:start + 6]
            columns = st.columns(6)

            for column, symbol in zip(columns, row):
                with column:
                    if st.button(symbol, key=f"watch_open_{symbol}", use_container_width=True):
                        open_ticker(symbol)

    st.stop()


# ==========================================================
# LOAD COMPANY DATA
# ==========================================================

# Render the page's real shape as skeletons while data loads, instead
# of leaving the area blank behind a lone spinner. The placeholder is
# cleared as soon as the fetch finishes, and the real sections below
# render into the same layout - so nothing jumps.
loading_slot = st.empty()

with loading_slot.container():
    st.markdown('<div class="section-spacer"></div>', unsafe_allow_html=True)
    skeleton_card()
    st.markdown('<div class="large-space"></div>', unsafe_allow_html=True)
    skeleton_card_row(4)
    st.markdown('<div class="section-spacer"></div>', unsafe_allow_html=True)
    skeleton_card_row(3)
    st.markdown('<div class="large-space"></div>', unsafe_allow_html=True)
    chart_skeleton_1, chart_skeleton_2 = st.columns(2)
    with chart_skeleton_1:
        skeleton_chart()
    with chart_skeleton_2:
        skeleton_chart()

with st.spinner(f"Analyzing {ticker}..."):

    try:
        kpis = load_kpis(ticker)
        financial_data = load_financials(ticker)

        # Sector lookup failing shouldn't block the whole dashboard -
        # calculate_health_score() falls back to default ranges when
        # sector is None.
        sector = load_sector(ticker)

        # Market data is a separate, shorter-lived fetch than the
        # statements, and the fundamentals below are perfectly usable
        # without it - so a failed quote degrades to an empty snapshot
        # rather than taking the page down with it.
        try:
            market = load_market(ticker)
        except Exception:  # noqa: BLE001 - yfinance raises many shapes
            market = {}

    except Exception as error:
        loading_slot.empty()
        st.error(f"Unable to analyze {ticker}: {error}")
        st.stop()

loading_slot.empty()


# ==========================================================
# CHECK RESULTS
# ==========================================================

if not kpis:
    st.error(f"No KPI data was found for {ticker}.")
    st.stop()

if not financial_data:
    st.error(f"No financial statement data was found for {ticker}.")
    st.stop()


# ==========================================================
# FINANCIAL STATEMENTS
# ==========================================================

income_statement = financial_data.get("income_statement", {})
balance_sheet = financial_data.get("balance_sheet", {})
cash_flow = financial_data.get("cash_flow", {})


# ==========================================================
# COMPANY OVERVIEW
# ==========================================================

price_header(ticker, market, sector)

# Watchlist toggle sits directly under the header, next to the thing
# it applies to.
watch_col, _ = st.columns([1, 4])

with watch_col:
    already_watched = watchlist_store.is_watched(ticker)
    watch_label = "★  On watchlist" if already_watched else "☆  Add to watchlist"

    if st.button(watch_label, key="watch_toggle", use_container_width=True):
        watchlist_store.toggle_ticker(ticker)
        st.rerun()


# ==========================================================
# HEALTH SCORE
# ==========================================================
# The single-number synthesis of the KPIs below, benchmarked against
# this company's own sector. Shown up top since it's the fastest
# "should I even keep looking at this" signal - the detailed KPIs
# further down are where that number comes from, for anyone who
# wants to see the breakdown.

score, score_breakdown = calculate_health_score(kpis, sector=sector)
score_label, score_class = get_score_label(score)
score_explanation = explain_score(score_breakdown)

st.markdown('<div class="section-spacer"></div>', unsafe_allow_html=True)
health_score_card(score, score_label, score_class, sector)

# ---- What's actually driving the number ----
# A single 0-100 figure is only worth anything if you can see where it
# came from. The breakdown was already being computed here and thrown
# away; this surfaces it.

if score_explanation["strengths"] or score_explanation["drags"]:

    coverage = score_explanation["coverage"]
    coverage_text, coverage_class = coverage_label(coverage)

    st.markdown('<div class="section-spacer"></div>', unsafe_allow_html=True)
    coverage_note(coverage, coverage_text, coverage_class)

    with st.expander("What's driving this score?", expanded=False):

        st.caption(
            "Each bar shows where the company sits within the range typical "
            f"for {sector or 'the broader market'} on that metric - full bar "
            "means the top of the range."
        )

        driver_col1, driver_col2 = st.columns(2)

        with driver_col1:
            st.markdown("##### Lifting the score")

            if score_explanation["strengths"]:
                for row in score_explanation["strengths"]:
                    driver_row(row, "strength")
            else:
                st.caption("No metric scored above the middle of its sector range.")

        with driver_col2:
            st.markdown("##### Holding it back")

            if score_explanation["drags"]:
                for row in score_explanation["drags"]:
                    driver_row(row, "drag")
            else:
                st.caption("No metric scored below the middle of its sector range.")


# ==========================================================
# KEY METRICS
# ==========================================================

# ==========================================================
# VALUATION
# ==========================================================
# Everything above answers "is this a good business?". This answers
# the other half - "is it priced like one?" - which is where the app
# used to stop short. A high health score on an expensive stock is
# not a buy signal, and without any price context a reader could
# easily take it as one.

valuation_reads = build_valuation_reads(market, sector=sector, kpis=kpis)

if market or valuation_reads:

    st.markdown('<div class="large-space"></div>', unsafe_allow_html=True)
    st.markdown('<div class="section-label">VALUATION</div>', unsafe_allow_html=True)
    st.subheader("What the Market Is Paying")
    st.caption(
        "A strong company and a good investment are not the same thing - "
        "quality is often already reflected in the price."
    )

    valuation_stats(market)

    st.markdown('<div class="section-spacer"></div>', unsafe_allow_html=True)

    trailing_pe = (market or {}).get("trailing_pe")
    yield_percent = earnings_yield(trailing_pe)

    if yield_percent is not None:
        st.markdown(
            f'<div class="basis-note">At {format_ratio(trailing_pe)}x trailing '
            f"earnings, the company earns {format_percent(yield_percent)} a year "
            f"per dollar invested if profits stay flat - the earnings yield. "
            f"That is the figure to weigh against a bond or savings rate.</div>",
            unsafe_allow_html=True,
        )

    read_col1, read_col2 = st.columns(2)

    for index, read in enumerate(valuation_reads):
        with read_col1 if index % 2 == 0 else read_col2:
            valuation_read(read)

    if market.get("fifty_two_week_high") is not None:
        st.markdown('<div class="section-spacer"></div>', unsafe_allow_html=True)
        range_bar(market)


# ==========================================================
# WHAT CHANGED
# ==========================================================
# Placed directly after Valuation because it reads the same numbers
# from the other end. Valuation says what the market and its analysts
# currently think; this says which way that thinking has been moving,
# and both are more useful next to each other than apart.
#
# Everything above this point comes from a live fetch. This section is
# the only part of the page that cannot be produced on demand - it is
# built from observations recorded over past weeks, which is exactly
# why it is worth having and why it will look sparse at first.

st.markdown('<div class="large-space"></div>', unsafe_allow_html=True)
st.markdown('<div class="section-label">REVISIONS</div>', unsafe_allow_html=True)
st.subheader("What Changed")
st.caption(
    "Analysts are slow to move their estimates, so when they do - and "
    "repeatedly in one direction - it is rarely noise."
)

# A database round trip on every page load would be wasteful for data
# that changes at most once a day, so the read is cached. Keyed on the
# ticker, and short enough that a snapshot recorded moments ago by the
# fetch above still shows up within the same session.
@st.cache_data(ttl=300, show_spinner=False)
def _recorded_history(symbol):
    return fetch_history(symbol)


change_panel(summarize_changes(_recorded_history(ticker)), TRACKED_FIELDS)


# ==========================================================
# KEY METRICS
# ==========================================================

st.markdown('<div class="large-space"></div>', unsafe_allow_html=True)
st.markdown('<div class="section-label">KEY METRICS</div>', unsafe_allow_html=True)
st.subheader("Profitability & Growth")

# Say plainly what period these numbers cover. The labels used to
# imply a precision the underlying data didn't always support - and
# when there isn't a year of history to compare against, a growth
# figure means something materially different and should say so.
growth_basis = kpis.get("revenue_growth_basis") or kpis.get("earnings_growth_basis")
period_basis = kpis.get("period_basis")

basis_parts = []

if period_basis == "ttm":
    basis_parts.append(
        "Margin, return on equity and cash flow cover the trailing twelve "
        "months (the last four reported quarters)."
    )
elif period_basis == "quarter":
    basis_parts.append(
        "Fewer than four quarters were available, so margin, return on equity "
        "and cash flow reflect the latest quarter alone."
    )

if growth_basis == "yoy":
    basis_parts.append(
        "Growth compares the latest quarter with the same quarter a year "
        "earlier, so seasonal swings don't distort it."
    )
elif growth_basis == "sequential":
    basis_parts.append(
        "There isn't a full year of history, so growth compares consecutive "
        "quarters and may reflect seasonality rather than real momentum."
    )

if basis_parts:
    st.markdown(
        f'<div class="basis-note">{html.escape(" ".join(basis_parts))}</div>',
        unsafe_allow_html=True,
    )


# ==========================================================
# FIRST KPI ROW
# ==========================================================

growth_suffix = "YoY" if growth_basis == "yoy" else "QoQ"

col1, col2, col3, col4 = st.columns(4)

with col1:
    metric_card(
        "NET PROFIT MARGIN (TTM)",
        format_percent(kpis.get("net_profit_margin")),
        kpis.get("net_profit_margin"),
        "profit_margin",
        "Share of revenue converted into net profit over the last twelve months.",
    )

with col2:
    metric_card(
        "RETURN ON EQUITY (TTM)",
        format_percent(kpis.get("roe")),
        kpis.get("roe"),
        "roe",
        "Annual profit generated per dollar of average shareholder equity.",
    )

with col3:
    metric_card(
        f"REVENUE GROWTH ({growth_suffix})",
        format_percent(kpis.get("revenue_growth")),
        kpis.get("revenue_growth"),
        "growth",
        (
            "Change in quarterly revenue versus the same quarter last year."
            if growth_basis == "yoy"
            else "Change in revenue from the previous quarter."
        ),
    )

with col4:
    # A loss in the comparison period makes a percentage meaningless -
    # a swing from loss to profit computes as -200% - so the card
    # shows the swing in words instead of an inverted number.
    earnings_swing = kpis.get("earnings_swing")
    earnings_growth_value = kpis.get("earnings_growth")

    if earnings_growth_value is None and earnings_swing:
        metric_card(
            f"EARNINGS GROWTH ({growth_suffix})",
            "--",
            None,
            "growth",
            f"{earnings_swing}. A percentage change off a loss would invert "
            f"the meaning, so none is shown.",
        )
    else:
        metric_card(
            f"EARNINGS GROWTH ({growth_suffix})",
            format_percent(earnings_growth_value),
            earnings_growth_value,
            "growth",
            (
                "Change in quarterly net income versus the same quarter last year."
                if growth_basis == "yoy"
                else "Change in net income from the previous quarter."
            ),
        )


# ==========================================================
# FINANCIAL HEALTH
# ==========================================================

st.markdown('<div class="section-spacer"></div>', unsafe_allow_html=True)
st.subheader("Financial Health")

health1, health2, health3 = st.columns(3)

with health1:
    metric_card(
        "DEBT / EQUITY",
        format_ratio(kpis.get("debt_to_equity")),
        kpis.get("debt_to_equity"),
        "debt",
        "Company debt relative to shareholders' equity.",
    )

with health2:
    metric_card(
        "CURRENT RATIO",
        format_ratio(kpis.get("current_ratio")),
        kpis.get("current_ratio"),
        "liquidity",
        "Ability to meet short-term financial obligations.",
    )

with health3:
    fcf_margin = kpis.get("fcf_margin")

    # The dollar figure alone doesn't travel between companies -
    # $2B is enormous for a mid-cap and unremarkable for a mega-cap -
    # so pair it with the share of revenue it represents.
    fcf_description = "Cash remaining after capital expenditures, last twelve months."

    if fcf_margin is not None:
        fcf_description = (
            f"Cash left after capital expenditure over the last twelve months - "
            f"{format_percent(fcf_margin)} of revenue."
        )

    metric_card(
        "FREE CASH FLOW (TTM)",
        format_money(kpis.get("free_cash_flow")),
        kpis.get("free_cash_flow"),
        "cash_flow",
        fcf_description,
    )


# ==========================================================
# FINANCIAL PERFORMANCE
# ==========================================================

st.markdown('<div class="large-space"></div>', unsafe_allow_html=True)
st.markdown('<div class="section-label">FINANCIAL PERFORMANCE</div>', unsafe_allow_html=True)
st.subheader("Quarterly Performance")
st.caption("Track recent revenue and net income trends across reported quarters.")


# ==========================================================
# REVENUE DATA
# ==========================================================

revenue_values = get_metric_values(income_statement, "Total Revenue")


# ==========================================================
# NET INCOME DATA
# ==========================================================

income_values = get_metric_values(income_statement, "Net Income")


# ==========================================================
# REVENUE CHART
# ==========================================================

chart1, chart2 = st.columns(2)

with chart1:
    st.markdown("#### Quarterly Revenue")

    if revenue_values:

        # Sort by real date, not string order, since string sort
        # can misorder e.g. "2025-3-1" vs "2025-09-30".
        revenue_dates = sorted(revenue_values.keys(), key=parse_date)
        revenue_data = [revenue_values[date] for date in revenue_dates]

        revenue_chart = create_financial_chart(
            revenue_dates,
            revenue_data,
            "Revenue",
            "bar",
        )

        st.plotly_chart(
            revenue_chart,
            use_container_width=True,
            config={"displaylogo": False},
        )

    else:
        st.info("Revenue history is unavailable.")


# ==========================================================
# NET INCOME CHART
# ==========================================================

with chart2:
    st.markdown("#### Quarterly Net Income")

    if income_values:

        income_dates = sorted(income_values.keys(), key=parse_date)
        income_data = [income_values[date] for date in income_dates]

        income_chart = create_financial_chart(
            income_dates,
            income_data,
            "Net Income",
            "line",
        )

        st.plotly_chart(
            income_chart,
            use_container_width=True,
            config={"displaylogo": False},
        )

    else:
        st.info("Net income history is unavailable.")


# ==========================================================
# GROWTH MOMENTUM
# ==========================================================

st.markdown('<div class="large-space"></div>', unsafe_allow_html=True)
st.markdown('<div class="section-label">GROWTH MOMENTUM</div>', unsafe_allow_html=True)

if growth_basis == "yoy":
    st.subheader("Year-over-Year Growth")
    st.caption(
        "Latest quarter against the same quarter a year earlier. Negative "
        "values indicate contraction; positive values indicate growth."
    )
else:
    st.subheader("Quarter-over-Quarter Growth")
    st.caption(
        "Consecutive quarters, since a full year of history isn't available. "
        "Seasonal businesses can look like they're shrinking on this basis."
    )

growth1, growth2 = st.columns(2)

with growth1:
    growth_bar("Revenue Growth", kpis.get("revenue_growth"))

with growth2:
    growth_bar("Earnings Growth", kpis.get("earnings_growth"))

# Sequential growth is genuinely useful as a momentum read - it's
# just not the headline, because seasonality dominates it. Shown as a
# labelled supplement rather than hidden entirely.
sequential_revenue = kpis.get("revenue_growth_qoq")
sequential_earnings = kpis.get("earnings_growth_qoq")

if growth_basis == "yoy" and (sequential_revenue is not None or sequential_earnings is not None):

    with st.expander("Sequential (quarter-over-quarter) growth", expanded=False):
        st.caption(
            "Against the immediately preceding quarter. Useful for spotting a "
            "turn early, but seasonal businesses swing hard here every year - "
            "a retailer always contracts after the holidays."
        )

        sequential1, sequential2 = st.columns(2)

        with sequential1:
            growth_bar("Revenue (QoQ)", sequential_revenue)

        with sequential2:
            growth_bar("Earnings (QoQ)", sequential_earnings)


# ==========================================================
# FINANCIAL ASSESSMENT
# ==========================================================

st.markdown('<div class="large-space"></div>', unsafe_allow_html=True)
st.markdown('<div class="section-label">FINANCIAL ASSESSMENT</div>', unsafe_allow_html=True)
st.subheader("Key Insights")
st.caption("Automated interpretation of the company's latest financial metrics.")


# ==========================================================
# BUILD INSIGHTS
# ==========================================================
# Collect (status, title, description) tuples first, render after,
# so we can lay them out in two columns below.

insights = []


# ---- Profitability ----

net_margin = kpis.get("net_profit_margin")

if net_margin is not None:

    if net_margin >= 20:
        insights.append((
            "positive",
            "Strong profitability",
            f"Net profit margin is {format_percent(net_margin)}, indicating strong profitability.",
        ))

    elif net_margin >= 0:
        insights.append((
            "neutral",
            "Positive profitability",
            f"The company remains profitable with a net margin of {format_percent(net_margin)}.",
        ))

    else:
        insights.append((
            "negative",
            "Negative profitability",
            f"Net profit margin is {format_percent(net_margin)}.",
        ))


# ---- Revenue growth ----
# Phrased against whichever comparison was actually used. Saying "from
# the previous quarter" when the figure is year-over-year (or the
# reverse) would misdescribe the number sitting next to it.

comparison_phrase = (
    "from the same quarter a year earlier"
    if growth_basis == "yoy"
    else "from the previous quarter"
)

revenue_growth = kpis.get("revenue_growth")

if revenue_growth is not None:

    if revenue_growth > 0:
        insights.append((
            "positive",
            "Revenue is growing",
            f"Revenue increased {format_percent(revenue_growth)} {comparison_phrase}.",
        ))

    elif revenue_growth < 0:
        insights.append((
            "negative",
            "Revenue is declining",
            f"Revenue decreased {format_percent(abs(revenue_growth))} {comparison_phrase}.",
        ))

    else:
        insights.append((
            "neutral",
            "Revenue is flat",
            f"Revenue was approximately unchanged {comparison_phrase}.",
        ))


# ---- Earnings growth ----

earnings_growth = kpis.get("earnings_growth")
earnings_swing_note = kpis.get("earnings_swing")

if earnings_growth is not None:

    if earnings_growth > 0:
        insights.append((
            "positive",
            "Earnings are growing",
            f"Net income increased {format_percent(earnings_growth)} {comparison_phrase}.",
        ))

    elif earnings_growth < 0:
        insights.append((
            "negative",
            "Earnings are declining",
            f"Net income decreased {format_percent(abs(earnings_growth))} {comparison_phrase}.",
        ))

    else:
        insights.append((
            "neutral",
            "Earnings are flat",
            f"Net income was approximately unchanged {comparison_phrase}.",
        ))

elif earnings_swing_note:

    # The comparison period was a loss, so a percentage would invert
    # the meaning. Describe the direction instead of computing one.
    swung_positive = earnings_swing_note in (
        "Swung from a loss to a profit",
        "Still lossmaking, but the loss narrowed",
        "Turned profitable from a breakeven prior period",
    )

    insights.append((
        "positive" if swung_positive else "negative",
        "Earnings turned",
        f"{earnings_swing_note} ({comparison_phrase}).",
    ))


# ---- Free cash flow ----

free_cash_flow = kpis.get("free_cash_flow")

if free_cash_flow is not None:

    if free_cash_flow > 0:
        insights.append((
            "positive",
            "Positive cash generation",
            f"The company generated {format_money(free_cash_flow)} in free cash flow.",
        ))

    else:
        insights.append((
            "negative",
            "Negative free cash flow",
            f"Free cash flow is {format_money(free_cash_flow)}.",
        ))


# ---- Debt ----

debt_equity = kpis.get("debt_to_equity")

if debt_equity is not None:

    if debt_equity < 1:
        insights.append((
            "positive",
            "Manageable leverage",
            f"Debt-to-equity is {format_ratio(debt_equity)}, which is below 1.0.",
        ))

    else:
        insights.append((
            "neutral",
            "Elevated leverage",
            f"Debt-to-equity is {format_ratio(debt_equity)}. Leverage should be compared with industry peers.",
        ))


# ---- Liquidity ----

current_ratio = kpis.get("current_ratio")

if current_ratio is not None:

    if current_ratio >= 1:
        insights.append((
            "positive",
            "Healthy short-term liquidity",
            f"The current ratio is {format_ratio(current_ratio)}, meaning current assets exceed current liabilities.",
        ))

    else:
        insights.append((
            "negative",
            "Liquidity may require attention",
            f"The current ratio is {format_ratio(current_ratio)}, which is below 1.0.",
        ))


# ==========================================================
# DISPLAY INSIGHTS
# ==========================================================
# Two-column layout, alternating left/right by index parity.

insight_col1, insight_col2 = st.columns(2)

for index, insight in enumerate(insights):

    status, title, description = insight

    if index % 2 == 0:
        with insight_col1:
            insight_card(status, title, description)
    else:
        with insight_col2:
            insight_card(status, title, description)


# ==========================================================
# KPI EDUCATION SECTION
# ==========================================================

st.markdown('<div class="large-space"></div>', unsafe_allow_html=True)
st.markdown('<div class="section-label">REFERENCE</div>', unsafe_allow_html=True)
st.subheader("Understand the Metrics")

with st.expander("What do these KPIs mean?", expanded=False):

    reference_col1, reference_col2 = st.columns(2)

    with reference_col1:
        st.markdown(
            """
### Net Profit Margin (TTM)

**Formula:** `TTM Net Income / TTM Revenue × 100`

How much of each sales dollar becomes profit. TTM means trailing twelve
months — the last four reported quarters summed, so a single unusual
quarter doesn't dominate.

---

### Return on Equity (TTM)

**Formula:** `TTM Net Income / Average Shareholders' Equity × 100`

How much annual profit the company generates per dollar of equity.
Equity is averaged over the year because it's a point-in-time balance
while profit accumulates over the period.

---

### Revenue Growth (YoY)

**Formula:** `(This Quarter - Same Quarter Last Year) / Same Quarter Last Year × 100`

Compared against the same quarter a year earlier rather than the previous
quarter, because most businesses are seasonal — a retailer's sales always
fall after the holidays, and that isn't a decline.

---

### Earnings Growth (YoY)

**Formula:** `(This Quarter - Same Quarter Last Year) / Same Quarter Last Year × 100`

No percentage is shown when the year-ago quarter was a loss: the standard
formula reports a swing from loss to profit as *negative* growth, which
inverts the meaning. The change is described in words instead.
"""
        )

    with reference_col2:
        st.markdown(
            """
### Debt-to-Equity

**Formula:** `Total Debt / Stockholders' Equity`

Financial leverage. Appropriate levels vary significantly by industry —
a utility carries debt a software company never would.

---

### Current Ratio

**Formula:** `Current Assets / Current Liabilities`

Whether the company can cover its next twelve months of obligations from
assets it can convert to cash in that time.

---

### Free Cash Flow (TTM)

**Formula:** `TTM Operating Cash Flow + TTM Capital Expenditure`

Cash left over after the spending needed to maintain the business. Profit
is an accounting opinion; cash flow is harder to massage.

Yahoo Finance reports capital expenditure as a negative number, hence the
addition.

---

### Price to Earnings

**Formula:** `Share Price / Earnings Per Share`

What the market pays for each dollar of profit. Only meaningful against
a peer group — 25× is ordinary for software and expensive for a bank. A
lossmaking company has no meaningful P/E, which is not the same as
being cheap.
"""
        )


# ==========================================================
# DISCLAIMER
# ==========================================================

st.markdown(
    """
<div class="dashboard-footer">
    <strong>Investor Assistant</strong> • Fundamental Analysis Dashboard
    <br>
    Financial metrics and classifications are provided for research and educational purposes only.
    General KPI thresholds may not be appropriate for every industry and should not be interpreted as investment advice.
</div>
""",
    unsafe_allow_html=True,
)