# ==========================================================
# HEALTH SCORE
# ==========================================================
# Combines the dashboard's existing KPIs into a single 0-100 score,
# so two companies can be compared with one headline number instead
# of six separate metrics.
#
# Each KPI is on a different scale (percent, ratio, dollars), so we
# can't just average the raw numbers. Instead each one is first
# "normalized" onto a common 0-100 scale using a min/max range for
# that metric, then combined with weights reflecting how much it
# should matter to the overall score.
#
# The normalization ranges are SECTOR-AWARE (see sector_profiles.py)
# - a 25% profit margin means something different for a software
# company than a grocery retailer, so scoring both against the same
# fixed range would be misleading. Pass a sector string (e.g.
# "Technology") to calculate_health_score() to use that sector's
# ranges; omit it (or pass an unrecognized sector) to fall back to
# the general-purpose default ranges.

from analytics.sector_profiles import get_ranges_for_sector


# ----------------------------------------------------------
# CONFIG: weight + direction per metric
# ----------------------------------------------------------
# These stay the same across all sectors

_METRIC_WEIGHTS = {
    "net_profit_margin": (0.20, False),
    "roe":               (0.20, False),
    "revenue_growth":    (0.15, False),
    "earnings_growth":   (0.15, False),
    "debt_to_equity":    (0.15, True),
    "current_ratio":     (0.10, False),
}

# ----------------------------------------------------------
# CASH GENERATION
# ----------------------------------------------------------
# Free cash flow is a dollar amount, so it can't share the percentage
# and ratio ranges above - a $2B FCF is enormous for a mid-cap and
# unremarkable for Apple. It used to be scored as a binary coin flip
# (positive = 100, negative = 0), which meant a business converting
# 30% of revenue into cash scored identically to one scraping by at
# 0.2%.
#
# Scoring FCF MARGIN (free cash flow / revenue) instead makes it
# size-independent and actually discriminating. The 0-20% range is a
# reasonable cross-sector span: sustained FCF margins above ~20% are
# the mark of an unusually cash-generative business, and negative
# margins clamp to zero.
#
# When revenue is unavailable we fall back to the old positive/
# negative test rather than dropping cash generation from the score
# entirely - a weak signal beats no signal here.

_FREE_CASH_FLOW_WEIGHT = 0.05
_FCF_MARGIN_RANGE = (0, 20)


def _normalize(value, minimum, maximum, invert):
    """Map a raw value onto a 0-100 scale, clamped at the edges."""

    if maximum == minimum:
        return 50.0  # avoid divide-by-zero; treat as neutral

    score = (value - minimum) / (maximum - minimum) * 100
    score = max(0.0, min(100.0, score))  # clamp to 0-100

    if invert:
        score = 100 - score

    return score


def calculate_health_score(kpis, sector=None):
    """

    Combine a company's KPIs into one weighted 0-100 score, scored
    against ranges appropriate to its sector.

    """

    ranges = get_ranges_for_sector(sector)

    breakdown = []
    weighted_total = 0.0
    weight_used = 0.0

    for metric, (weight, invert) in _METRIC_WEIGHTS.items():
        raw_value = kpis.get(metric)

        if raw_value is None:
            continue  # skip metrics with missing data entirely

        minimum, maximum = ranges.get(metric)
        normalized = _normalize(raw_value, minimum, maximum, invert)

        breakdown.append({
            "metric": metric,
            "raw_value": raw_value,
            "normalized": normalized,
            "weight": weight,
        })

        weighted_total += normalized * weight
        weight_used += weight

    # Cash generation: scored on FCF margin where revenue is known,
    # falling back to a positive/negative test where it isn't.
    fcf_margin = kpis.get("fcf_margin")
    free_cash_flow = kpis.get("free_cash_flow")

    if fcf_margin is not None:
        minimum, maximum = _FCF_MARGIN_RANGE
        normalized = _normalize(fcf_margin, minimum, maximum, invert=False)
        raw_value = fcf_margin
    elif free_cash_flow is not None:
        normalized = 100.0 if free_cash_flow > 0 else 0.0
        raw_value = free_cash_flow
    else:
        normalized = None
        raw_value = None

    if normalized is not None:
        breakdown.append({
            "metric": "free_cash_flow",
            "raw_value": raw_value,
            "normalized": normalized,
            "weight": _FREE_CASH_FLOW_WEIGHT,
        })

        weighted_total += normalized * _FREE_CASH_FLOW_WEIGHT
        weight_used += _FREE_CASH_FLOW_WEIGHT

    if weight_used == 0:
        return None, []  # no usable data at all

    # Re-normalize by the weight actually used, so a company missing
    # one or two metrics isn't unfairly penalized just for missing
    # data (its score is based on what we DO know, scaled back up
    # to a full 100).
    score = weighted_total / weight_used

    return round(score, 1), breakdown


def get_score_label(score):
    """Map a 0-100 health score to a (label, css_class) pair."""

    if score is None:
        return "N/A", "neutral"

    if score >= 80:
        return "Excellent", "positive"
    elif score >= 65:
        return "Strong", "positive"
    elif score >= 50:
        return "Moderate", "neutral"
    elif score >= 35:
        return "Weak", "warning"
    else:
        return "Poor", "negative"


# Human-readable labels for chart axes / tables, since the raw
# metric keys ("net_profit_margin") aren't display-friendly.
METRIC_DISPLAY_NAMES = {
    "net_profit_margin": "Profit Margin",
    "roe": "Return on Equity",
    "revenue_growth": "Revenue Growth",
    "earnings_growth": "Earnings Growth",
    "debt_to_equity": "Low Leverage",  # framed as "higher = better" since normalized score is already inverted
    "current_ratio": "Liquidity",
    "free_cash_flow": "Cash Generation",
}


# ==========================================================
# EXPLAINING THE SCORE
# ==========================================================
# A single 0-100 number is only trustworthy if you can see where it
# came from. Two things determine that:
#
#   1. WHICH metrics pushed it up or held it down, and by how much.
#   2. HOW MUCH of the company's data was actually available - a
#      score built from three metrics is a far weaker claim than one
#      built from all seven, and previously nothing in the app said
#      so. calculate_health_score() re-normalizes by the weight it
#      actually used, which is the right call (it avoids penalizing a
#      company for a data gap) but has the side effect of making a
#      thin score look exactly as confident as a complete one.

# Sum of every weight a company could possibly score on, used as the
# denominator for data coverage.
_TOTAL_POSSIBLE_WEIGHT = (
    sum(weight for weight, _ in _METRIC_WEIGHTS.values()) + _FREE_CASH_FLOW_WEIGHT
)


def score_coverage(breakdown):
    """
    Fraction (0-1) of the total possible metric weight that had data
    behind it. 1.0 means every metric was available.
    """
    if not breakdown:
        return 0.0

    return sum(row["weight"] for row in breakdown) / _TOTAL_POSSIBLE_WEIGHT


def coverage_label(coverage):
    """Map a coverage fraction to a (label, css_class) confidence pair."""
    if coverage >= 0.95:
        return "Complete data", "positive"
    if coverage >= 0.75:
        return "Mostly complete", "neutral"
    if coverage >= 0.5:
        return "Partial data", "warning"
    return "Sparse data", "negative"


def explain_score(breakdown, limit=3):
    """
    Turn a score breakdown into the story behind the number.

    Returns a dict with:
      strengths - metrics contributing the most points, best first
      drags     - metrics costing the most points, worst first
      coverage  - fraction of possible metric weight backed by data

    Each entry carries `contribution` (points this metric added to the
    final 0-100 score) and `points_lost` (points it gave up against a
    perfect 100 on that metric). Because the final score is
    re-normalized by the weight actually used, both are expressed
    relative to that same denominator - so contributions across all
    metrics sum to the score, and points_lost sums to 100 minus it.
    """
    if not breakdown:
        return {"strengths": [], "drags": [], "coverage": 0.0}

    weight_used = sum(row["weight"] for row in breakdown)

    if weight_used == 0:
        return {"strengths": [], "drags": [], "coverage": 0.0}

    rows = []

    for row in breakdown:
        share = row["weight"] / weight_used

        rows.append({
            "metric": row["metric"],
            "label": METRIC_DISPLAY_NAMES.get(row["metric"], row["metric"]),
            "raw_value": row["raw_value"],
            "normalized": row["normalized"],
            "weight": row["weight"],
            "contribution": row["normalized"] * share,
            "points_lost": (100.0 - row["normalized"]) * share,
        })

    strengths = sorted(rows, key=lambda row: row["contribution"], reverse=True)
    drags = sorted(rows, key=lambda row: row["points_lost"], reverse=True)

    # A metric scoring at or near the top of its sector range isn't a
    # "drag" worth naming even if it's technically the weakest one, and
    # the same in reverse - so filter rather than always showing `limit`.
    strengths = [row for row in strengths if row["normalized"] >= 50][:limit]
    drags = [row for row in drags if row["normalized"] < 50][:limit]

    return {
        "strengths": strengths,
        "drags": drags,
        "coverage": score_coverage(breakdown),
    }