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

from sector_profiles import get_ranges_for_sector


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

# Free cash flow is handled separately since it's a dollar amount,

_FREE_CASH_FLOW_WEIGHT = 0.05


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

    # Free cash flow: simple positive/negative scoring, unaffected by sector.
    free_cash_flow = kpis.get("free_cash_flow")

    if free_cash_flow is not None:
        normalized = 100.0 if free_cash_flow > 0 else 0.0

        breakdown.append({
            "metric": "free_cash_flow",
            "raw_value": free_cash_flow,
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