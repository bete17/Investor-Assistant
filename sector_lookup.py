# ==========================================================
# SECTOR LOOKUP
# ==========================================================
# NOTE: this assumes your project already uses yfinance somewhere
# (the "Yahoo Finance" mentions in your KPI reference section
# suggested this) since it's the free/no-API-key way to get a
# ticker's sector. If your data actually comes from a different
# provider, swap the implementation of get_sector() below to use
# that provider's sector field instead - the rest of the app only
# depends on this function returning a string like "Technology" or
# None, not on HOW it gets it.

try:
    import yfinance as yf
    _YFINANCE_AVAILABLE = True
except ImportError:
    _YFINANCE_AVAILABLE = False


def get_sector(ticker):
    """
    Look up a ticker's sector (e.g. "Technology", "Healthcare").
    Returns None if unavailable, so callers can fall back to
    default (non-sector-specific) scoring rather than crashing.
    """

    if not _YFINANCE_AVAILABLE:
        return None

    try:
        info = yf.Ticker(ticker).info
        return info.get("sector")

    except Exception:
        # Network issue, invalid ticker, rate limit, etc. - fail
        # quietly and let the caller fall back to default ranges.
        return None