# --------------------------------------------------
# Formatting helper functions
# --------------------------------------------------


import re

TICKER_PATTERN = re.compile(r"^[A-Z0-9\.\-]{1,10}$")

def is_valid_ticker(ticker: str) -> bool:
    return bool(TICKER_PATTERN.match(ticker))



def format_percent(value):
    """
    Converts a number into a percentage string.

    Example:
    26.6023 -> "26.60%"
    """

    if value is None:
        return "N/A"

    return f"{value:.2f}%"


def format_ratio(value):
    """
    Formats financial ratios.

    Example:
    0.8034 -> "0.80"
    """

    if value is None:
        return "N/A"

    return f"{value:.2f}"


def format_money(value):
    """
    Converts large dollar values into
    easier-to-read financial notation.

    Example:
    26,730,000,000 -> "$26.73B"
    """

    if value is None:
        return "N/A"

    # Remember whether the number is negative
    negative = value < 0

    # Work with the positive version temporarily
    value = abs(value)

    # Trillion
    if value >= 1_000_000_000_000:
        result = f"${value / 1_000_000_000_000:.2f}T"

    # Billion
    elif value >= 1_000_000_000:
        result = f"${value / 1_000_000_000:.2f}B"

    # Million
    elif value >= 1_000_000:
        result = f"${value / 1_000_000:.2f}M"

    # Thousand
    elif value >= 1_000:
        result = f"${value / 1_000:.2f}K"

    # Normal number
    else:
        result = f"${value:.2f}"

    # Put the negative sign back if needed
    if negative:
        return "-" + result

    return result


# NOTE: KPI status/label logic (profitability, ROE, growth, debt,
# liquidity, cash flow) lives in kpi_dashboard.py's get_status(), which
# is the single source of truth for those thresholds. An earlier,
# unused duplicate set of *_status() helpers used to live here with
# slightly different thresholds than get_status() - removed to avoid
# two disagreeing definitions of the same label existing at once.