# ==========================================================
# VALUATION
# ==========================================================
# Everything else in this app answers "is this a good business?".
# This module answers the other half of the question: "is it priced
# like one?"
#
# Those are genuinely independent. A company can be excellent and a
# poor investment at the same time, because the quality is already in
# the price - which is why a health score alone can quietly mislead
# someone into thinking a high number means "buy". Nothing here
# produces a buy/sell call; it produces context, phrased so a reader
# understands what a multiple is telling them.
#
# ----------------------------------------------------------
# WHY SECTOR BANDS, AND HOW MUCH TO TRUST THEM
# ----------------------------------------------------------
# Multiples are only interpretable against a peer group. A 30x P/E is
# ordinary for software and expensive for a bank, because banks are
# capital-constrained and grow slowly while software compounds. The
# bands below are broad "typical range" figures for each sector, not
# a live peer screen - so they place a company loosely rather than
# precisely. They are wide on purpose: a narrow band would imply an
# accuracy this data doesn't have.
#
# Ranges reflect long-run sector norms rather than any single moment
# in the cycle, so a whole sector re-rating (as energy and tech both
# have) will push many of its companies outside these bands at once.
# That is information, not an error - but it means "above the band"
# should be read as "expensive relative to this sector's history",
# not "overvalued".

# sector -> (typical low P/E, typical high P/E)
SECTOR_PE_BANDS = {
    "Technology": (20, 35),
    "Healthcare": (15, 28),
    "Financial Services": (8, 16),
    "Consumer Cyclical": (14, 25),
    "Consumer Defensive": (15, 24),
    "Energy": (8, 16),
    "Industrials": (15, 25),
    "Utilities": (14, 22),
    "Real Estate": (20, 40),
    "Basic Materials": (10, 20),
    "Communication Services": (14, 25),
}

DEFAULT_PE_BAND = (12, 25)

# Sectors where a plain P/E is a genuinely poor tool, and saying so
# is more useful than ranking the number. REIT net income is pushed
# down by large non-cash depreciation charges, so REITs are valued on
# funds from operations (FFO) instead; bank earnings depend on
# reserve and mark-to-market accounting that makes cross-company P/E
# comparison shakier than it looks.
_PE_CAVEATS = {
    "Real Estate": (
        "REITs are normally valued on funds from operations rather than "
        "earnings, because depreciation depresses their reported net income. "
        "Treat this P/E as a rough placeholder."
    ),
    "Financial Services": (
        "Bank and insurer earnings swing with reserve and mark-to-market "
        "accounting, so price-to-book is often the more stable read here."
    ),
}

# Market capitalization tiers, in dollars. These are the conventional
# US market boundaries.
_MARKET_CAP_TIERS = [
    (200_000_000_000, "Mega cap"),
    (10_000_000_000, "Large cap"),
    (2_000_000_000, "Mid cap"),
    (300_000_000, "Small cap"),
    (0, "Micro cap"),
]


def get_pe_band(sector):
    """Typical (low, high) P/E for a sector, falling back to a general band."""
    return SECTOR_PE_BANDS.get(sector, DEFAULT_PE_BAND)


def get_pe_caveat(sector):
    """A warning about P/E's usefulness in this sector, or None."""
    return _PE_CAVEATS.get(sector)


def classify_pe(pe, sector=None):
    """
    Place a P/E ratio against its sector's typical band.

    Returns (label, css_class, explanation). A None or negative P/E
    is not "cheap" - it means the company has no trailing profit to
    divide by, which is a different statement entirely and is
    reported as such.
    """
    if pe is None:
        return (
            "Not available",
            "neutral",
            "No trailing price-to-earnings ratio is available for this company.",
        )

    if pe <= 0:
        return (
            "No earnings",
            "warning",
            "This company has no trailing twelve-month profit, so a "
            "price-to-earnings ratio can't be calculated. That is common for "
            "early-stage and turnaround companies - it is not the same as "
            "being cheap.",
        )

    low, high = get_pe_band(sector)
    sector_name = sector or "the broader market"

    if pe < low:
        return (
            "Below sector norm",
            "positive",
            f"At {pe:.1f}x earnings, this trades below the {low:.0f}-{high:.0f}x "
            f"range typical for {sector_name}. That can mean it's overlooked, "
            f"or that the market expects earnings to fall.",
        )

    if pe <= high:
        return (
            "In line with sector",
            "neutral",
            f"At {pe:.1f}x earnings, this sits inside the {low:.0f}-{high:.0f}x "
            f"range typical for {sector_name}.",
        )

    if pe <= high * 2:
        return (
            "Above sector norm",
            "warning",
            f"At {pe:.1f}x earnings, this trades above the {low:.0f}-{high:.0f}x "
            f"range typical for {sector_name}. Investors are paying up for "
            f"expected growth, which leaves less room for disappointment.",
        )

    return (
        "Richly valued",
        "negative",
        f"At {pe:.1f}x earnings, this trades far above the {low:.0f}-{high:.0f}x "
        f"range typical for {sector_name}. Multiples this high depend on "
        f"years of strong growth actually arriving.",
    )


def earnings_yield(pe):
    """
    The inverse of P/E, as a percentage - what you'd earn annually per
    dollar invested if profits stayed flat and were all paid out.

    Useful because it's directly comparable to a bond yield, which is
    a far more intuitive framing than "22x" for most people.
    """
    if pe is None or pe <= 0:
        return None

    return (1 / pe) * 100


def classify_beta(beta):
    """
    Translate a stock's beta into a plain statement about how it has
    historically moved relative to the broader market.

    Beta is a pure descriptor, not a judgment - the way describe_range_
    position never calls a 52-week low "bad". A beginner favoring calm
    names and one deliberately chasing leveraged upside want opposite
    answers from the same number, so every band here renders neutral
    rather than positive/negative the way a margin does.

    Returns (label, css_class, explanation).
    """
    if beta is None:
        return (
            "Not available",
            "neutral",
            "No volatility estimate is available for this company.",
        )

    magnitude = abs(beta - 1) * 100

    if beta < 0:
        return (
            "Tends to move opposite the market",
            "neutral",
            f"With a beta of {beta:.2f}, this stock has historically moved "
            f"against the broader market rather than with it - an unusual "
            f"pattern, seen more often in gold miners or inverse funds than "
            f"ordinary companies.",
        )

    if beta < 0.8:
        return (
            "Calmer than the market",
            "neutral",
            f"With a beta of {beta:.2f}, this stock has historically moved "
            f"about {magnitude:.0f}% less than the S&P 500 in either "
            f"direction - smaller gains in rallies, smaller losses in "
            f"selloffs.",
        )

    if beta <= 1.2:
        return (
            "Moves with the market",
            "neutral",
            f"With a beta of {beta:.2f}, this stock has historically tracked "
            f"the S&P 500 fairly closely.",
        )

    if beta <= 1.6:
        return (
            "More volatile than the market",
            "neutral",
            f"With a beta of {beta:.2f}, this stock has historically moved "
            f"about {magnitude:.0f}% more than the S&P 500 in either "
            f"direction - bigger gains in rallies, bigger losses in "
            f"selloffs.",
        )

    return (
        "Highly volatile",
        "neutral",
        f"With a beta of {beta:.2f}, this stock has historically swung "
        f"roughly {beta:.1f}x as much as the market in either direction - "
        f"sharp rallies and sharp drops both, more often than the typical "
        f"stock.",
    )


def market_cap_tier(market_cap):
    """Conventional size label for a market capitalization."""
    if market_cap is None or market_cap <= 0:
        return None

    for threshold, label in _MARKET_CAP_TIERS:
        if market_cap >= threshold:
            return label

    return "Micro cap"


def describe_range_position(position):
    """
    Turn a 0-100 position within the 52-week range into words.

    Deliberately descriptive rather than predictive: being near a
    52-week low says nothing about direction, and phrasing that
    implies otherwise would be the app making a call it can't support.
    """
    if position is None:
        return None

    if position >= 90:
        return "Trading near its 52-week high"
    if position >= 60:
        return "In the upper half of its 52-week range"
    if position >= 40:
        return "Around the middle of its 52-week range"
    if position >= 10:
        return "In the lower half of its 52-week range"

    return "Trading near its 52-week low"


def growth_adjusted_read(pe, revenue_growth):
    """
    Compare a P/E against the company's growth rate - the intuition
    behind the PEG ratio, without pretending to the false precision
    of a single number.

    A 40x multiple on a business growing 40% a year is a very
    different proposition from 40x on one growing 3%, and judging the
    multiple in isolation misses that entirely.

    Returns (label, css_class, explanation), or None when there isn't
    enough to say.
    """
    if pe is None or pe <= 0 or revenue_growth is None:
        return None

    if revenue_growth <= 0:
        return (
            "Paying up without growth",
            "warning",
            f"Revenue isn't growing, yet the stock trades at {pe:.1f}x earnings. "
            f"A multiple has to be justified by either growth or durability - "
            f"here it would have to be durability.",
        )

    ratio = pe / revenue_growth

    if ratio < 1:
        return (
            "Growth exceeds the multiple",
            "positive",
            f"Revenue is growing {revenue_growth:.1f}% a year against a "
            f"{pe:.1f}x multiple. On that comparison the price looks modest "
            f"relative to the growth being delivered.",
        )

    if ratio <= 2:
        return (
            "Multiple broadly matches growth",
            "neutral",
            f"A {pe:.1f}x multiple against {revenue_growth:.1f}% revenue growth "
            f"is a fairly conventional pairing.",
        )

    return (
        "Multiple runs ahead of growth",
        "warning",
        f"A {pe:.1f}x multiple against {revenue_growth:.1f}% revenue growth "
        f"means a lot of future improvement is already in the price.",
    )


def build_valuation_reads(snapshot, sector=None, kpis=None):
    """
    Assemble every valuation observation we can support for a company.

    Returns a list of {title, label, status, explanation} dicts, in
    the order they're worth reading. Observations with no data behind
    them are omitted rather than rendered as "N/A" rows - a page of
    blanks reads as brokenness, while a shorter page reads as honesty.
    """
    if not snapshot:
        return []

    kpis = kpis or {}
    reads = []

    trailing_pe = snapshot.get("trailing_pe")
    label, status, explanation = classify_pe(trailing_pe, sector)

    caveat = get_pe_caveat(sector)
    if caveat and trailing_pe is not None and trailing_pe > 0:
        explanation = f"{explanation} {caveat}"

    reads.append({
        "title": "Price to earnings",
        "label": label,
        "status": status,
        "explanation": explanation,
    })

    growth_read = growth_adjusted_read(trailing_pe, kpis.get("revenue_growth"))

    if growth_read:
        growth_label, growth_status, growth_explanation = growth_read
        reads.append({
            "title": "Multiple vs. growth",
            "label": growth_label,
            "status": growth_status,
            "explanation": growth_explanation,
        })

    forward_pe = snapshot.get("forward_pe")

    if forward_pe is not None and trailing_pe is not None and forward_pe > 0 and trailing_pe > 0:
        if forward_pe < trailing_pe:
            reads.append({
                "title": "Forward expectations",
                "label": "Earnings expected to rise",
                "status": "positive",
                "explanation": (
                    f"The forward multiple ({forward_pe:.1f}x) is below the "
                    f"trailing one ({trailing_pe:.1f}x), meaning analysts expect "
                    f"earnings to grow over the next year. Those are estimates, "
                    f"not results."
                ),
            })
        else:
            reads.append({
                "title": "Forward expectations",
                "label": "Earnings expected to fall",
                "status": "warning",
                "explanation": (
                    f"The forward multiple ({forward_pe:.1f}x) is above the "
                    f"trailing one ({trailing_pe:.1f}x), meaning analysts expect "
                    f"earnings to decline over the next year."
                ),
            })

    dividend_yield = snapshot.get("dividend_yield")

    if dividend_yield is not None and dividend_yield > 0:
        reads.append({
            "title": "Dividend",
            "label": f"{dividend_yield:.2f}% yield",
            "status": "positive" if dividend_yield >= 2 else "neutral",
            "explanation": (
                f"Pays {dividend_yield:.2f}% a year in dividends at the current "
                f"price. A high yield can reflect a generous payout or a falling "
                f"share price, so it's worth checking which."
            ),
        })

    beta = snapshot.get("beta")

    if beta is not None:
        beta_label, beta_status, beta_explanation = classify_beta(beta)
        reads.append({
            "title": "Volatility (beta)",
            "label": beta_label,
            "status": beta_status,
            "explanation": beta_explanation,
        })

    position = describe_range_position(snapshot.get("range_position"))

    if position:
        reads.append({
            "title": "52-week range",
            "label": position,
            "status": "neutral",
            "explanation": (
                "Where the price sits relative to its own past year. This "
                "describes where it has been, not where it is going."
            ),
        })

    return reads
