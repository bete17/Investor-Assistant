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
from analytics.health_score import calculate_health_score, get_score_label
from analytics.sector_lookup import get_sector

from data.financials_fetcher import fetch_company_financials
from data.ticker_fetcher import find_valid_ticker
from utils import (
    format_percent,
    format_ratio,
    format_money,
)
from skeletons import skeleton_card, skeleton_card_row, skeleton_chart


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
        <p>Enter a stock ticker to explore financial KPIs, quarterly trends and automated financial insights.</p>
    </div>
</div>
""",
        unsafe_allow_html=True,
    )

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

st.markdown(
    f"""
<div class="company-header">
    <div>
        <div class="company-symbol">{html.escape(ticker)}</div>
        <div class="company-subtitle">Fundamental financial overview</div>
    </div>
    <div class="analysis-badge">QUARTERLY ANALYSIS</div>
</div>
""",
    unsafe_allow_html=True,
)


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

st.markdown('<div class="section-spacer"></div>', unsafe_allow_html=True)
health_score_card(score, score_label, score_class, sector)


# ==========================================================
# KEY METRICS
# ==========================================================

st.markdown('<div class="section-label">KEY METRICS</div>', unsafe_allow_html=True)
st.subheader("Profitability & Growth")


# ==========================================================
# FIRST KPI ROW
# ==========================================================

col1, col2, col3, col4 = st.columns(4)

with col1:
    metric_card(
        "NET PROFIT MARGIN",
        format_percent(kpis.get("net_profit_margin")),
        kpis.get("net_profit_margin"),
        "profit_margin",
        "Percentage of revenue converted into net profit.",
    )

with col2:
    metric_card(
        "RETURN ON EQUITY",
        format_percent(kpis.get("roe")),
        kpis.get("roe"),
        "roe",
        "Profit generated relative to shareholder equity.",
    )

with col3:
    metric_card(
        "REVENUE GROWTH",
        format_percent(kpis.get("revenue_growth")),
        kpis.get("revenue_growth"),
        "growth",
        "Change in total revenue from the previous quarter.",
    )

with col4:
    metric_card(
        "EARNINGS GROWTH",
        format_percent(kpis.get("earnings_growth")),
        kpis.get("earnings_growth"),
        "growth",
        "Change in net income from the previous quarter.",
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
    metric_card(
        "FREE CASH FLOW",
        format_money(kpis.get("free_cash_flow")),
        kpis.get("free_cash_flow"),
        "cash_flow",
        "Cash remaining after capital expenditures.",
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
st.subheader("Quarter-over-Quarter Growth")
st.caption("Negative values indicate contraction; positive values indicate growth.")

growth1, growth2 = st.columns(2)

with growth1:
    growth_bar("Revenue Growth", kpis.get("revenue_growth"))

with growth2:
    growth_bar("Earnings Growth", kpis.get("earnings_growth"))


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

revenue_growth = kpis.get("revenue_growth")

if revenue_growth is not None:

    if revenue_growth > 0:
        insights.append((
            "positive",
            "Revenue is growing",
            f"Revenue increased {format_percent(revenue_growth)} from the previous quarter.",
        ))

    elif revenue_growth < 0:
        insights.append((
            "negative",
            "Revenue is declining",
            f"Revenue decreased {format_percent(abs(revenue_growth))} from the previous quarter.",
        ))

    else:
        insights.append((
            "neutral",
            "Revenue is flat",
            "Revenue was approximately unchanged from the previous quarter.",
        ))


# ---- Earnings growth ----

earnings_growth = kpis.get("earnings_growth")

if earnings_growth is not None:

    if earnings_growth > 0:
        insights.append((
            "positive",
            "Earnings are growing",
            f"Net income increased {format_percent(earnings_growth)} from the previous quarter.",
        ))

    elif earnings_growth < 0:
        insights.append((
            "negative",
            "Earnings are declining",
            f"Net income decreased {format_percent(abs(earnings_growth))} from the previous quarter.",
        ))

    else:
        insights.append((
            "neutral",
            "Earnings are flat",
            "Net income was approximately unchanged from the previous quarter.",
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
### Net Profit Margin

**Formula:** `Net Income / Revenue × 100`

Measures how much of the company's revenue becomes net profit.

---

### Return on Equity

**Formula:** `Net Income / Stockholders' Equity × 100`

Measures how efficiently shareholder equity generates profit.

---

### Revenue Growth

**Formula:** `(Current Revenue - Previous Revenue) / Previous Revenue × 100`

Measures quarter-over-quarter revenue change.

---

### Earnings Growth

**Formula:** `(Current Net Income - Previous Net Income) / Previous Net Income × 100`

Measures quarter-over-quarter net income change.
"""
        )

    with reference_col2:
        st.markdown(
            """
### Debt-to-Equity

**Formula:** `Total Debt / Stockholders' Equity`

Measures financial leverage. Appropriate levels vary significantly by industry.

---

### Current Ratio

**Formula:** `Current Assets / Current Liabilities`

Measures the company's ability to meet short-term obligations.

---

### Free Cash Flow

**Formula:** `Operating Cash Flow + Capital Expenditure`

Measures cash remaining after capital expenditures.

Yahoo Finance generally reports capital expenditure as a negative number.
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