# --------------------------------------------------
# Formatting helper functions
# --------------------------------------------------


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


# --------------------------------------------------
# KPI status helpers
# --------------------------------------------------


def profitability_status(value):
    """
    Gives a simple interpretation
    of net profit margin.
    """

    if value is None:
        return "No data"

    if value >= 20:
        return "Strong"

    if value >= 10:
        return "Moderate"

    if value >= 0:
        return "Low"

    return "Negative"


def roe_status(value):
    """
    Gives a simple interpretation of ROE.
    """

    if value is None:
        return "No data"

    if value >= 20:
        return "Strong"

    if value >= 10:
        return "Moderate"

    if value >= 0:
        return "Low"

    return "Negative"


def growth_status(value):
    """
    Determines whether growth is
    positive, flat, or declining.
    """

    if value is None:
        return "No data"

    if value > 10:
        return "Strong growth"

    if value > 0:
        return "Growing"

    if value == 0:
        return "Flat"

    return "Declining"


def debt_status(value):
    """
    Simple interpretation of Debt / Equity.

    Important:
    Proper debt interpretation can vary
    significantly between industries.
    """

    if value is None:
        return "No data"

    if value < 0.5:
        return "Low leverage"

    if value < 1:
        return "Moderate"

    if value < 2:
        return "Elevated"

    return "High leverage"


def liquidity_status(value):
    """
    Simple interpretation of Current Ratio.
    """

    if value is None:
        return "No data"

    if value >= 2:
        return "Strong"

    if value >= 1:
        return "Healthy"

    return "Weak"


def cash_flow_status(value):
    """
    Determines whether free cash flow
    is positive or negative.
    """

    if value is None:
        return "No data"

    if value > 0:
        return "Positive"

    if value == 0:
        return "Neutral"

    return "Negative"