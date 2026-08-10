# ==========================================================
# IMPORTS
# ==========================================================

import html
import sys
from pathlib import Path

import plotly.graph_objects as go
import streamlit as st

# ==========================================================
# PROJECT PATH
# ==========================================================
# This file is designed to sit at:
# Investor-Assistant/UI/pages/1_Compare_Stocks.py
# so it needs to go up THREE levels to reach the project root
# (pages/ -> UI -> Investor-Assistant). Adjust if you place it
# elsewhere.

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))


# ==========================================================
# PROJECT IMPORTS
# ==========================================================

from analytics.kpi_engine import calculate_kpis
from utils import format_percent, format_ratio, format_money

from analytics.health_score import (
    calculate_health_score,
    get_score_label,
    METRIC_DISPLAY_NAMES,
)
from analytics.sector_lookup import get_sector
from skeletons import skeleton_card, skeleton_chart

# Note: this file does NOT import from kpi_dashboard.py, even
# though it duplicates load_kpis() below. Importing kpi_dashboard.py
# would re-run its entire top-to-bottom Streamlit page


# ==========================================================
# PAGE CONFIGURATION
# ==========================================================

st.set_page_config(
    page_title="Compare Stocks - Investor Assistant",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# ==========================================================
# LOAD CUSTOM CSS
# ==========================================================
# Reuses the same stylesheet as the main dashboard so both pages
# look consistent. Path goes up one level from pages/ to UI/.

css_path = Path(__file__).resolve().parent.parent / "styles.css"

if css_path.exists():
    css = css_path.read_text(encoding="utf-8")
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


# ==========================================================
# CACHED DATA LOADER
# ==========================================================

@st.cache_data(ttl=300, show_spinner=False)
def load_kpis(ticker):
    return calculate_kpis(ticker)


@st.cache_data(ttl=3600, show_spinner=False)  # sector changes rarely, cache longer
def load_sector(ticker):
    return get_sector(ticker)


# ==========================================================
# HELPER FUNCTIONS
# ==========================================================


def score_card(ticker, score, label, css_class, sector):
    """Big headline health-score card for one ticker."""

    display_score = "N/A" if score is None else f"{score}"

    # Show what the score was benchmarked against, since that's the
    # whole point of sector-aware scoring - a number without this
    # context is just as opaque as a competitor's black-box score.
    sector_note = f"vs. {sector} peers" if sector else "vs. general benchmark (sector unknown)"

    st.markdown(
        f"""
<div class="kpi-card">
    <div class="kpi-title">{html.escape(ticker)} HEALTH SCORE</div>
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


def build_radar_chart(ticker_a, breakdown_a, ticker_b, breakdown_b):
    """
    Overlay both companies' normalized KPI scores (0-100 each) on a
    radar/spider chart, so it's easy to see at a glance which one
    wins on which dimension.
    """

    # Only chart metrics BOTH companies actually have data for, so
    # the two shapes are directly comparable point-for-point.
    metrics_a = {row["metric"]: row["normalized"] for row in breakdown_a}
    metrics_b = {row["metric"]: row["normalized"] for row in breakdown_b}
    shared_metrics = [m for m in metrics_a if m in metrics_b]

    if not shared_metrics:
        return None

    labels = [METRIC_DISPLAY_NAMES.get(m, m) for m in shared_metrics]
    values_a = [metrics_a[m] for m in shared_metrics]
    values_b = [metrics_b[m] for m in shared_metrics]

    # Radar charts need the shape to "close" - the last point must
    # repeat the first, or there'll be a visible gap in the outline.
    labels_closed = labels + [labels[0]]
    values_a_closed = values_a + [values_a[0]]
    values_b_closed = values_b + [values_b[0]]

    fig = go.Figure()

    fig.add_trace(
        go.Scatterpolar(
            r=values_a_closed,
            theta=labels_closed,
            name=ticker_a,
            fill="toself",
            line=dict(color="#3b82f6"),
            opacity=0.7,
        )
    )

    fig.add_trace(
        go.Scatterpolar(
            r=values_b_closed,
            theta=labels_closed,
            name=ticker_b,
            fill="toself",
            line=dict(color="#f59e0b"),
            opacity=0.7,
        )
    )

    fig.update_layout(
        polar=dict(
            bgcolor="rgba(0,0,0,0)",
            radialaxis=dict(
                visible=True,
                range=[0, 100],
                showticklabels=False,
                gridcolor="#334155",
            ),
            angularaxis=dict(
                gridcolor="#334155",
                color="#cbd5e1",
            ),
        ),
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#f1f5f9"),
        legend=dict(orientation="h", y=-0.1),
        height=440,
        margin=dict(l=40, r=40, t=20, b=20),
    )

    return fig


def comparison_row(label, format_fn, raw_a, raw_b, higher_is_better=True):
    """
    One row of the side-by-side comparison table, with the better
    value highlighted.
    """

    col_label, col_a, col_b = st.columns([2, 1, 1])

    with col_label:
        st.markdown(f"<div class='compare-row-label'>{html.escape(label)}</div>", unsafe_allow_html=True)

    a_wins = False
    b_wins = False

    if raw_a is not None and raw_b is not None and raw_a != raw_b:
        if higher_is_better:
            a_wins = raw_a > raw_b
            b_wins = raw_b > raw_a
        else:
            a_wins = raw_a < raw_b
            b_wins = raw_b < raw_a

    with col_a:
        text = format_fn(raw_a) if raw_a is not None else "N/A"
        css_class = "compare-winner" if a_wins else ""
        st.markdown(f"<div class='compare-row-value {css_class}'>{html.escape(text)}</div>", unsafe_allow_html=True)

    with col_b:
        text = format_fn(raw_b) if raw_b is not None else "N/A"
        css_class = "compare-winner" if b_wins else ""
        st.markdown(f"<div class='compare-row-value {css_class}'>{html.escape(text)}</div>", unsafe_allow_html=True)


# ==========================================================
# PAGE HEADER
# ==========================================================

st.markdown(
    """
<div class="dashboard-header">
    <div class="eyebrow">INVESTOR ASSISTANT</div>
    <h1>Compare Stocks</h1>
    <p>See two companies side-by-side, scored and ranked on the same fundamentals.</p>
</div>
""",
    unsafe_allow_html=True,
)


# ==========================================================
# SESSION STATE
# ==========================================================

if "compare_tickers" not in st.session_state:
    st.session_state.compare_tickers = None


# ==========================================================
# TICKER INPUTS
# ==========================================================

st.markdown('<div class="section-label">SELECT TWO COMPANIES</div>', unsafe_allow_html=True)

input_a, input_b, button_col = st.columns([3, 3, 1])

default_a, default_b = st.session_state.compare_tickers or ("AAPL", "MSFT")

# The button column has no label, so the button sat higher than the two
# labelled inputs next to it. This previously used a hardcoded
# <div style='height: 28px'> spacer, which overshot slightly and would
# drift again on any change to label font-size or Streamlit's padding.
#
# Instead, Streamlit's own labels are collapsed and the SAME label
# element is rendered in all three columns - with non-breaking space as
# the button column's text. Heights then match by construction rather
# than by a guessed pixel value, so nothing to re-tune later.
FIELD_LABEL = '<div class="field-label">{}</div>'

with input_a:
    st.markdown(FIELD_LABEL.format("Ticker A"), unsafe_allow_html=True)
    ticker_a_input = st.text_input(
        "Ticker A",
        value=default_a,
        placeholder="e.g. AAPL",
        label_visibility="collapsed",
    ).strip().upper()

with input_b:
    st.markdown(FIELD_LABEL.format("Ticker B"), unsafe_allow_html=True)
    ticker_b_input = st.text_input(
        "Ticker B",
        value=default_b,
        placeholder="e.g. MSFT",
        label_visibility="collapsed",
    ).strip().upper()

with button_col:
    st.markdown(FIELD_LABEL.format("&nbsp;"), unsafe_allow_html=True)
    compare_clicked = st.button("Compare", use_container_width=True, type="primary")

if compare_clicked:

    if not ticker_a_input or not ticker_b_input:
        st.warning("Please enter both ticker symbols.")
        st.stop()

    if ticker_a_input == ticker_b_input:
        st.warning("Please enter two different tickers.")
        st.stop()

    st.session_state.compare_tickers = (ticker_a_input, ticker_b_input)

tickers = st.session_state.compare_tickers

if not tickers:
    st.markdown(
        """
<div class="welcome-card">
    <div class="welcome-icon">⚖️</div>
    <div>
        <h3>Compare two companies</h3>
        <p>Enter two ticker symbols to see health scores, KPIs, and a side-by-side breakdown.</p>
    </div>
</div>
""",
        unsafe_allow_html=True,
    )
    st.stop()

ticker_a, ticker_b = tickers


# ==========================================================
# LOAD DATA FOR BOTH TICKERS
# ==========================================================

loading_slot = st.empty()

with loading_slot.container():
    st.markdown('<div class="large-space"></div>', unsafe_allow_html=True)
    skeleton_col_a, skeleton_col_b = st.columns(2)
    with skeleton_col_a:
        skeleton_card()
    with skeleton_col_b:
        skeleton_card()
    st.markdown('<div class="large-space"></div>', unsafe_allow_html=True)
    skeleton_chart()

with st.spinner(f"Comparing {ticker_a} and {ticker_b}..."):

    try:
        kpis_a = load_kpis(ticker_a)
        kpis_b = load_kpis(ticker_b)

        # Sector lookup failing shouldn't block the whole comparison -
        # calculate_health_score() falls back to default ranges when
        # sector is None, so this is allowed to come back empty.
        sector_a = load_sector(ticker_a)
        sector_b = load_sector(ticker_b)

    except Exception as error:
        loading_slot.empty()
        st.error(f"Unable to load comparison: {error}")
        st.stop()

loading_slot.empty()

if not kpis_a:
    st.error(f"No KPI data was found for {ticker_a}.")
    st.stop()

if not kpis_b:
    st.error(f"No KPI data was found for {ticker_b}.")
    st.stop()


# ==========================================================
# HEALTH SCORES
# ==========================================================

score_a, breakdown_a = calculate_health_score(kpis_a, sector=sector_a)
score_b, breakdown_b = calculate_health_score(kpis_b, sector=sector_b)

label_a, class_a = get_score_label(score_a)
label_b, class_b = get_score_label(score_b)

st.markdown('<div class="large-space"></div>', unsafe_allow_html=True)
st.markdown('<div class="section-label">FINANCIAL HEALTH SCORE</div>', unsafe_allow_html=True)

score_col_a, score_col_b = st.columns(2)

with score_col_a:
    score_card(ticker_a, score_a, label_a, class_a, sector_a)

with score_col_b:
    score_card(ticker_b, score_b, label_b, class_b, sector_b)

# Each score is benchmarked against its OWN sector's norms, so when
# the two companies are in different sectors, the two numbers aren't
# directly "apples to apples" the way they are within the same
# sector - worth flagging rather than letting the user assume they are.
if sector_a and sector_b and sector_a != sector_b:
    st.caption(
        f"Note: {ticker_a} is scored against {sector_a} norms and {ticker_b} against "
        f"{sector_b} norms, since they're in different sectors - each score reflects "
        f"how strong that company is within its own industry, not a direct apples-to-apples ranking."
    )


# ==========================================================
# RADAR CHART
# ==========================================================

st.markdown('<div class="large-space"></div>', unsafe_allow_html=True)
st.markdown('<div class="section-label">SIDE-BY-SIDE PROFILE</div>', unsafe_allow_html=True)
st.subheader("Normalized KPI Comparison")
st.caption("Each metric scaled 0-100 so profit margin, leverage, and growth can be compared on the same chart.")

radar_fig = build_radar_chart(ticker_a, breakdown_a, ticker_b, breakdown_b)

if radar_fig:
    st.plotly_chart(radar_fig, use_container_width=True, config={"displaylogo": False})
else:
    st.info("Not enough shared data between these two companies to build a comparison chart.")


# ==========================================================
# DETAILED COMPARISON TABLE
# ==========================================================

st.markdown('<div class="large-space"></div>', unsafe_allow_html=True)
st.markdown('<div class="section-label">DETAILED COMPARISON</div>', unsafe_allow_html=True)
st.subheader("Metric by Metric")

table_header_a, table_header_b, table_header_c = st.columns([2, 1, 1])
with table_header_b:
    st.markdown(f"<div class='compare-col-header'>{html.escape(ticker_a)}</div>", unsafe_allow_html=True)
with table_header_c:
    st.markdown(f"<div class='compare-col-header'>{html.escape(ticker_b)}</div>", unsafe_allow_html=True)

comparison_row("Net Profit Margin", format_percent, kpis_a.get("net_profit_margin"), kpis_b.get("net_profit_margin"))
comparison_row("Return on Equity", format_percent, kpis_a.get("roe"), kpis_b.get("roe"))
comparison_row("Revenue Growth", format_percent, kpis_a.get("revenue_growth"), kpis_b.get("revenue_growth"))
comparison_row("Earnings Growth", format_percent, kpis_a.get("earnings_growth"), kpis_b.get("earnings_growth"))
comparison_row("Debt / Equity", format_ratio, kpis_a.get("debt_to_equity"), kpis_b.get("debt_to_equity"), higher_is_better=False)
comparison_row("Current Ratio", format_ratio, kpis_a.get("current_ratio"), kpis_b.get("current_ratio"))
comparison_row("Free Cash Flow", format_money, kpis_a.get("free_cash_flow"), kpis_b.get("free_cash_flow"))


# ==========================================================
# DISCLAIMER
# ==========================================================

st.markdown(
    """
<div class="dashboard-footer">
    <strong>Investor Assistant</strong> - Stock Comparison
    <br>
    The health score is a simple weighted model over public fundamentals for research and
    educational purposes only, and should not be interpreted as investment advice.
</div>
""",
    unsafe_allow_html=True,
)