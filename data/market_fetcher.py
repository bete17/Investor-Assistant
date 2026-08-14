# ==========================================================
# MARKET FETCHER
# ==========================================================
# Price and valuation data: what the market currently thinks a
# company is worth, as opposed to what its financial statements say
# about the business.
#
# This is deliberately separate from financials_fetcher.py because
# the two have completely different freshness requirements. Quarterly
# statements change four times a year and are cached for 24 hours;
# quotes change every second the market is open, so caching them for
# a day would be worse than useless. This module uses a short TTL and
# its own cache files.
#
# yfinance's Ticker.info is the only practical source for most of
# these fields, but it's slow and rate-limit-prone, which is exactly
# why the cache matters.

import json
import os
import time

# yfinance is imported lazily inside the fetch (see sector_lookup.py
# for the full rationale - the import costs over a second, and a warm
# cache means we usually never need it).

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_DIR = os.path.join(BASE_DIR, "data", "cache")
os.makedirs(CACHE_DIR, exist_ok=True)

# Quotes go stale fast. Fifteen minutes keeps the app responsive and
# roughly matches the delay on free market data anyway, so this isn't
# pretending to be realtime.
CACHE_TTL_SECONDS = 15 * 60

# Fields we pull out of yfinance's info blob. Everything is optional -
# ETFs, ADRs, recent IPOs and lossmaking companies all legitimately
# lack some of these, and a missing field must never break the page.
_INFO_FIELDS = {
    "name": ("longName", "shortName"),
    "currency": ("currency",),
    "price": ("currentPrice", "regularMarketPrice", "previousClose"),
    "previous_close": ("regularMarketPreviousClose", "previousClose"),
    "market_cap": ("marketCap",),
    "trailing_pe": ("trailingPE",),
    "forward_pe": ("forwardPE",),
    "price_to_sales": ("priceToSalesTrailing12Months",),
    "price_to_book": ("priceToBook",),
    "dividend_rate": ("dividendRate",),
    "dividend_yield_raw": ("dividendYield",),
    "beta": ("beta",),
    "fifty_two_week_high": ("fiftyTwoWeekHigh",),
    "fifty_two_week_low": ("fiftyTwoWeekLow",),
    "shares_outstanding": ("sharesOutstanding",),
    "trailing_eps": ("trailingEps",),
    # ------------------------------------------------------
    # Fields kept for their history, not for today's value
    # ------------------------------------------------------
    # Everything above describes what a company is worth right now.
    # These five describe what analysts currently expect of it, which
    # is a different kind of number: it gets revised, and the
    # revisions are the signal. yfinance only ever reports the
    # current figure - there is no way to ask what a target price was
    # last month - so snapshot_store writes these down as they pass.
    "target_price": ("targetMeanPrice",),
    "forward_eps": ("forwardEps",),
    "recommendation": ("recommendationKey",),
    "num_analysts": ("numberOfAnalystOpinions",),
    "profit_margin": ("profitMargins",),
}


def _cache_path(ticker):
    return os.path.join(CACHE_DIR, f"{ticker.upper()}_market.json")


def _is_cache_valid(path):
    if not os.path.exists(path):
        return False

    return (time.time() - os.path.getmtime(path)) < CACHE_TTL_SECONDS


def _coerce_number(value):
    """
    Return value as a float, or None if it isn't a usable number.

    yfinance returns "Infinity", NaN, and occasionally strings for
    fields that are supposed to be numeric, so nothing from the info
    blob is trusted without this.
    """
    if value is None or isinstance(value, bool):
        return None

    try:
        number = float(value)
    except (TypeError, ValueError):
        return None

    # NaN is the only value that isn't equal to itself.
    if number != number or number in (float("inf"), float("-inf")):
        return None

    return number


def _first_available(info, keys):
    """Return the first key in `keys` that has a usable value."""
    for key in keys:
        value = info.get(key)

        # recommendationKey is a label ("buy", "hold"), not a number,
        # so it belongs with the other string fields - left out of
        # this tuple it would fail _coerce_number and come back None.
        if key in ("longName", "shortName", "currency", "recommendationKey"):
            if isinstance(value, str) and value.strip():
                return value.strip()
            continue

        number = _coerce_number(value)
        if number is not None:
            return number

    return None


def _resolve_dividend_yield(snapshot):
    """
    Work out an annual dividend yield as a PERCENTAGE.

    yfinance has changed the units of its `dividendYield` field
    between releases - older versions returned a fraction (0.0044 for
    0.44%), newer ones return a percentage (0.44). Guessing from
    magnitude is genuinely ambiguous in the 0.5-1.0 band, so where
    possible we sidestep the question entirely and compute the yield
    from the annual dividend rate and the price, which have
    unambiguous units.

    The reported field is only used as a fallback, and then only when
    it lands in a plausible range.
    """
    rate = snapshot.get("dividend_rate")
    price = snapshot.get("price")

    if rate is not None and price is not None and price > 0:
        return (rate / price) * 100

    reported = snapshot.get("dividend_yield_raw")

    if reported is None:
        return None

    # A fraction would be well under 1; a percentage is typically
    # 0.1-15. Anything above 100 is a unit error, not a real yield.
    if reported > 100:
        return None

    return reported


def _position_in_52_week_range(snapshot):
    """
    Where the current price sits between the 52-week low and high, as
    a 0-100 percentage. 0 means at the low, 100 means at the high.
    """
    price = snapshot.get("price")
    low = snapshot.get("fifty_two_week_low")
    high = snapshot.get("fifty_two_week_high")

    if price is None or low is None or high is None:
        return None

    if high <= low:
        return None

    position = (price - low) / (high - low) * 100

    # Intraday prices can print slightly outside the trailing 52-week
    # band before it updates, so clamp rather than showing 104%.
    return max(0.0, min(100.0, position))


def _build_snapshot(ticker, info):
    """Normalize a raw yfinance info blob into our own flat shape."""
    snapshot = {"ticker": ticker.upper()}

    for field, keys in _INFO_FIELDS.items():
        snapshot[field] = _first_available(info, keys)

    snapshot["dividend_yield"] = _resolve_dividend_yield(snapshot)
    snapshot.pop("dividend_yield_raw", None)

    price = snapshot.get("price")
    previous_close = snapshot.get("previous_close")

    if price is not None and previous_close is not None and previous_close > 0:
        snapshot["price_change"] = price - previous_close
        snapshot["price_change_percent"] = (
            (price - previous_close) / previous_close
        ) * 100
    else:
        snapshot["price_change"] = None
        snapshot["price_change_percent"] = None

    snapshot["range_position"] = _position_in_52_week_range(snapshot)
    snapshot["fetched_at"] = time.time()

    return snapshot


def fetch_market_snapshot(ticker: str) -> dict:
    """
    Fetch price and valuation data for a ticker.

    Returns a flat dict of normalized fields (any of which may be
    None), or {} if the ticker is unknown or the fetch fails. Callers
    should treat {} and a snapshot full of Nones the same way: show
    what's there, say nothing about what isn't.
    """
    if not ticker or not ticker.strip():
        return {}

    path = _cache_path(ticker)

    if _is_cache_valid(path):
        try:
            with open(path, "r", encoding="utf-8") as cache_file:
                return json.load(cache_file)
        except (OSError, ValueError):
            # A truncated or corrupt cache file shouldn't be fatal -
            # fall through and re-fetch.
            pass

    try:
        import yfinance as yf  # lazy: see note at top of module

        info = yf.Ticker(ticker).info or {}
    except Exception as error:  # noqa: BLE001 - yfinance raises many shapes
        print(f"Market data unavailable for {ticker.upper()}: {error}")
        return {}

    if not info:
        return {}

    snapshot = _build_snapshot(ticker, info)

    try:
        with open(path, "w", encoding="utf-8") as cache_file:
            json.dump(snapshot, cache_file)
    except OSError:
        pass  # a cache write failure is not worth failing the request over

    # Record the day's observation.
    #
    # This sits on the cache-miss path deliberately. A miss means
    # these numbers were just fetched fresh, and once every fifteen
    # minutes is already far more often than the one row a day the
    # store keeps - so the same coverage costs a fraction of the
    # writes that hooking _build_snapshot would.
    #
    # Imported lazily and failing silently for the same reason as the
    # cache write above: recording history is a side effect, never the
    # request the user is waiting on. An app with no database
    # configured behaves exactly as it did before this existed.
    try:
        from data.snapshot_store import record_snapshot

        record_snapshot(snapshot)
    except Exception:  # noqa: BLE001 - import or driver, both non-fatal
        pass

    return snapshot


if __name__ == "__main__":
    from pprint import pprint

    pprint(fetch_market_snapshot("AAPL"))