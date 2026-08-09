# ==========================================================
# SECTOR LOOKUP
# ==========================================================
# Sector data changes rarely, but yf.Ticker(ticker).info is one of
# the slowest and most rate-limit-prone calls in the yfinance API -
# it pulls a large metadata blob just to read one field. This adds
# an on-disk cache (matching the pattern used by financials_fetcher
# / storyline_fetcher elsewhere in this project) so repeated lookups
# - e.g. a screener running across hundreds of tickers, or a nightly
# alert job across every watchlist - don't re-hit yfinance for data
# that's still fresh. Previously this only worked by accident, via
# each page's own short-lived @st.cache_data wrapper.

import json
import os
from datetime import datetime, timezone

try:
    import yfinance as yf
    _YFINANCE_AVAILABLE = True
except ImportError:
    _YFINANCE_AVAILABLE = False


CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "cache")
CACHE_TTL_SECONDS = 24 * 60 * 60  # sector reassignments are rare; 24h is plenty


def _cache_path(ticker):
    return os.path.join(CACHE_DIR, f"{ticker.upper()}_sector.json")


def _read_cache(ticker):
    """Return a cached sector lookup if the cache file exists and is fresh, else None."""
    path = _cache_path(ticker)

    if not os.path.exists(path):
        return None

    try:
        with open(path, encoding="utf-8") as cache_file:
            payload = json.load(cache_file)
    except (OSError, json.JSONDecodeError):
        return None  # corrupt/unreadable cache file - treat as a miss

    fetched_at = payload.get("fetched_at")

    if not fetched_at:
        return None

    try:
        fetched_dt = datetime.fromisoformat(fetched_at)
    except ValueError:
        return None

    age_seconds = (datetime.now(timezone.utc) - fetched_dt).total_seconds()

    if age_seconds > CACHE_TTL_SECONDS:
        return None  # stale - fall through to a live fetch

    # NOTE: this dict always HAS the "sector" key once cached (see
    # _write_cache), even when the value is None - that's what lets
    # us distinguish "no cache entry, please fetch" from "we already
    # know this ticker has no sector, don't bother re-fetching."
    return payload if "sector" in payload else None


def _write_cache(ticker, sector):
    """Persist a sector lookup result (including a None sector) to disk."""
    os.makedirs(CACHE_DIR, exist_ok=True)

    payload = {
        "ticker": ticker.upper(),
        "sector": sector,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }

    try:
        with open(_cache_path(ticker), "w", encoding="utf-8") as cache_file:
            json.dump(payload, cache_file)
    except OSError:
        pass  # caching is a nice-to-have; don't let a disk issue break the lookup


def get_sector(ticker, force_refresh=False):
    """
    Look up a ticker's sector (e.g. "Technology", "Healthcare").
    Returns None if unavailable, so callers can fall back to
    default (non-sector-specific) scoring rather than crashing.

    Cached to disk for CACHE_TTL_SECONDS so repeated lookups (a
    screener, a nightly job) don't hammer yfinance's slow .info call.
    Pass force_refresh=True to bypass the cache and re-fetch.
    """

    if not force_refresh:
        cached = _read_cache(ticker)
        if cached is not None:
            return cached.get("sector")

    if not _YFINANCE_AVAILABLE:
        return None

    try:
        info = yf.Ticker(ticker).info
        sector = info.get("sector")

    except Exception:
        # Network issue, invalid ticker, rate limit, etc. - fail
        # quietly and let the caller fall back to default ranges.
        # Deliberately NOT cached: a transient failure should be
        # retried on the next call, not locked in as "no sector"
        # for a full day.
        return None

    _write_cache(ticker, sector)

    return sector


if __name__ == "__main__":
    for test_ticker in ("AAPL", "MSFT", "INVALID_TICKER_XYZ"):
        print(f"{test_ticker}: {get_sector(test_ticker)}")