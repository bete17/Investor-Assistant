# ==========================================================
# SHARED UI COMPONENTS
# ==========================================================
# Rendering helpers used by more than one page. Anything that draws
# the same thing on two pages belongs here rather than being copied,
# which is how the KPI card markup ended up duplicated between the
# dashboard and the compare page.
#
# Every function here takes plain data and writes markup. None of
# them fetch anything or compute a metric - that stays in analytics/
# and data/, so the layering the project already follows holds.
#
# All interpolated values go through html.escape, because some of it
# (company names, ticker symbols) traces back to user input or to an
# external API, and this markup is rendered with unsafe_allow_html.

import html

import streamlit as st

from analytics.valuation import market_cap_tier
from utils import format_money, format_percent, format_ratio


def _escape(value):
    return html.escape(str(value))


# ----------------------------------------------------------
# PRICE HEADER
# ----------------------------------------------------------


def price_header(ticker, snapshot, sector=None):
    """
    The company identity block: name, price, and today's move.

    Falls back to just the ticker when market data is unavailable, so
    a failed quote fetch degrades to the old header rather than an
    error - the fundamentals below it are still perfectly usable
    without a live price.
    """
    snapshot = snapshot or {}

    name = snapshot.get("name") or ticker
    price = snapshot.get("price")
    change = snapshot.get("price_change")
    change_percent = snapshot.get("price_change_percent")
    currency = snapshot.get("currency") or ""

    if price is None:
        price_block = (
            '<div class="price-value price-unavailable">Price unavailable</div>'
        )
    else:
        price_block = (
            f'<div class="price-value">{_escape(f"{price:,.2f}")}'
            f'<span class="price-currency">{_escape(currency)}</span></div>'
        )

    if change is not None and change_percent is not None:
        direction = "positive" if change >= 0 else "negative"
        sign = "+" if change >= 0 else ""
        change_block = (
            f'<div class="price-change {direction}">'
            f'{_escape(f"{sign}{change:,.2f}")} '
            f'({_escape(f"{sign}{change_percent:.2f}%")})'
            f'<span class="price-change-note">vs. previous close</span>'
            f"</div>"
        )
    else:
        change_block = ""

    meta_parts = []

    if sector:
        meta_parts.append(_escape(sector))

    tier = market_cap_tier(snapshot.get("market_cap"))
    if tier:
        meta_parts.append(_escape(tier))

    market_cap = snapshot.get("market_cap")
    if market_cap:
        meta_parts.append(_escape(format_money(market_cap)))

    meta = (
        f'<div class="price-meta">{" · ".join(meta_parts)}</div>'
        if meta_parts
        else ""
    )

    st.markdown(
        f"""
<div class="price-header">
    <div class="price-identity">
        <div class="price-name">{_escape(name)}</div>
        <div class="price-ticker">{_escape(ticker)}</div>
        {meta}
    </div>
    <div class="price-quote">
        {price_block}
        {change_block}
    </div>
</div>
""",
        unsafe_allow_html=True,
    )


# ----------------------------------------------------------
# 52-WEEK RANGE
# ----------------------------------------------------------


def range_bar(snapshot):
    """
    Where the current price sits within its 52-week band.

    Renders nothing at all when the data isn't there, rather than an
    empty track - a blank widget looks broken, an absent one doesn't.
    """
    snapshot = snapshot or {}

    low = snapshot.get("fifty_two_week_low")
    high = snapshot.get("fifty_two_week_high")
    position = snapshot.get("range_position")

    if low is None or high is None or position is None:
        return

    st.markdown(
        f"""
<div class="range-row">
    <div class="range-header">
        <span>52-Week Range</span>
        <strong>{_escape(f"{position:.0f}% of range")}</strong>
    </div>
    <div class="range-track">
        <div class="range-marker" style="left:{position}%;"></div>
    </div>
    <div class="range-scale">
        <span>{_escape(f"{low:,.2f}")}</span>
        <span>{_escape(f"{high:,.2f}")}</span>
    </div>
</div>
""",
        unsafe_allow_html=True,
    )


# ----------------------------------------------------------
# VALUATION
# ----------------------------------------------------------

# (label, snapshot key, formatter). Ordered by how often someone
# actually wants the number.
_VALUATION_STATS = [
    ("P/E (TTM)", "trailing_pe", format_ratio),
    ("Forward P/E", "forward_pe", format_ratio),
    ("Price / Sales", "price_to_sales", format_ratio),
    ("Price / Book", "price_to_book", format_ratio),
    ("Dividend Yield", "dividend_yield", format_percent),
    ("Market Cap", "market_cap", format_money),
]


def valuation_stats(snapshot):
    """
    The raw valuation multiples as a compact grid.

    Unavailable multiples are shown as "--" rather than dropped,
    because their absence is itself informative here: no P/E means no
    trailing profit, and silently omitting the row would hide that.
    """
    snapshot = snapshot or {}

    cells = []

    for label, key, formatter in _VALUATION_STATS:
        value = snapshot.get(key)
        display = formatter(value) if value is not None else "--"

        cells.append(
            f'<div class="stat-item">'
            f'<div class="stat-label">{_escape(label)}</div>'
            f'<div class="stat-value">{_escape(display)}</div>'
            f"</div>"
        )

    st.markdown(
        f'<div class="stat-grid">{"".join(cells)}</div>',
        unsafe_allow_html=True,
    )


def valuation_read(read):
    """Render one interpretive valuation observation."""
    st.markdown(
        f"""
<div class="read-card">
    <div class="read-head">
        <span class="read-title">{_escape(read["title"])}</span>
        <span class="kpi-status {read["status"]}">
            <span class="status-dot"></span>{_escape(read["label"])}
        </span>
    </div>
    <div class="read-body">{_escape(read["explanation"])}</div>
</div>
""",
        unsafe_allow_html=True,
    )


# ----------------------------------------------------------
# SCORE EXPLANATION
# ----------------------------------------------------------

# How each metric's raw value should be rendered in the driver list.
_DRIVER_FORMATTERS = {
    "net_profit_margin": format_percent,
    "roe": format_percent,
    "revenue_growth": format_percent,
    "earnings_growth": format_percent,
    "debt_to_equity": format_ratio,
    "current_ratio": format_ratio,
    "free_cash_flow": format_percent,  # scored on FCF margin
}


def driver_row(row, kind):
    """
    One metric's contribution to the health score.

    The bar shows the metric's own 0-100 normalized position within
    its sector range, not its share of the final score - that's the
    number a reader can act on ("leverage is at the bad end of the
    range for this sector"), whereas a weight share mostly describes
    our own scoring config.
    """
    formatter = _DRIVER_FORMATTERS.get(row["metric"], format_ratio)
    raw = row["raw_value"]
    display = formatter(raw) if raw is not None else "--"

    st.markdown(
        f"""
<div class="driver-row">
    <div class="driver-header">
        <span class="driver-label">{_escape(row["label"])}</span>
        <span class="driver-value">{_escape(display)}</span>
    </div>
    <div class="driver-track">
        <div class="driver-fill {kind}" style="width:{max(2.0, row["normalized"])}%;"></div>
    </div>
</div>
""",
        unsafe_allow_html=True,
    )


def coverage_note(coverage, label, css_class):
    """
    How much of the company's data the score was actually built from.

    Worth stating plainly: calculate_health_score re-normalizes by the
    weight it used, which correctly avoids penalizing a company for
    missing data but also makes a score built from three metrics look
    exactly as confident as one built from seven.
    """
    percent = coverage * 100

    st.markdown(
        f"""
<div class="coverage-note">
    <span class="kpi-status {css_class}">
        <span class="status-dot"></span>{_escape(label)}
    </span>
    <span class="coverage-text">
        Score built from {_escape(f"{percent:.0f}%")} of the metrics it weighs.
    </span>
</div>
""",
        unsafe_allow_html=True,
    )
