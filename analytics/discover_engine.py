# ==========================================================
# DISCOVER ENGINE
# ==========================================================
# For someone who doesn't have a ticker in mind yet. A short quiz
# maps to a risk tier + sector; that looks up a CURATED pool of
# well-known tickers for that combination, which then gets RANKED
# LIVE by Health Score (see rank_by_score() below and
# UI/pages/3_discover.py) - the page shows the top matches from that
# pool, not the pool in a fixed order.
#
# WHY RANK A POOL INSTEAD OF JUST DISPLAYING ONE:
# An earlier version showed exactly 3 fixed tickers per cell in a
# fixed order - which meant the "selection" was entirely my taste,
# with a real Health Score bolted on after the fact for flavor. That
# wasn't actually finding anything. Widening the pool (6 tickers per
# cell) and ranking it live by Health Score means the ones actually
# shown are the ones that score best RIGHT NOW within that pool -
# genuinely data-driven, even though the pool itself is still hand-
# picked and bounded (see below for why bounded is still the right
# call, rather than screening the whole market).
#
# WHY STILL A BOUNDED POOL, NOT A LIVE SCREEN OF THE WHOLE MARKET:
# A bounded, disclosed list is closer to what the SEC calls "an
# objective report of facts on a non-selective basis" than an opaque
# personalized pick from the whole market would be. It's also an
# engineering constraint: scoring is one financials fetch + one
# sector lookup per ticker, so scoring the whole market on every
# quiz submission isn't viable without a pre-computed batch-scoring
# subsystem, which is a genuinely bigger feature (a real Screener)
# than this quiz was ever meant to be. See the module's git history /
# project notes for that tradeoff discussion.
#
# WHY THE "WHY" LINE ISN'T HAND-WRITTEN OPINION COPY:
# Every suggestion's rationale is generated from this app's own
# Health Score at display time (see UI/pages/3_discover.py), not
# written here as persuasive text about the company. That keeps
# suggestions grounded in the same data-driven scoring used
# everywhere else in the app, rather than editorial opinion.
#
# THIS IS NOT INVESTMENT ADVICE. Tickers below were chosen by hand
# as recognizable examples for demonstration purposes and are NOT
# vetted, current, or endorsed recommendations - see the disclaimer
# rendered on the Discover page itself. Review and refresh this
# list periodically; it will go stale.

RISK_TIERS = ["Conservative", "Balanced", "Growth"]

# Friendly quiz label -> real Yahoo Finance sector string (must match
# sector_profiles.py / sector_lookup.py exactly, since suggestions
# are scored using the same sector-aware Health Score as everywhere
# else in the app).
SECTOR_OPTIONS = {
    "Technology": "Technology",
    "Healthcare": "Healthcare",
    "Banks & Financial": "Financial Services",
    "Consumer Brands": "Consumer Cyclical",
    "Industrial & Manufacturing": "Industrials",
    "Energy": "Energy",
}

# sector -> risk tier -> candidate tickers (16 per cell). This is the
# POOL that gets ranked live by Health Score - not the final display
# list. The page shows the top few as cards plus the full ranked pool
# in an expandable table. See the module docstring above for why it's
# still hand-picked and bounded rather than a live market-wide screen.
CURATED_UNIVERSE = {
    "Technology": {
        "Conservative": [
            "MSFT", "AAPL", "ORCL", "IBM", "TXN", "QCOM", "ACN", "ADI",
            "AMAT", "CSCO", "HPQ", "INTC", "MSI", "ROP", "TEL", "GLW",
        ],
        "Balanced": [
            "GOOGL", "ADBE", "WDAY", "INTU", "AMD", "NOW", "CRM", "PANW",
            "ANET", "KLAC", "LRCX", "SNPS", "CDNS", "MU", "NXPI", "FTNT",
        ],
        "Growth": [
            "PLTR", "CRWD", "NET", "DDOG", "SNOW", "MDB", "ZS", "OKTA",
            "TEAM", "HUBS", "TWLO", "CFLT", "GTLB", "S", "ESTC", "PATH",
        ],
    },
    "Healthcare": {
        "Conservative": [
            "JNJ", "ABBV", "PFE", "MRK", "ABT", "BMY", "AMGN", "GILD",
            "MDT", "CVS", "CI", "ELV", "BDX", "ZBH", "BAX", "EW",
        ],
        "Balanced": [
            "UNH", "LLY", "TMO", "DHR", "ISRG", "SYK", "BSX", "HCA",
            "MCK", "COR", "IQV", "A", "RMD", "WST", "DXCM", "PODD",
        ],
        "Growth": [
            "VRTX", "REGN", "MRNA", "ALNY", "EXAS", "NBIX", "INCY", "BMRN",
            "SRPT", "IONS", "UTHR", "NTRA", "TECH", "RARE", "CRSP", "ARWR",
        ],
    },
    "Financial Services": {
        "Conservative": [
            "JPM", "BRK-B", "USB", "WFC", "BAC", "PNC", "TFC", "CB",
            "TRV", "AON", "MMC", "AJG", "BK", "STT", "CME", "SPGI",
        ],
        "Balanced": [
            "GS", "MS", "SCHW", "AXP", "BLK", "ICE", "MCO", "NDAQ",
            "COF", "DFS", "SYF", "FITB", "KEY", "RF", "HBAN", "CFG",
        ],
        "Growth": [
            "SOFI", "COIN", "UPST", "AFRM", "HOOD", "NU", "TOST", "LC",
            "MARA", "BILL", "PYPL", "SQ", "TREE", "OPFI", "PGY", "DAVE",
        ],
    },
    "Consumer Cyclical": {
        "Conservative": [
            "MCD", "HD", "NKE", "LOW", "TJX", "YUM", "SBUX", "ORLY",
            "AZO", "GPC", "DPZ", "DRI", "GRMN", "POOL", "TSCO", "BBY",
        ],
        "Balanced": [
            "TGT", "BKNG", "ROST", "MAR", "CMG", "HLT", "LULU", "EBAY",
            "GM", "F", "APTV", "LVS", "MGM", "RCL", "CCL", "EXPE",
        ],
        "Growth": [
            "TSLA", "CVNA", "ABNB", "RIVN", "DKNG", "W", "CHWY", "ETSY",
            "LCID", "RH", "WSM", "DASH", "UBER", "LYFT", "PTON", "SHAK",
        ],
    },
    "Industrials": {
        "Conservative": [
            "HON", "CAT", "UNP", "LMT", "MMM", "ITW", "GD", "NOC",
            "RTX", "EMR", "CSX", "NSC", "PCAR", "CMI", "PNR", "DOV",
        ],
        "Balanced": [
            "BA", "GE", "DE", "ETN", "PH", "URI", "FDX", "UPS",
            "WM", "RSG", "CARR", "OTIS", "JCI", "TT", "IR", "SWK",
        ],
        "Growth": [
            "RKLB", "AXON", "GEV", "JOBY", "ACHR", "ASTS", "LDOS", "BWXT",
            "PWR", "FIX", "BLDR", "SAIA", "XPO", "GNRC", "PLUG", "BE",
        ],
    },
    "Energy": {
        "Conservative": [
            "XOM", "CVX", "COP", "PSX", "VLO", "MPC", "EPD", "ET",
            "TRGP", "LNG", "BKR", "HAL", "OKE", "KMI", "WMB", "DTM",
        ],
        "Balanced": [
            "SLB", "EOG", "HES", "PXD", "MRO", "CTRA", "AR", "EQT",
            "RRC", "SWN", "NOV", "CHX", "WFRD", "TDW", "HP", "PTEN",
        ],
        "Growth": [
            "OXY", "DVN", "FANG", "APA", "MTDR", "CHRD", "SM", "CRC",
            "GPOR", "CNX", "MGY", "VTLE", "TALO", "REPX", "AMPY", "BRY",
        ],
    },
}

# ----------------------------------------------------------
# QUIZ -> RISK TIER
# ----------------------------------------------------------
# Two questions instead of one self-rating, following the pattern
# robo-advisors (Wealthfront, Betterment) use: a direct self-rating
# is known to be inflated (people, especially under-35s, tend to
# overestimate their own risk tolerance), so a scenario question is
# paired with it as a consistency check. When the two disagree by a
# lot, we trust the MORE CONSERVATIVE answer rather than averaging -
# same principle Wealthfront describes: inconsistency lowers the
# score, it doesn't just get averaged away.

SELF_RATING_OPTIONS = {
    "Play it safe": 1,
    "Some ups and downs are fine": 2,
    "I'm fine with big swings for bigger potential gains": 3,
}

SCENARIO_OPTIONS = {
    "Sell to stop the loss": 1,
    "Hold and wait it out": 2,
    "Buy more at the lower price": 3,
}

GOAL_OPTIONS = ["Long-term growth", "Steady & stable", "Just exploring"]

_INCONSISTENCY_THRESHOLD = 2  # scores are 1-3, so a gap of 2 means opposite ends


def _tier_from_score(score: float) -> str:
    """Map a combined 1-3 score to a risk tier, clamping to valid range."""
    index = round(score) - 1
    index = max(0, min(len(RISK_TIERS) - 1, index))
    return RISK_TIERS[index]


def _nudge_tier(tier: str, steps: int) -> str:
    """Move a tier up/down the RISK_TIERS ladder, clamped at the ends."""
    index = RISK_TIERS.index(tier) + steps
    index = max(0, min(len(RISK_TIERS) - 1, index))
    return RISK_TIERS[index]


def compute_risk_tier(self_rating_label: str, scenario_label: str, goal_label: str) -> str:
    """
    Combine the self-rated risk question, the scenario consistency
    check, and the stated goal into one risk tier.

    - If the two risk answers roughly agree, average them.
    - If they disagree sharply (e.g. "play it safe" but "buy more on
      the dip"), trust the more conservative of the two rather than
      averaging - an inconsistent answer is a signal of overclaiming
      risk tolerance, not a genuinely moderate one.
    - The stated goal then nudges the tier by at most one step, so a
      "steady & stable" goal pulls toward safer suggestions even for
      someone who scored themselves as risk-tolerant, and vice versa.
    """
    self_score = SELF_RATING_OPTIONS.get(self_rating_label)
    scenario_score = SCENARIO_OPTIONS.get(scenario_label)

    if self_score is None or scenario_score is None:
        base_tier = "Balanced"
    elif abs(self_score - scenario_score) >= _INCONSISTENCY_THRESHOLD:
        base_tier = _tier_from_score(min(self_score, scenario_score))
    else:
        base_tier = _tier_from_score((self_score + scenario_score) / 2)

    if goal_label == "Steady & stable":
        return _nudge_tier(base_tier, -1)
    if goal_label == "Long-term growth":
        return _nudge_tier(base_tier, +1)
    return base_tier


def get_suggestions(sector: str, risk_tier: str, max_results: int | None = None) -> list[str]:
    """
    Return candidate tickers for a sector + risk tier - the pool to
    be ranked, not necessarily the final display list. max_results
    caps the pool size if given; omit it to get every candidate.
    """
    pool = CURATED_UNIVERSE.get(sector, {}).get(risk_tier, [])
    return pool if max_results is None else pool[:max_results]


def rank_by_score(tickers: list[str], score_fn, max_results: int = 4) -> list[tuple[str, float | None]]:
    """
    Rank tickers by a score obtained from score_fn(ticker) -> float | None,
    highest first, returning (ticker, score) pairs.

    score_fn is injected rather than imported directly so this stays
    a pure, fast function to test - the caller (UI/pages/3_discover.py)
    supplies a score_fn backed by the real Health Score, while tests
    can supply a fake one with no network calls.

    Tickers whose score_fn returns None (data temporarily unavailable)
    are kept and sorted to the end in their original order, rather
    than silently dropped - a missing score is still worth surfacing,
    just not worth ranking highly.
    """
    scored = [(ticker, score_fn(ticker)) for ticker in tickers]
    with_score = sorted(
        (pair for pair in scored if pair[1] is not None),
        key=lambda pair: pair[1],
        reverse=True,
    )
    without_score = [pair for pair in scored if pair[1] is None]
    return (with_score + without_score)[:max_results]