# ==========================================================
# IMPORTS
# ==========================================================

import html
import sys
from datetime import datetime
from pathlib import Path

import streamlit as st

# ==========================================================
# PROJECT PATH
# ==========================================================
# Investor-Assistant/UI/pages/2_Storyline.py -> up three levels

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

# ==========================================================
# PROJECT IMPORTS
# ==========================================================

from analytics.storyline_engine import summarize_item7
from data.news_fetcher import fetch_news
from analytics.sentiment_engine import SentimentEngine
from data.ticker_fetcher import find_valid_ticker
from skeletons import skeleton_card, skeleton_bullets

# ==========================================================
# PAGE CONFIGURATION
# ==========================================================

st.set_page_config(
    page_title="Storyline - Investor Assistant",
    page_icon="📜",
    layout="wide",
    initial_sidebar_state="collapsed",
)

css_path = Path(__file__).resolve().parent.parent / "styles.css"
if css_path.exists():
    css = css_path.read_text(encoding="utf-8")
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)

# ==========================================================
# CONFIG
# ==========================================================

YEARS_TO_SHOW = 5
CURRENT_YEAR = datetime.now().year
# Most recent 10-K is usually for the prior fiscal year.
MOST_RECENT_FILING_YEAR = CURRENT_YEAR - 1

# One shared SentimentEngine instance for this page - the VADER
# analyzer is stateless and reusable across tickers.
_sentiment_engine = SentimentEngine()

# ==========================================================
# CACHED LOADERS
# ==========================================================


@st.cache_data(ttl=3600, show_spinner=False)
def load_year_summary(ticker, year):
    return summarize_item7(ticker, year)


@st.cache_data(ttl=1800, show_spinner=False)  # news goes stale faster than filings
def load_sentiment(ticker):
    # fetch_news() handles its own on-disk caching (via is_cache_valid),
    # so calling it here just ensures a cache file exists before
    # SentimentEngine reads it - no fetch happens if it's already fresh.
    fetch_news(ticker)
    return _sentiment_engine.generate_aggregate_sentiment_story(ticker)


# ==========================================================
# HELPERS
# ==========================================================


def summary_to_bullets(summary_text):
    """Split the LLM summary string into individual bullet lines."""
    if not summary_text:
        return []

    skip_prefixes = ("here is", "here's a summary", "here's a concise summary")

    lines = []
    for raw_line in summary_text.splitlines():
        line = raw_line.strip().lstrip("-•*").strip()
        line = line.replace("**", "")
        if not line or line.lower().startswith(skip_prefixes):
            continue
        lines.append(line)
    return lines


def timeline_entry(year, summary_text, is_diff):
    """Render one year's card: year marker + full bullet summary, always visible.

    is_diff flags whether this summary was generated FROM a diff against
    the prior year's filing (the app's actual differentiator - this is
    management's own account of what changed, not just what they said
    this year) versus a first-year baseline read with nothing to
    compare against yet.
    """

    bullets = summary_to_bullets(summary_text)
    bullets_html = "".join(f"<li>{html.escape(b)}</li>" for b in bullets)

    if is_diff:
        badge_html = (
            '<span class="story-diff-badge story-diff-badge-diff">'
            "&#8593; Changed vs. prior year</span>"
        )
    else:
        badge_html = (
            '<span class="story-diff-badge story-diff-badge-baseline">'
            "First year on record</span>"
        )

    st.markdown(
        f"""
<div class="story-year-marker">
    <div class="story-year">{year}</div>
    {badge_html}
</div>
<div class="kpi-card">
    <ul class="story-bullets">
        {bullets_html}
    </ul>
</div>
""",
        unsafe_allow_html=True,
    )


def timeline_gap(year):
    """Render a placeholder for a year with no filing/summary available."""
    st.markdown(
        f"""
<div class="story-year-marker story-year-marker-empty">
    <div class="story-year">{year}</div>
    <div class="story-empty-note">No filing on record</div>
</div>
""",
        unsafe_allow_html=True,
    )


def sentiment_status(average_score):
    """Map a VADER compound score to a (label, css_class) pair, matching kpi-status conventions."""
    if average_score > 0.05:
        return "Positive", "positive"
    elif average_score < -0.05:
        return "Negative", "negative"
    else:
        return "Neutral", "neutral"


def sentiment_card(sentiment):
    """Render the recent-news sentiment score as a KPI-style card."""

    average_score = sentiment.get("average_score", 0.0)
    total_articles = sentiment.get("total_articles_analyzed", 0)
    summary_text = sentiment.get("sentiment_summary", "")
    label, css_class = sentiment_status(average_score)

    if total_articles == 0:
        st.info("No recent news headlines were found for this ticker.")
        return

    st.markdown(
        f"""
<div class="kpi-card">
    <div class="kpi-title">RECENT NEWS SENTIMENT</div>
    <div class="kpi-value">{average_score:+.2f}</div>
    <div class="kpi-status {css_class}">
        <span class="status-dot"></span>
        {label}
    </div>
    <div class="kpi-description">{html.escape(summary_text)} (based on {total_articles} recent headlines)</div>
</div>
""",
        unsafe_allow_html=True,
    )


# ==========================================================
# PAGE HEADER
# ==========================================================

st.markdown(
    """
<div class="dashboard-header">
    <div class="eyebrow">INVESTOR ASSISTANT</div>
    <h1>The Story So Far</h1>
    <p>How this company's own narrative has changed, year by year.</p>
</div>
""",
    unsafe_allow_html=True,
)

# ==========================================================
# SESSION STATE
# ==========================================================

if "active_ticker" not in st.session_state:
    st.session_state.active_ticker = None

# ==========================================================
# TICKER INPUT
# ==========================================================

st.markdown('<div class="section-label">COMPANY</div>', unsafe_allow_html=True)

search_col, button_col = st.columns([5, 1])

with search_col:
    ticker_input = st.text_input(
        "Ticker Symbol",
        value=st.session_state.active_ticker or "AAPL",
        placeholder="Ticker or company name, e.g. AAPL or Apple",
        label_visibility="collapsed",
    ).strip()

with button_col:
    load_clicked = st.button("View Story", use_container_width=True, type="primary")

if load_clicked:
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
# TICKER INPUT
# ==========================================================



if not ticker:
    st.markdown(
        """
<div class="welcome-card">
    <div class="welcome-icon">📜</div>
    <div>
        <h3>See the story behind the numbers</h3>
        <p>Enter a ticker to see how management's own account of the business has changed year over year.</p>
    </div>
</div>
""",
        unsafe_allow_html=True,
    )
    st.stop()

# ==========================================================
# RECENT SENTIMENT
# ==========================================================

st.markdown('<div class="large-space"></div>', unsafe_allow_html=True)
st.markdown('<div class="section-label">RECENT SENTIMENT</div>', unsafe_allow_html=True)
st.caption("Tone of recent news headlines, scored automatically.")

sentiment_slot = st.empty()

with sentiment_slot.container():
    skeleton_card()

with st.spinner(f"Checking recent news for {ticker}..."):
    try:
        sentiment = load_sentiment(ticker)
        sentiment_slot.empty()
        sentiment_card(sentiment)
    except Exception as error:
        sentiment_slot.empty()
        st.error(f"Unable to load sentiment: {error}")

# ==========================================================
# BUILD TIMELINE
# ==========================================================

years = list(range(MOST_RECENT_FILING_YEAR, MOST_RECENT_FILING_YEAR - YEARS_TO_SHOW, -1))

st.markdown('<div class="large-space"></div>', unsafe_allow_html=True)
st.markdown(f'<div class="section-label">{html.escape(ticker)} - YEAR BY YEAR</div>', unsafe_allow_html=True)
st.caption("Pick a year to see management's own account of the business for that filing.")

if "storyline_selected_year" not in st.session_state or st.session_state.get("storyline_selected_ticker") != ticker:
    st.session_state.storyline_selected_year = years[0]
    st.session_state.storyline_selected_ticker = ticker
    st.session_state.storyline_loaded_years = set()  # reset when ticker changes

if "storyline_loaded_years" not in st.session_state:
    st.session_state.storyline_loaded_years = set()

loading = st.session_state.get("storyline_loading", False)

selected_year = st.segmented_control(
    "Select year",
    options=years,
    default=st.session_state.storyline_selected_year,
    label_visibility="collapsed",
    disabled=loading,
    key="storyline_selected_year",
)

# Whether this year was already loaded earlier in the session -
# session_state.storyline_loaded_years is the source of truth for
# that (populated below each time load_year_summary succeeds), so
# this just checks membership rather than recomputing anything.
already_loaded = selected_year in st.session_state.storyline_loaded_years

st.session_state.storyline_loading = True
spinner_text = f"Loading {selected_year} for {ticker}..." if not already_loaded else f"Fetching {selected_year} (cached)..."

story_slot = st.empty()

with story_slot.container():
    skeleton_bullets(7)

with st.spinner(spinner_text):
    try:
        result = load_year_summary(ticker, selected_year)
        st.session_state.storyline_loaded_years.add(selected_year)
    except Exception as error:
        story_slot.empty()
        st.error(f"Unable to load {selected_year}: {error}")
        result = None
st.session_state.storyline_loading = False

story_slot.empty()

if st.session_state.storyline_loaded_years:
    loaded_str = ", ".join(str(y) for y in sorted(st.session_state.storyline_loaded_years, reverse=True))
    st.caption(f"✓ Loaded this session: {loaded_str}")

if result is None:
    timeline_gap(selected_year)
else:
    timeline_entry(
        selected_year,
        result.get("summary", ""),
        result.get("is_diff", False),
    )

# ==========================================================
# DISCLAIMER
# ==========================================================

st.markdown(
    """
<div class="dashboard-footer">
    <strong>Investor Assistant</strong> &middot; The Story So Far
    <br>
    Drawn from SEC 10-K filings and recent news headlines, summarized for research and
    educational purposes only. Not investment advice.
</div>
""",
    unsafe_allow_html=True,
)