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

# PERFORMANCE NOTE: yfinance is imported lazily inside get_sector(),
# NOT at module level.
#
# This module previously did `try: import yfinance` at import time.
# Because three of the four pages import sector_lookup, and importing
# yfinance costs ~1.1s, every one of those pages blocked for over a
# second before Streamlit could draw anything - and nothing can be
# rendered (no spinner, no skeleton) while a module-level import runs.
#
# Worth noting how this hid: it was indented inside a try block, so it
# didn't match a grep for top-level `import yfinance` lines and survived
# an earlier pass that made the other modules' imports lazy. Measuring
# each module in isolation is what actually found it.
#
# The import is also genuinely unnecessary most of the time: a warm
# 24-hour disk cache means get_sector() returns before ever touching
# yfinance.


def _import_yfinance():
    """
    Import yfinance on demand. Returns the module, or None if it isn't
    installed - preserving the original try/except ImportError behavior
    so a missing yfinance degrades to "no sector" rather than crashing.
    """
    try:
        import yfinance as yf

        return yf
    except ImportError:
        return None


# Same cache dir as financials_fetcher.py / news_fetcher.py /
# storyline_fetcher.py: <project_root>/data/cache. This file lives in
# analytics/, so it has to go up one level first - previously this
# computed analytics/data/cache/ instead, a silent mismatch that also
# meant these cache files weren't covered by the top-level
# "data/cache/" .gitignore rule and ended up committed to the repo.
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_DIR = os.path.join(BASE_DIR, "data", "cache")
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

    # Only now - after a cache miss - is yfinance actually needed.
    yf = _import_yfinance()

    if yf is None:
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