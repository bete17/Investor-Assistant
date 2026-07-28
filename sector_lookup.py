# ==========================================================
# SECTOR LOOKUP
# ==========================================================

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