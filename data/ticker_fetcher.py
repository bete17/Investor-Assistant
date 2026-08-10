"""
Resolve user input to a valid SEC ticker using company_tickers.json.

Supports ticker symbols (AAPL), legal company names (Alphabet Inc.),
and common brand aliases (Google -> GOOGL, Facebook -> META).
"""

from __future__ import annotations

import json
import os
import re
from functools import lru_cache

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TICKERS_PATH = os.path.join(BASE_DIR, "tickers", "company_tickers.json")

TICKER_PATTERN = re.compile(r"^[A-Z0-9.\-]{1,10}$")

_SUFFIXES = re.compile(
    r"\b(inc\.?|corp\.?|corporation|co\.?|company|ltd\.?|limited|plc|lp|llc|n\.?v\.?|s\.?a\.?)\b",
    re.I,
)

# Brand / colloquial names that don't appear in SEC legal titles.
# Values must exist in company_tickers.json (or alias chain resolves to one).
ALIASES: dict[str, str] = {
    "google": "GOOGL",
    "alphabet": "GOOGL",
    "facebook": "META",
    "fb": "META",
    "meta": "META",
    "amazon": "AMZN",
    "apple": "AAPL",
    "microsoft": "MSFT",
    "nvidia": "NVDA",
    "tesla": "TSLA",
    "berkshire": "BRK-B",
    "berkshire hathaway": "BRK-B",
    "johnson and johnson": "JNJ",
    "johnson & johnson": "JNJ",
    "visa": "V",
    "walmart": "WMT",
    "mastercard": "MA",
}


def normalize_text(text: str) -> str:
    """Lowercase, strip punctuation/suffixes, collapse whitespace."""
    text = text.strip().lower()
    text = re.sub(r"[^\w\s]", " ", text)
    text = _SUFFIXES.sub(" ", text)
    return re.sub(r"\s+", " ", text).strip()


@lru_cache(maxsize=1)
def _load_index() -> tuple[dict[str, str], dict[str, str]]:
    """
    Load company_tickers.json once and build lookup indexes.

    Returns:
        tickers: upper-case symbol -> canonical symbol from JSON
        by_title: normalized company title (and aliases) -> ticker
    """
    with open(TICKERS_PATH, encoding="utf-8") as tickers_file:
        raw = json.load(tickers_file)

    tickers: dict[str, str] = {}
    by_title: dict[str, str] = {}

    for entry in raw.values():
        ticker = entry.get("ticker", "").strip()
        title = entry.get("title", "").strip()
        if not ticker:
            continue

        tickers[ticker.upper()] = ticker

        if title:
            by_title.setdefault(normalize_text(title), ticker)

    for alias, target in ALIASES.items():
        normalized_alias = normalize_text(alias)
        canonical = tickers.get(target.upper(), target)
        by_title.setdefault(normalized_alias, canonical)

    return tickers, by_title


def is_valid_ticker(user_input: str) -> bool:
    """True if input is a known ticker symbol in company_tickers.json."""
    if not user_input or not user_input.strip():
        return False

    candidate = user_input.strip().upper()
    if not TICKER_PATTERN.match(candidate):
        return False

    tickers, _ = _load_index()
    return candidate in tickers


def find_valid_ticker(user_input: str) -> str | None:
    """
    Resolve user input to a known ticker.

    Resolution order:
      1. Alias map (Google, Facebook, ...)
      2. Exact ticker match (case-insensitive)
      3. Exact normalized company name
      4. Unique prefix match on company name
      5. Unique substring match on company name
    """
    if not user_input or not user_input.strip():
        return None

    raw = user_input.strip()
    tickers, by_title = _load_index()
    normalized = normalize_text(raw)

    if normalized in ALIASES:
        target = ALIASES[normalized]
        return tickers.get(target.upper(), target)

    upper = raw.upper()
    if upper in tickers:
        return tickers[upper]

    if normalized in by_title:
        return by_title[normalized]

    prefix_matches = sorted(
        {ticker for title, ticker in by_title.items() if title.startswith(normalized)}
    )
    if len(prefix_matches) == 1:
        return prefix_matches[0]

    substring_matches = sorted(
        {ticker for title, ticker in by_title.items() if normalized in title}
    )
    if len(substring_matches) == 1:
        return substring_matches[0]

    return None
