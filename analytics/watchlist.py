# ==========================================================
# WATCHLIST
# ==========================================================
# The app previously had no memory at all: every visit started at an
# empty search box, and nothing a user did in one session survived
# into the next. That's the difference between a tool someone tries
# once and one they come back to, so this stores the small amount of
# state that's actually worth keeping.
#
# ----------------------------------------------------------
# SCOPE: LOCAL, SINGLE USER, ON PURPOSE
# ----------------------------------------------------------
# There is no authentication in this project, so there is no user to
# key a watchlist against. This is a single JSON file on the machine
# running the app - which is exactly right for the local/self-hosted
# use this app is built for, and exactly wrong for a shared
# deployment, where every visitor would read and write one another's
# list. Multi-user watchlists need accounts first; that's a
# deliberately deferred feature, not an oversight.
#
# The store is kept in analytics/ rather than data/ because it holds
# the user's own state rather than fetched market data, and it never
# touches the network.

import json
import os
import re
from datetime import datetime, timezone

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_PATH = os.path.join(BASE_DIR, "data", "watchlist.json")

# Where the file lives can be overridden, which is what lets tests run
# against a temporary file instead of clobbering a real user's list.
# Resolved per call rather than at import time so setting the variable
# after the module loads still takes effect.
PATH_ENV_VAR = "INVESTOR_ASSISTANT_WATCHLIST"


def _resolve_path(path=None):
    if path is not None:
        return path

    return os.environ.get(PATH_ENV_VAR) or DEFAULT_PATH

# Same shape the rest of the app accepts as a ticker.
_TICKER_PATTERN = re.compile(r"^[A-Z0-9.\-]{1,10}$")

# A cap keeps the landing page fast: every entry shown there costs a
# scoring pass, and a list long enough to be slow is a list nobody
# reads anyway.
MAX_ENTRIES = 30


def normalize_ticker(ticker):
    """
    Return a ticker in canonical form, or None if it isn't one.

    Validating here rather than at the call site means a malformed
    value can never reach the stored file, so anything read back out
    is safe to render and safe to look up.
    """
    if not ticker or not isinstance(ticker, str):
        return None

    candidate = ticker.strip().upper()

    if not _TICKER_PATTERN.match(candidate):
        return None

    return candidate


def load_watchlist(path=None):
    """
    Read the stored watchlist.

    Returns a list of {ticker, added_at} dicts, most recently added
    first. A missing, empty, or corrupt file yields an empty list -
    losing a watchlist is unfortunate, but refusing to start the app
    over it would be worse.
    """
    path = _resolve_path(path)

    if not os.path.exists(path):
        return []

    try:
        with open(path, "r", encoding="utf-8") as watchlist_file:
            stored = json.load(watchlist_file)
    except (OSError, ValueError):
        return []

    if not isinstance(stored, list):
        return []

    entries = []
    seen = set()

    for item in stored:
        if isinstance(item, str):
            ticker, added_at = normalize_ticker(item), None
        elif isinstance(item, dict):
            ticker = normalize_ticker(item.get("ticker"))
            added_at = item.get("added_at")
        else:
            continue

        # Re-validating on read matters because the file is editable
        # by hand, and because an older version of this app may have
        # written a different shape.
        if ticker is None or ticker in seen:
            continue

        seen.add(ticker)
        entries.append({"ticker": ticker, "added_at": added_at})

    return entries


def save_watchlist(entries, path=None):
    """
    Write the watchlist to disk.

    Writes to a temporary file and replaces the real one, so an
    interrupted write leaves the previous list intact rather than a
    truncated file that would read back as empty.
    """
    path = _resolve_path(path)

    os.makedirs(os.path.dirname(path), exist_ok=True)

    temporary_path = f"{path}.tmp"

    with open(temporary_path, "w", encoding="utf-8") as watchlist_file:
        json.dump(entries[:MAX_ENTRIES], watchlist_file, indent=2)

    os.replace(temporary_path, path)


def get_tickers(path=None):
    """Just the ticker symbols, most recently added first."""
    return [entry["ticker"] for entry in load_watchlist(path)]


def is_watched(ticker, path=None):
    """True if this ticker is already on the watchlist."""
    normalized = normalize_ticker(ticker)

    if normalized is None:
        return False

    return normalized in get_tickers(path)


def add_ticker(ticker, path=None):
    """
    Add a ticker to the front of the watchlist.

    Returns True if it was added, False if it was invalid or already
    present. Idempotent, so a double-click can't create duplicates.
    """
    normalized = normalize_ticker(ticker)

    if normalized is None:
        return False

    entries = load_watchlist(path)

    if any(entry["ticker"] == normalized for entry in entries):
        return False

    entries.insert(0, {
        "ticker": normalized,
        "added_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    })

    save_watchlist(entries, path)
    return True


def remove_ticker(ticker, path=None):
    """
    Remove a ticker from the watchlist.

    Returns True if something was removed, False if it wasn't there.
    """
    normalized = normalize_ticker(ticker)

    if normalized is None:
        return False

    entries = load_watchlist(path)
    remaining = [entry for entry in entries if entry["ticker"] != normalized]

    if len(remaining) == len(entries):
        return False

    save_watchlist(remaining, path)
    return True


def toggle_ticker(ticker, path=None):
    """
    Add the ticker if absent, remove it if present.

    Returns True if the ticker is on the list afterwards.
    """
    if is_watched(ticker, path):
        remove_ticker(ticker, path)
        return False

    return add_ticker(ticker, path)
