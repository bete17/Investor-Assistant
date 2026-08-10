# ==========================================================
# IMPORTS
# ==========================================================

import html
import sys
from pathlib import Path

import streamlit as st

# ==========================================================
# PROJECT PATH
# ==========================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

# ==========================================================
# PROJECT IMPORTS
# ==========================================================

from analytics.discover_engine import (
    GOAL_OPTIONS,
    SCENARIO_OPTIONS,
    SECTOR_OPTIONS,
    SELF_RATING_OPTIONS,
    compute_risk_tier,
    get_suggestions,
    rank_by_score,
)
from analytics.health_score import calculate_health_score, get_score_label
from analytics.kpi_engine import calculate_kpis
from analytics.sector_lookup import get_sector
from skeletons import skeleton_card_row

# ==========================================================
# PAGE CONFIGURATION
# ==========================================================

st.set_page_config(
    page_title="Discover - Investor Assistant",
    page_icon="🧭",
    layout="wide",
    initial_sidebar_state="collapsed",
)

css_path = Path(__file__).resolve().parent.parent / "styles.css"
if css_path.exists():
    css = css_path.read_text(encoding="utf-8")
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)

# ==========================================================
# CACHED LOADERS
# ==========================================================
# Same cached loaders/TTLs as kpi_dashboard.py, so a ticker looked
# up here and then opened on the dashboard doesn't trigger a
# redundant fetch.


@st.cache_data(ttl=300, show_spinner=False)
def load_kpis(ticker):
    return calculate_kpis(ticker)


@st.cache_data(ttl=3600, show_spinner=False)
def load_sector(ticker):
    return get_sector(ticker)


# ==========================================================
# HELPERS
# ==========================================================


def why_line(score, label, sector):
    """
    Build the suggestion's rationale FROM the app's own Health Score
    output, rather than hand-written opinion copy - see
    discover_engine.py's module docstring for why that distinction
    matters here specifically.
    """
    if score is None:
        return "Health Score unavailable right now - data may be temporarily missing for this ticker."

    sector_note = f"vs. {sector} peers" if sector else "vs. general benchmark (sector unknown)"
    return f"Health Score {score} ({label}) {sector_note}."


def suggestion_card(ticker, score, sector):
    """Render one ranked suggestion: ticker, Health Score, data-driven rationale, and a handoff button."""

    label, css_class = get_score_label(score)

    st.markdown(
        f"""
<div class="kpi-card">
    <div class="kpi-title">{html.escape(ticker)}</div>
    <div class="kpi-value">{html.escape("N/A" if score is None else str(score))}</div>
    <div class="kpi-status {css_class}">
        <span class="status-dot"></span>
        {label}
    </div>
    <div class="kpi-description">{html.escape(why_line(score, label, sector))}</div>
</div>
""",
        unsafe_allow_html=True,
    )

    if st.button("See full analysis", key=f"open_{ticker}", use_container_width=True):
        st.session_state.active_ticker = ticker
        st.switch_page("kpi_dashboard.py")


def ranked_row(position, ticker, score, sector):
    """
    Render one compact row of the full ranked pool. Deliberately not a
    card: at 16 candidates, 16 full-size cards is a heavy scroll, so
    the long tail gets a dense leaderboard-style row instead while the
    top few keep the rich card treatment.
    """
    label, css_class = get_score_label(score)
    display_score = "N/A" if score is None else f"{score}"
    sector_note = sector if sector else "Sector unknown"

    row_col, button_col = st.columns([5, 1])

    with row_col:
        st.markdown(
            f"""
<div class="discover-row">
    <span class="discover-rank">#{position}</span>
    <span class="discover-row-ticker">{html.escape(ticker)}</span>
    <span class="discover-row-score">{html.escape(display_score)}</span>
    <span class="kpi-status {css_class} discover-row-status">
        <span class="status-dot"></span>{label}
    </span>
    <span class="discover-row-sector">{html.escape(sector_note)}</span>
</div>
""",
            unsafe_allow_html=True,
        )

    with button_col:
        if st.button("Analyze", key=f"row_{ticker}", use_container_width=True):
            st.session_state.active_ticker = ticker
            st.switch_page("kpi_dashboard.py")


# ==========================================================
# PAGE HEADER
# ==========================================================

st.markdown(
    """
<div class="dashboard-header">
    <div class="eyebrow">INVESTOR ASSISTANT</div>
    <h1>Discover</h1>
    <p>Don't have a ticker in mind yet? Answer a few quick questions to get some starting points.</p>
</div>
""",
    unsafe_allow_html=True,
)

st.markdown(
    """
<div class="dashboard-footer" style="margin-top: 0; margin-bottom: 24px;">
    These are top matches, ranked live by Health Score, from a small pool of well-known
    companies for your answers - not personalized investment advice, and not a screen of
    the whole market. Always do your own research before investing.
</div>
""",
    unsafe_allow_html=True,
)

# ==========================================================
# QUIZ
# ==========================================================

st.markdown('<div class="section-label">A FEW QUICK QUESTIONS</div>', unsafe_allow_html=True)

with st.form("discover_quiz"):

    self_rating = st.radio(
        "How do you feel about risk with your investments?",
        options=list(SELF_RATING_OPTIONS.keys()),
        index=1,
    )

    scenario = st.radio(
        "A stock you own drops 20% in a month. What do you do?",
        options=list(SCENARIO_OPTIONS.keys()),
        index=1,
    )

    sector_choice = st.radio(
        "Which of these sounds most interesting to you?",
        options=list(SECTOR_OPTIONS.keys()),
        index=0,
    )

    goal = st.radio(
        "What's your main goal right now?",
        options=GOAL_OPTIONS,
        index=2,
    )

    submitted = st.form_submit_button("Show me some starting points", type="primary")

if not submitted and "discover_results" not in st.session_state:
    st.stop()

if submitted:
    st.session_state.discover_results = {
        "sector_label": sector_choice,
        "sector": SECTOR_OPTIONS[sector_choice],
        "risk_tier": compute_risk_tier(self_rating, scenario, goal),
        "goal": goal,
    }

results = st.session_state.discover_results

# ==========================================================
# RESULTS
# ==========================================================

st.markdown('<div class="large-space"></div>', unsafe_allow_html=True)
st.markdown('<div class="section-label">STARTING POINTS</div>', unsafe_allow_html=True)
st.subheader(f"{results['risk_tier']} · {results['sector_label']}")

candidates = get_suggestions(results["sector"], results["risk_tier"])

if not candidates:
    st.info("No curated candidates for this combination yet.")
    st.stop()

# Score every candidate in the pool once (cached loaders make repeat
# runs within the TTL free), THEN rank - so the tickers actually
# shown are whichever score best right now, not a fixed display
# order. See discover_engine.py's module docstring for why this beats
# just showing the pool as-is.
# This is a LOOP of known length, so it gets a real progress bar with
# live status rather than an indeterminate spinner - the wait is long
# enough (up to 2 network calls per candidate on a cold cache) that
# showing actual progress matters more than a generic "loading".
progress_slot = st.empty()
status_slot = st.empty()
skeleton_slot = st.empty()

with skeleton_slot.container():
    skeleton_card_row(4)

progress_bar = progress_slot.progress(0.0)

ticker_data = {}
for index, candidate in enumerate(candidates, start=1):
    status_slot.caption(f"Scoring {candidate} ({index} of {len(candidates)})...")
    try:
        kpis = load_kpis(candidate)
        candidate_sector = load_sector(candidate)
        score, _ = calculate_health_score(kpis, sector=candidate_sector) if kpis else (None, [])
    except Exception:
        score, candidate_sector = None, None
    ticker_data[candidate] = (score, candidate_sector)
    progress_bar.progress(index / len(candidates))

progress_slot.empty()
status_slot.empty()
skeleton_slot.empty()

# Rank the WHOLE pool, then slice for display - the top few get
# cards, the rest are browsable in the expander below.
ranked = rank_by_score(
    candidates,
    score_fn=lambda ticker: ticker_data[ticker][0],
    max_results=len(candidates),
)

TOP_CARD_COUNT = 4
top_matches = ranked[:TOP_CARD_COUNT]
remaining = ranked[TOP_CARD_COUNT:]

st.caption(
    f"Top {len(top_matches)} by Health Score, ranked live from a pool of {len(candidates)} "
    f"{results['sector_label'].lower()} candidates in the {results['risk_tier'].lower()} range."
)

columns = st.columns(len(top_matches))
for column, (ticker, score) in zip(columns, top_matches):
    with column:
        suggestion_card(ticker, score, ticker_data[ticker][1])

# ==========================================================
# FULL RANKED POOL
# ==========================================================
# Collapsed by default: the top cards are the answer, this is for
# anyone who wants to scan further down the list themselves rather
# than trust the top 4.

if remaining:
    st.markdown('<div class="large-space"></div>', unsafe_allow_html=True)

    with st.expander(f"See all {len(ranked)} ranked candidates", expanded=False):
        st.caption(
            "Every candidate in this pool, ranked by Health Score. Scores are "
            "benchmarked against each company's own sector, so they reflect strength "
            "within its industry rather than a direct cross-sector ranking."
        )

        for position, (ticker, score) in enumerate(ranked, start=1):
            ranked_row(position, ticker, score, ticker_data[ticker][1])

# ==========================================================
# DISCLAIMER
# ==========================================================

st.markdown(
    """
<div class="dashboard-footer">
    <strong>Investor Assistant</strong> &middot; Discover
    <br>
    Suggestions are a small curated list matched against your answers and public data,
    for research and educational purposes only. Not investment advice, and not a
    substitute for your own research.
</div>
""",
    unsafe_allow_html=True,
)