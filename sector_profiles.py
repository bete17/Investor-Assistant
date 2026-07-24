# SECTOR PROFILES
# ==========================================================
# Different industries have structurally different "normal" ranges
# for the same metric - a 25% profit margin is unremarkable for a
# software company but exceptional for a grocery retailer. Scoring
# every company against one fixed range systematically favors
# certain sectors regardless of how well-run the company actually
# is, so calibrating by sector is a real improvement over a single
# fixed range.
#
# Sector names match Yahoo Finance's sector classification
# (yfinance's Ticker.info["sector"]), matching sector_lookup.py.
#
# ----------------------------------------------------------
# SOURCES / METHODOLOGY
# ----------------------------------------------------------
# net_profit_margin, roe:
#   Derived from Aswath Damodaran's NYU Stern industry dataset
#   (https://pages.stern.nyu.edu/~adamodar/New_Home_Page/datafile/margin.html
#   and .../datafile/roe.html), data as of January 2026. each Yahoo
#   Finance sector below was built by averaging the
#   Damodaran industries that roll up into it. 
#
# debt_to_equity:
#   Damodaran reports market-value debt ratios, while
#   kpi_engine uses book-value Total Debt / Book Equity. Book D/E
#   can be higher than market D/E for buyback-heavy firms, so
#   sector ranges are widened to plausible book-value levels.
#
# current_ratio:
#   No single authoritative cross-sector dataset exists for this
#   (Damodaran doesn't track it). These ranges are built from
#   well-established qualitative liquidity characteristics of each
#   sector (e.g. asset-light tech and cash-rich biotech run high;
#   capital-intensive utilities and REITs run low) rather than a
#   specific cited dataset. Lowest-confidence numbers in this file.
#
# revenue_growth, earnings_growth:
#   Directional, informed by sector growth/volatility patterns
#   from Damodaran's commentary and FactSet's 2025 sector earnings
#   outlook (e.g. Energy as the standout decliner, Technology
#   leading growth, Utilities/Consumer Defensive being low-growth
#   but stable). Not a precise per-sector percentile dataset.

 
# if it can't determine the sector, it uses these general market ranges instead
DEFAULT_RANGES = {
    "net_profit_margin": (0, 25),
    "roe": (0, 25),
    "revenue_growth": (-10, 20),
    "earnings_growth": (-10, 20),
    "debt_to_equity": (0, 1.5),
    "current_ratio": (0, 3),
}
 
SECTOR_RANGES = {

    "Technology": {
        "net_profit_margin": (-5, 30),
        "roe": (0, 35),
        "revenue_growth": (-10, 35),
        "earnings_growth": (-10, 35),
        # Market D/C for these industries is mostly under 25% (D/E
        # under ~0.3), but book D/E for mature, buyback-heavy tech
        # names (e.g. Oracle) can run much higher despite low real
        # leverage risk - widened accordingly.
        "debt_to_equity": (0, 2),
        "current_ratio": (0, 4),
    },
 
    # Biotech commonly runs net margin/ROE negative (pre-revenue
    # R&D-stage firms), pulling the low end well below zero.
    "Healthcare": {
        "net_profit_margin": (-10, 20),
        "roe": (-10, 30),
        "revenue_growth": (-10, 25),
        "earnings_growth": (-15, 30),
        "debt_to_equity": (0, 1.5),
        # Biotech is famously cash-rich relative to near-term
        # revenue, pushing sector current ratios high.
        "current_ratio": (0, 5),
    },
 
    "Financial Services": {
        "net_profit_margin": (0, 30),
        "roe": (0, 30),
        "revenue_growth": (-10, 15),
        "earnings_growth": (-15, 25),
        "debt_to_equity": (0, 6),
        "current_ratio": (0, 2),
    },
 

    "Consumer Cyclical": {
        "net_profit_margin": (-5, 15),
        "roe": (-10, 35),
        "revenue_growth": (-10, 20),
        "earnings_growth": (-10, 25),
        "debt_to_equity": (0, 2),
        "current_ratio": (0, 2.5),
    },
 
    "Consumer Defensive": {
        "net_profit_margin": (0, 25),
        "roe": (0, 30),
        "revenue_growth": (-5, 12),
        "earnings_growth": (-5, 15),
        "debt_to_equity": (0, 2),
        "current_ratio": (0, 2),
    },
 

    "Energy": {
        "net_profit_margin": (-15, 20),
        "roe": (-15, 20),
        "revenue_growth": (-30, 30),
        "earnings_growth": (-40, 40),
        "debt_to_equity": (0, 1.5),
        "current_ratio": (0, 2),
    },
 
    "Industrials": {
        "net_profit_margin": (0, 18),
        "roe": (0, 30),
        "revenue_growth": (-10, 20),
        "earnings_growth": (-10, 25),
        "debt_to_equity": (0, 2),
        "current_ratio": (0, 2.5),
    },
 
    "Utilities": {
        "net_profit_margin": (0, 22),
        "roe": (0, 15),
        "revenue_growth": (-5, 10),
        "earnings_growth": (-10, 15),
        "debt_to_equity": (0, 2.5),
        "current_ratio": (0, 1.5),
    },

    "Real Estate": {
        "net_profit_margin": (0, 25),
        "roe": (0, 15),
        "revenue_growth": (-5, 15),
        "earnings_growth": (-15, 20),
        "debt_to_equity": (0, 4),
        "current_ratio": (0, 1.5),
    },
 

    "Basic Materials": {
        "net_profit_margin": (-10, 25),
        "roe": (-15, 25),
        "revenue_growth": (-20, 25),
        "earnings_growth": (-30, 35),
        "debt_to_equity": (0, 1.5),
        "current_ratio": (0, 2.5),
    },
 
    "Communication Services": {
        "net_profit_margin": (-5, 20),
        "roe": (-5, 25),
        "revenue_growth": (-5, 20),
        "earnings_growth": (-10, 25),
        "debt_to_equity": (0, 2.5),
        "current_ratio": (0, 2),
    },
}
 
 
def get_ranges_for_sector(sector):
    """
    Look up the normalization ranges for a sector. Falls back to
    DEFAULT_RANGES for unknown/missing sectors (e.g. sector lookup
    failed, or a sector not covered above) so scoring never breaks
    """
 
    return SECTOR_RANGES.get(sector, DEFAULT_RANGES)