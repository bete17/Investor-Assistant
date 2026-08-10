"""
Fetch SEC 10-K filings, extract Item 7 (MD&A), and cache structured blocks locally.

See tests/test_storyline_fetcher.py for the behaviors this module must support.
"""
import json
import os
import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup, NavigableString, Tag
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_DIR = os.path.join(BASE_DIR, "data", "cache")
os.makedirs(CACHE_DIR, exist_ok=True)

# ==========================================================
# SEC EDGAR IDENTITY
# ==========================================================
# SEC's fair-access policy requires every automated caller to
# identify itself with a real name and email in every request
# (https://www.sec.gov/os/webmaster-faq#developers). Submitting a
# placeholder violates that policy and risks getting the calling
# IP rate-limited or blocked outright - so this fails loudly at
# import time instead of silently sending SEC a fake identity.
#
# Set in your .env file, e.g.:
#   EDGAR_IDENTITY="Jane Doe jane.doe@example.com"


# PERFORMANCE NOTE: this is split into a cheap check that runs at import
# time and an expensive one that runs on first fetch.
#
# `import edgar` costs ~14.5 SECONDS. This module previously called
# set_identity() (and therefore imported edgar) at module level, which
# meant clicking the Storyline page blocked for ~14.5s before Streamlit
# could render anything at all - no spinner, no skeleton, nothing, since
# no UI can be drawn while a module-level import is running.
#
# Reading the env var, by contrast, is free. So the validation stays
# eager (you still find out immediately if EDGAR_IDENTITY is missing,
# rather than after picking a ticker), while the edgar import and
# set_identity() call are deferred to the first actual filing fetch.

_MISSING_IDENTITY_MESSAGE = (
    "EDGAR_IDENTITY is not set. SEC EDGAR requires every automated "
    "caller to identify itself with a real name and email address. "
    "Add EDGAR_IDENTITY=\"Your Name your.email@example.com\" to your "
    ".env file before fetching filings."
)

_identity_configured = False


def _validate_edgar_identity() -> str:
    """Cheap check - no edgar import. Raises if EDGAR_IDENTITY is unusable."""
    identity = os.getenv("EDGAR_IDENTITY")

    if not identity or not identity.strip():
        raise RuntimeError(_MISSING_IDENTITY_MESSAGE)

    return identity.strip()


def _configure_edgar_identity() -> None:
    """
    Register the identity with edgartools, importing it on first use.
    Idempotent - the ~14.5s import is paid at most once per process.
    """
    global _identity_configured

    if _identity_configured:
        return

    identity = _validate_edgar_identity()

    from edgar import set_identity

    set_identity(identity)
    _identity_configured = True


# Eager validation only - deliberately does NOT import edgar.
_validate_edgar_identity()

ITEM7_HEADER = re.compile(
    r"^\s*item\s*7[\.\:\-\s].*(?:management|discussion|analysis|md\s*&\s*a|financial\s+condition|results\s+of\s+operations)",
    re.I,
)
ITEM7_HEADER_LOOSE = re.compile(r"^\s*item\s*7[\.\:\-\s]", re.I)
ITEM7_TEXT = re.compile(r"item\s*7", re.I)
ITEM_END = re.compile(r"^\s*item\s*(7a|8)[\.\:\-\s]", re.I)

BLOCK_TAGS = {"p", "div", "li", "h1", "h2", "h3", "h4", "h5", "h6", "td", "th"}
INLINE_TAGS = {"span", "a", "b", "strong", "i", "em", "font", "u"}


def get_tenK_filing(ticker: str, year: int):
    """
    Fetch the 10-K filing for a ticker and fiscal year from the SEC API.

    Returns:
        The edgartools filing object for that year's 10-K, or None if not found.
    """
    # Registers identity with edgartools and pays the (one-time) edgar
    # import cost here, on first actual fetch, rather than at page load.
    _configure_edgar_identity()

    from edgar import Company

    company = Company(ticker)
    filings = company.get_filings(year=year, form="10-K")
    if not filings:
        return None
    return filings.latest()


def get_item7_blocks(tenK) -> list[dict] | None:
    """
    Extract Item 7 (MD&A) from a 10-K filing as ordered structured blocks.

    Each block is a dict with ``type`` of ``"paragraph"`` or ``"table"``.
    """
    soup = BeautifulSoup(tenK.html(), "html.parser")

    start_el = _find_item7_start(soup)
    if start_el is None:
        return None

    end_el = _find_item7_end(start_el)
    return _extract_section_blocks(start_el, end_el)


def item7_cache_path(ticker: str, year: int) -> str:
    """Return the local cache file path for a ticker's Item 7 blocks."""
    return os.path.join(CACHE_DIR, f"{ticker.upper()}_item7_{year}.json")


def save_item7_cache(ticker: str, year: int, filing_date: str, blocks: list[dict]) -> dict:
    """Write extracted Item 7 blocks to the local cache."""
    payload = {
        "ticker": ticker.upper(),
        "year": year,
        "filing_date": filing_date,
        "extracted_at": datetime.now(timezone.utc).isoformat(),
        "blocks": blocks,
    }
    with open(item7_cache_path(ticker, year), "w", encoding="utf-8") as cache_file:
        json.dump(payload, cache_file, default=str)
    return payload


def fetch_item7(ticker: str, year: int) -> dict | None:
    """Fetch a 10-K from the SEC, extract Item 7 blocks, and save them to cache."""
    filing = get_tenK_filing(ticker, year)
    if filing is None:
        return None

    blocks = get_item7_blocks(filing)
    if blocks is None:
        return None

    return save_item7_cache(ticker, year, _filing_date(filing), blocks)


def _filing_date(filing) -> str:
    """Return the filing date string from an edgartools filing object."""
    filing_date = getattr(filing, "filing_date", None)
    return str(filing_date) if filing_date is not None else ""


def _normalize_text(text: str) -> str:
    """Collapse whitespace and strip surrounding space from extracted text."""
    return re.sub(r"[ \t]+", " ", text).strip()


def _is_inside_table(node) -> bool:
    """Return True if the node sits inside an HTML table (e.g. TOC rows)."""
    return node.find_parent("table") is not None


def _get_block_element(tag: Tag) -> Tag:
    """Walk up from an inline tag to its enclosing block-level element."""
    block = tag
    while block and block.name in INLINE_TAGS:
        block = block.parent
    return block


def _at_or_past_end(el, end_el: Tag | None) -> bool:
    """Return True when traversal has reached or passed the section end marker."""
    if end_el is None:
        return False
    if el is end_el:
        return True
    if isinstance(el, NavigableString):
        return end_el in el.parents
    return False


def _find_item7_start(soup: BeautifulSoup) -> Tag | None:
    """Find the first Item 7 header outside of tables (skips TOC)."""
    for text_node in soup.find_all(string=ITEM7_TEXT):
        if _is_inside_table(text_node):
            continue

        block = _get_block_element(text_node.parent)
        block_text = block.get_text(" ", strip=True)
        if ITEM7_HEADER.match(block_text) or ITEM7_HEADER_LOOSE.match(block_text):
            return block

    return None


def _find_item7_end(start_el: Tag) -> Tag | None:
    """Find where Item 7 ends (Item 7A or Item 8), ignoring table content."""
    for el in start_el.next_elements:
        if isinstance(el, NavigableString) and _is_inside_table(el):
            continue
        if isinstance(el, Tag) and el.name == "table":
            continue

        if isinstance(el, NavigableString):
            text = str(el).strip()
            parent = el.parent
        elif isinstance(el, Tag) and el.name in BLOCK_TAGS | INLINE_TAGS | {"a"}:
            text = el.get_text(" ", strip=True)
            parent = el
        else:
            continue

        if len(text) > 300:
            continue
        if ITEM_END.match(text):
            return _get_block_element(parent)

    return None


def _table_to_rows(table: Tag) -> tuple[list[str], list[list[str]]]:
    """Parse an HTML table into a header row and body rows."""
    rows = []
    for tr in table.find_all("tr"):
        cells = [
            _normalize_text(cell.get_text(" ", strip=True))
            for cell in tr.find_all(["th", "td"])
        ]
        if any(cells):
            rows.append(cells)

    if not rows:
        return [], []

    width = max(len(row) for row in rows)
    rows = [row + [""] * (width - len(row)) for row in rows]
    headers = rows[0]
    body = rows[1:] if len(rows) > 1 else []
    return headers, body


def _extract_section_blocks(start_el: Tag, end_el: Tag | None) -> list[dict]:
    """Extract Item 7 content between start and end markers as ordered blocks."""
    blocks = []
    seen_blocks = {id(start_el)}
    seen_tables = set()

    def add_paragraph(text: str):
        text = _normalize_text(text)
        if text:
            blocks.append({"type": "paragraph", "text": text})

    def add_table(table: Tag):
        headers, rows = _table_to_rows(table)
        if headers or rows:
            blocks.append({"type": "table", "headers": headers, "rows": rows})
            return

        fallback = _normalize_text(table.get_text("\n", strip=True))
        if fallback:
            add_paragraph(fallback)

    add_paragraph(start_el.get_text(" ", strip=True))

    for el in start_el.next_elements:
        if _at_or_past_end(el, end_el):
            break

        if isinstance(el, Tag) and el.name == "table":
            table_id = id(el)
            if table_id not in seen_tables:
                seen_tables.add(table_id)
                add_table(el)
            continue

        if isinstance(el, NavigableString):
            if _is_inside_table(el):
                continue

            block = _get_block_element(el.parent)
            if id(block) in seen_blocks:
                continue
            if block.name not in BLOCK_TAGS:
                continue

            seen_blocks.add(id(block))
            add_paragraph(block.get_text(" ", strip=True))

    return blocks