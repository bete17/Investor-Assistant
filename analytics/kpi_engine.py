# ==========================================================
# KPI ENGINE
# ==========================================================
# Turns raw quarterly financial statements into the handful of
# numbers the rest of the app reasons about.
#
# ----------------------------------------------------------
# WHY TTM AND YOY, AND NOT "LATEST QUARTER"
# ----------------------------------------------------------
# Two conventions matter here, and getting them wrong makes the whole
# app misleading rather than merely incomplete:
#
# 1. LEVEL metrics (margin, ROE, free cash flow) are computed on a
#    TRAILING TWELVE MONTH basis - the last four reported quarters
#    summed - not on the single most recent quarter.
#
#    A single quarter's net income is roughly a quarter of the annual
#    figure, so dividing it by (full, point-in-time) shareholder
#    equity produces an ROE about 4x too small. That matters because
#    sector_profiles.py benchmarks ROE against Damodaran's ANNUAL
#    industry data. Scoring a quarterly numerator against an annual
#    range meant essentially every company scored near zero on a
#    metric carrying 20% of the health score. TTM puts numerator and
#    benchmark on the same footing.
#
# 2. GROWTH metrics compare the latest quarter to THE SAME QUARTER A
#    YEAR EARLIER, not to the immediately preceding quarter.
#
#    Almost every real business is seasonal. Apple's fiscal Q2
#    revenue falls sharply from its holiday Q1 every single year;
#    retailers swing harder still. Sequential (quarter-over-quarter)
#    growth therefore reports a large "decline" for a perfectly
#    healthy company on a predictable annual cycle - and then the
#    health score docks it for that. Year-over-year is the convention
#    every earnings release and every analyst uses, precisely because
#    it cancels seasonality.
#
#    Sequential growth is still computed and exposed separately as
#    revenue_growth_qoq / earnings_growth_qoq, because it is genuinely
#    useful as a momentum read - it is just not the headline number.
#
# ----------------------------------------------------------
# GRACEFUL DEGRADATION
# ----------------------------------------------------------
# Yahoo Finance does not always return four clean quarters, and its
# date keys are not guaranteed parseable. Every function below
# degrades rather than failing: TTM falls back to the latest single
# quarter, year-over-year falls back to sequential comparison, and
# anything genuinely unknowable returns None. Each KPI reports which
# basis it actually used (see the "*_basis" keys from calculate_kpis)
# so the UI can label the number honestly instead of implying a
# precision the data doesn't support.

from datetime import datetime

from data.financials_fetcher import fetch_company_financials

# A "same quarter last year" comparison should land roughly 365 days
# back. Fiscal calendars drift (52/53-week years, period-end shifts),
# so accept a generous window rather than demanding an exact year.
_YEAR_MIN_DAYS = 300
_YEAR_MAX_DAYS = 430

# Number of quarters summed for a trailing-twelve-month figure.
_TTM_QUARTERS = 4


def _parse_date(date):
    """
    Parse a statement date string into a real datetime for sorting.
    Falls back to datetime.min on failure so unparseable dates sort
    last instead of crashing the whole KPI calculation.
    """
    if isinstance(date, datetime):
        return date

    # yfinance statement dates are typically "YYYY-MM-DD", but this
    # tries a couple of other common shapes too before giving up.
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(str(date), fmt)
        except ValueError:
            continue

    try:
        # Last resort: let Python's own parser take a shot at it.
        return datetime.fromisoformat(str(date))
    except ValueError:
        return datetime.min


def _sorted_pairs(statement, metric):
    """
    Return (parsed_date, value) pairs for this metric, sorted
    most-recent-first by ACTUAL date rather than dict/string order.

    Dict key order from the data source is not a reliable proxy for
    chronological order - a cache rewrite, a restated fiscal year, or
    a source that just doesn't guarantee ordering can all silently
    flip it. Sorting explicitly by parsed date avoids trusting it.

    None values are dropped since they represent missing data.
    """
    if metric not in statement:
        return []

    raw_values = statement[metric]

    if not isinstance(raw_values, dict):
        return []

    dated_values = [
        (_parse_date(date), value)
        for date, value in raw_values.items()
        if value is not None
    ]

    # Python's sort is stable, so entries whose dates failed to parse
    # (all datetime.min) keep the order the source gave them.
    dated_values.sort(key=lambda pair: pair[0], reverse=True)

    return dated_values


def _sorted_values(statement, metric):
    """Values only, most-recent-first. See _sorted_pairs."""
    return [value for _, value in _sorted_pairs(statement, metric)]


def get_latest_value(statement, metric):
    """Gets the latest available value for a specific financial metric."""
    values = _sorted_values(statement, metric)
    return values[0] if values else None


def get_ttm_value(statement, metric):
    """
    Sum the last four reported quarters for a flow metric (revenue,
    net income, cash flow) to get a trailing-twelve-month figure.

    Returns (value, basis) where basis is:
      "ttm"     - a genuine four-quarter sum
      "quarter" - fewer than four quarters available, so this is the
                  latest single quarter and callers should say so
      None      - no data at all

    Only ever use this for FLOW metrics that accumulate over a
    period. Balance sheet items (debt, equity, current assets) are
    point-in-time STOCKS and must not be summed - use
    get_latest_value for those.
    """
    values = _sorted_values(statement, metric)

    if not values:
        return None, None

    if len(values) >= _TTM_QUARTERS:
        return sum(values[:_TTM_QUARTERS]), "ttm"

    return values[0], "quarter"


def _find_year_ago_index(pairs):
    """
    Locate the entry in `pairs` that represents the same fiscal
    quarter one year before pairs[0].

    Returns the index, or None if no entry falls in the acceptable
    window (which happens when there's under a year of history, or
    when the source's date keys didn't parse).
    """
    if len(pairs) < 2:
        return None

    latest_date = pairs[0][0]

    # datetime.min means the dates never parsed, so day-deltas between
    # them are meaningless - don't pretend we found a year-ago match.
    if latest_date == datetime.min:
        return None

    for index in range(1, len(pairs)):
        candidate_date = pairs[index][0]

        if candidate_date == datetime.min:
            continue

        days_back = (latest_date - candidate_date).days

        if _YEAR_MIN_DAYS <= days_back <= _YEAR_MAX_DAYS:
            return index

    return None


def _percent_change(current, previous):
    """
    Percent change from `previous` to `current`.

    Returns None when `previous` is zero or NEGATIVE. Percent change
    off a negative base is not just awkward, it inverts: a company
    going from a $100M loss to a $100M profit yields -200% under the
    standard formula, which the UI would then render as "earnings are
    declining" for what is unambiguously good news. There is no sign
    convention that fixes this, so we decline to state a percentage
    and let callers describe the swing in words instead (see
    describe_swing).
    """
    if previous is None or current is None:
        return None

    if previous <= 0:
        return None

    return ((current - previous) / previous) * 100


def describe_swing(current, previous):
    """
    Describe a period-over-period change in words for the cases where
    a percentage would be meaningless or actively misleading.

    Returns a short string, or None when a plain percentage is fine.
    """
    if current is None or previous is None:
        return None

    if previous > 0:
        return None  # percent change is well-defined; no words needed

    if previous == 0:
        return (
            "Prior period was breakeven"
            if current <= 0
            else "Turned profitable from a breakeven prior period"
        )

    # previous < 0 from here: the prior period was a loss.
    if current > 0:
        return "Swung from a loss to a profit"

    if current > previous:
        return "Still lossmaking, but the loss narrowed"

    if current < previous:
        return "Loss widened"

    return "Loss unchanged"


def _growth(statement, metric):
    """
    Year-over-year growth for a flow metric, as a percentage.

    Returns (value, basis) where basis is:
      "yoy"        - compared against the same quarter a year earlier
      "sequential" - not enough history (or unparseable dates) to find
                     a year-ago quarter, so this compares to the prior
                     quarter and is seasonally distorted
      None         - not computable

    The basis is returned rather than hidden because a sequential
    comparison means something materially different from a
    year-over-year one, and the UI needs to be able to say which it's
    showing.
    """
    pairs = _sorted_pairs(statement, metric)

    if len(pairs) < 2:
        return None, None

    current = pairs[0][1]

    year_ago_index = _find_year_ago_index(pairs)

    if year_ago_index is not None:
        return _percent_change(current, pairs[year_ago_index][1]), "yoy"

    return _percent_change(current, pairs[1][1]), "sequential"


def _sequential_growth(statement, metric):
    """Plain quarter-over-quarter growth, kept as a secondary momentum read."""
    values = _sorted_values(statement, metric)

    if len(values) < 2:
        return None

    return _percent_change(values[0], values[1])


# ----------------------------------------------------------
# PROFITABILITY
# ----------------------------------------------------------


def calculate_net_profit_margin(income_statement):
    """
    Share of revenue that becomes net profit, on a TTM basis.
    Formula: TTM Net Income / TTM Revenue * 100
    """
    net_income, income_basis = get_ttm_value(income_statement, "Net Income")
    revenue, revenue_basis = get_ttm_value(income_statement, "Total Revenue")

    if net_income is None or revenue is None or revenue == 0:
        return None

    # Mixing a four-quarter numerator with a one-quarter denominator
    # would inflate margin ~4x, so only report a margin when both
    # sides cover the same period.
    if income_basis != revenue_basis:
        return None

    return (net_income / revenue) * 100


def calculate_roe(income_statement, balance_sheet):
    """
    Return on equity: profit generated per dollar of shareholder equity.
    Formula: TTM Net Income / Average Stockholders Equity * 100

    Equity is a point-in-time balance, while net income accumulates
    over the year, so the textbook treatment averages beginning and
    ending equity. We do that when a year-ago balance sheet is
    available and fall back to the latest balance otherwise.
    """
    net_income, _ = get_ttm_value(income_statement, "Net Income")
    equity = _average_equity(balance_sheet)

    if net_income is None or equity is None or equity == 0:
        return None

    return (net_income / equity) * 100


def _average_equity(balance_sheet):
    """
    Average shareholders' equity across the trailing year, falling
    back to the latest reported balance when there isn't a year of
    history.

    Returns None if equity is missing, or if average equity comes out
    negative or zero - ROE on a negative equity base is not a
    meaningful number (a company with negative book equity and
    positive earnings would score as spectacularly negative), so the
    honest answer is to report nothing.
    """
    pairs = _sorted_pairs(balance_sheet, "Stockholders Equity")

    if not pairs:
        return None

    latest = pairs[0][1]
    year_ago_index = _find_year_ago_index(pairs)

    if year_ago_index is None:
        average = latest
    else:
        average = (latest + pairs[year_ago_index][1]) / 2

    if average <= 0:
        return None

    return average


# ----------------------------------------------------------
# GROWTH
# ----------------------------------------------------------


def calculate_revenue_growth(income_statement):
    """Year-over-year revenue growth, as a percentage."""
    value, _ = _growth(income_statement, "Total Revenue")
    return value


def calculate_revenue_growth_detailed(income_statement):
    """Year-over-year revenue growth as (value, basis). See _growth."""
    return _growth(income_statement, "Total Revenue")


def calculate_earnings_growth(income_statement):
    """
    Year-over-year net income growth, as a percentage.

    Returns None when the year-ago quarter was a loss - see
    _percent_change for why a number would mislead there.
    """
    value, _ = _growth(income_statement, "Net Income")
    return value


def calculate_earnings_growth_detailed(income_statement):
    """Year-over-year earnings growth as (value, basis). See _growth."""
    return _growth(income_statement, "Net Income")


def calculate_earnings_swing(income_statement):
    """
    Plain-language description of the year-over-year earnings change
    for the cases calculate_earnings_growth can't express as a
    percentage. Returns None when a percentage is adequate.
    """
    pairs = _sorted_pairs(income_statement, "Net Income")

    if len(pairs) < 2:
        return None

    year_ago_index = _find_year_ago_index(pairs)
    comparison_index = year_ago_index if year_ago_index is not None else 1

    return describe_swing(pairs[0][1], pairs[comparison_index][1])


# ----------------------------------------------------------
# BALANCE SHEET & CASH FLOW
# ----------------------------------------------------------


def calculate_debt_to_equity(balance_sheet):
    """
    Financial leverage: Total Debt / Stockholders Equity.

    Both sides are point-in-time balances, so this uses the latest
    reported figures rather than a trailing sum.
    """
    total_debt = get_latest_value(balance_sheet, "Total Debt")
    equity = get_latest_value(balance_sheet, "Stockholders Equity")

    if total_debt is None or equity is None or equity <= 0:
        # Negative book equity makes the ratio negative, which reads as
        # "very low leverage" when it means the opposite. Report nothing.
        return None

    return total_debt / equity


def calculate_current_ratio(balance_sheet):
    """
    Short-term solvency: Current Assets / Current Liabilities.
    Point-in-time, so no trailing sum.
    """
    current_assets = get_latest_value(balance_sheet, "Current Assets")
    current_liabilities = get_latest_value(balance_sheet, "Current Liabilities")

    if (
        current_assets is None
        or current_liabilities is None
        or current_liabilities == 0
    ):
        return None

    return current_assets / current_liabilities


def calculate_free_cash_flow(cash_flow):
    """
    Cash left after capital expenditure, on a TTM basis.
    Formula: TTM Operating Cash Flow + TTM Capital Expenditure

    Yahoo Finance reports capital expenditure as a negative number,
    hence the addition.
    """
    operating_cash_flow, operating_basis = get_ttm_value(
        cash_flow, "Operating Cash Flow"
    )
    capital_expenditure, capex_basis = get_ttm_value(
        cash_flow, "Capital Expenditure"
    )

    if operating_cash_flow is None or capital_expenditure is None:
        return None

    # Same period-matching rule as margin: a four-quarter operating
    # cash flow minus a one-quarter capex would badly overstate FCF.
    if operating_basis != capex_basis:
        return None

    return operating_cash_flow + capital_expenditure


def calculate_fcf_margin(cash_flow, income_statement):
    """
    Free cash flow as a percentage of revenue - how much of each
    sales dollar actually converts to cash.

    This is what separates a business that reports profits from one
    that generates cash, and it's a far better signal than the
    positive/negative coin flip the health score used to apply.
    """
    free_cash_flow = calculate_free_cash_flow(cash_flow)
    revenue, _ = get_ttm_value(income_statement, "Total Revenue")

    if free_cash_flow is None or revenue is None or revenue <= 0:
        return None

    return (free_cash_flow / revenue) * 100


# ----------------------------------------------------------
# TOP-LEVEL
# ----------------------------------------------------------


def calculate_kpis(ticker):
    """
    Fetch a company's financials and compute every KPI the app uses.

    Returns a dict of metric -> value (None where uncomputable), plus
    "*_basis" keys describing what period each headline number
    actually covers, so the UI can label them accurately.
    """
    data = fetch_company_financials(ticker)

    if not data:
        return {}

    income_statement = data.get("income_statement", {})
    balance_sheet = data.get("balance_sheet", {})
    cash_flow = data.get("cash_flow", {})

    revenue_growth, revenue_growth_basis = calculate_revenue_growth_detailed(
        income_statement
    )
    earnings_growth, earnings_growth_basis = calculate_earnings_growth_detailed(
        income_statement
    )

    revenue_ttm, revenue_basis = get_ttm_value(income_statement, "Total Revenue")
    net_income_ttm, _ = get_ttm_value(income_statement, "Net Income")

    return {
        # Headline metrics consumed by health_score and every page.
        "net_profit_margin": calculate_net_profit_margin(income_statement),
        "debt_to_equity": calculate_debt_to_equity(balance_sheet),
        "revenue_growth": revenue_growth,
        "earnings_growth": earnings_growth,
        "free_cash_flow": calculate_free_cash_flow(cash_flow),
        "current_ratio": calculate_current_ratio(balance_sheet),
        "roe": calculate_roe(income_statement, balance_sheet),
        "fcf_margin": calculate_fcf_margin(cash_flow, income_statement),
        # Absolute scale, useful for context and for valuation ratios.
        "revenue_ttm": revenue_ttm,
        "net_income_ttm": net_income_ttm,
        # Secondary momentum read - seasonally distorted by design,
        # shown as a supplement rather than as the headline.
        "revenue_growth_qoq": _sequential_growth(income_statement, "Total Revenue"),
        "earnings_growth_qoq": _sequential_growth(income_statement, "Net Income"),
        # Narrative fallback for when earnings growth can't be a percentage.
        "earnings_swing": calculate_earnings_swing(income_statement),
        # How to label the numbers above.
        "revenue_growth_basis": revenue_growth_basis,
        "earnings_growth_basis": earnings_growth_basis,
        "period_basis": revenue_basis,
    }


# Metric keys that carry a value rather than a label - useful for
# callers that want to check whether any real data came back.
VALUE_METRICS = (
    "net_profit_margin",
    "debt_to_equity",
    "revenue_growth",
    "earnings_growth",
    "free_cash_flow",
    "current_ratio",
    "roe",
    "fcf_margin",
)


if __name__ == "__main__":
    kpis = calculate_kpis("AAPL")

    print("\n--- AAPL KPI Results ---")

    for name, value in kpis.items():
        if isinstance(value, (int, float)):
            print(f"{name}: {value:,.2f}")
        else:
            print(f"{name}: {value if value is not None else 'N/A'}")
