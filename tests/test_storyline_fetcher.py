"""
Tests for data/storyline_fetcher.py

Run with: pytest tests/test_storyline_fetcher.py -v

Pipeline (matches storyline_fetcher.py):
1. Call the SEC API and fetch the 10-K
2. Confirm it is the right 10-K filing
3. Parse the filing and locate Item 7
4. Verify Item 7 block content is correct
5. Verify Item 7 block content is complete
6. Save extracted blocks to cache
7. Verify the cached JSON schema is correct
"""
 
import json
import os
from unittest.mock import MagicMock, patch

import pytest
from bs4 import BeautifulSoup

import storyline_fetcher
from storyline_fetcher import (
    _find_item7_start,
    fetch_item7,
    get_item7_blocks,
    get_tenK_filing,
    item7_cache_path,
    save_item7_cache,
)


# ----------------------------------------------------------
# Shared fixtures
# ----------------------------------------------------------


class _FakeFiling:
    """Minimal stand-in for an edgartools filing object in unit tests."""

    def __init__(
        self,
        html: str,
        *,
        form: str = "10-K",
        filing_date: str = "2024-11-01",
    ):
        self._html = html
        self.form = form
        self.filing_date = filing_date

    def html(self) -> str:
        return self._html


TOC_AND_ITEM7_HTML = """
<html><body>
<table>
  <tr><td>Item 7. Management's Discussion and Analysis</td><td>42</td></tr>
</table>
<div>Item 7. Management's Discussion and Analysis of Financial Condition</div>
<p>Revenue increased 12% year over year.</p>
<div>Item 7A. Quantitative and Qualitative Disclosures</div>
</body></html>
"""

ITEM7_WITH_TABLE_HTML = """
<html><body>
<div>Item 7. Management's Discussion and Analysis of Financial Condition</div>
<p>Revenue increased 12% year over year.</p>
<table>
  <tr><th>Metric</th><th>2024</th></tr>
  <tr><td>Revenue</td><td>$100M</td></tr>
</table>
<p>Operating margin improved to 25%.</p>
<div>Item 7A. Quantitative and Qualitative Disclosures</div>
</body></html>
"""

NO_ITEM7_HTML = """
<html><body>
<div>Item 1. Business</div>
<p>We sell software.</p>
<div>Item 8. Financial Statements</div>
</body></html>
"""

SAMPLE_BLOCKS = [
    {"type": "paragraph", "text": "Item 7 header"},
    {
        "type": "table",
        "headers": ["Metric", "2024"],
        "rows": [["Revenue", "$100M"]],
    },
]


@pytest.fixture
def cache_dir(tmp_path, monkeypatch):
    """Use a temp directory for cache files so tests do not touch real data."""
    monkeypatch.setattr(storyline_fetcher, "CACHE_DIR", str(tmp_path))
    return tmp_path


# ----------------------------------------------------------
# Step 1 — Call the SEC API and fetch the 10-K
# ----------------------------------------------------------


@patch("storyline_fetcher.get_tenK_filing")
def test_fetch_item7_fetches_data_from_api(mock_get_filing, cache_dir):
    mock_get_filing.return_value = _FakeFiling(TOC_AND_ITEM7_HTML)

    result = fetch_item7("AAPL", 2024)

    assert result is not None
    assert result["ticker"] == "AAPL"
    assert result["year"] == 2024
    assert result["blocks"]


# ----------------------------------------------------------
# Step 2 — Confirm it is the right 10-K filing
# ----------------------------------------------------------


def test_get_tenK_filing_returns_correct_filing():
    filing = _FakeFiling("", form="10-K", filing_date="2024-11-01")
    filings = MagicMock()
    filings.__bool__.return_value = True
    filings.latest.return_value = filing

    fake_edgar = MagicMock()
    fake_edgar.Company.return_value.get_filings.return_value = filings

    with patch.dict("sys.modules", {"edgar": fake_edgar}):
        result = get_tenK_filing("AAPL", 2024)

    fake_edgar.Company.assert_called_once_with("AAPL")
    fake_edgar.Company.return_value.get_filings.assert_called_once_with(
        year=2024,
        form="10-K",
    )
    assert result is filing
    assert result.form == "10-K"
    assert str(result.filing_date) == "2024-11-01"


# ----------------------------------------------------------
# Step 3 — Parse the filing and locate Item 7
# ----------------------------------------------------------


def test_get_item7_blocks_locates_item7():
    blocks = get_item7_blocks(_FakeFiling(ITEM7_WITH_TABLE_HTML))

    assert blocks is not None
    assert len(blocks) > 0
    assert blocks[0]["type"] == "paragraph"


# ----------------------------------------------------------
# Step 4 — Verify Item 7 block content is correct
# ----------------------------------------------------------


def test_get_item7_blocks_data_is_correct():
    blocks = get_item7_blocks(_FakeFiling(ITEM7_WITH_TABLE_HTML))

    assert blocks is not None

    paragraph_texts = [b["text"] for b in blocks if b["type"] == "paragraph"]
    assert any("Revenue increased 12%" in text for text in paragraph_texts)
    assert any("Operating margin improved to 25%" in text for text in paragraph_texts)

    table_blocks = [b for b in blocks if b["type"] == "table"]
    assert len(table_blocks) == 1
    assert table_blocks[0]["headers"] == ["Metric", "2024"]
    assert table_blocks[0]["rows"] == [["Revenue", "$100M"]]


# ----------------------------------------------------------
# Step 5 — Verify Item 7 block content is complete
# ----------------------------------------------------------


def test_get_item7_blocks_data_is_complete():
    blocks = get_item7_blocks(_FakeFiling(ITEM7_WITH_TABLE_HTML))

    assert blocks is not None

    paragraph_texts = [b["text"] for b in blocks if b["type"] == "paragraph"]
    assert paragraph_texts[0].startswith("Item 7.")
    assert any("Revenue increased 12%" in text for text in paragraph_texts)
    assert any("Operating margin improved to 25%" in text for text in paragraph_texts)
    assert not any("Item 7A" in text for text in paragraph_texts)
    assert any(b["type"] == "table" for b in blocks)


# ----------------------------------------------------------
# Step 6 — Save extracted blocks to cache
# ----------------------------------------------------------


@patch("storyline_fetcher.get_tenK_filing")
def test_fetch_item7_saves_data_to_cache(mock_get_filing, cache_dir):
    mock_get_filing.return_value = _FakeFiling(TOC_AND_ITEM7_HTML)

    fetch_item7("MSFT", 2023)

    cache_path = item7_cache_path("MSFT", 2023)
    assert cache_path.startswith(str(cache_dir))
    assert cache_path.endswith("MSFT_item7_2023.json")
    assert os.path.exists(cache_path)


# ----------------------------------------------------------
# Step 7 — Verify the cached JSON schema is correct
# ----------------------------------------------------------


def test_save_item7_cache_writes_correct_schema(cache_dir):
    payload = save_item7_cache("aapl", 2024, "2024-11-01", SAMPLE_BLOCKS)

    assert payload["ticker"] == "AAPL"
    assert payload["year"] == 2024
    assert payload["filing_date"] == "2024-11-01"
    assert payload["extracted_at"]
    assert payload["blocks"] == SAMPLE_BLOCKS

    cache_path = item7_cache_path("aapl", 2024)
    with open(cache_path, encoding="utf-8") as cache_file:
        saved = json.load(cache_file)

    assert saved == payload
    assert saved["blocks"][0]["type"] == "paragraph"
    assert saved["blocks"][1]["headers"] == ["Metric", "2024"]


# ----------------------------------------------------------
# Edge cases — parser boundaries
# ----------------------------------------------------------


def test_find_item7_start_skips_toc_table_entry():
    soup = BeautifulSoup(TOC_AND_ITEM7_HTML, "html.parser")
    start = _find_item7_start(soup)

    assert start is not None
    assert start.name == "div"
    assert "Financial Condition" in start.get_text(" ", strip=True)
    assert "42" not in start.get_text(" ", strip=True)


def test_get_item7_blocks_returns_none_when_item7_missing():
    blocks = get_item7_blocks(_FakeFiling(NO_ITEM7_HTML))

    assert blocks is None


def test_get_item7_blocks_skips_toc_false_positive():
    blocks = get_item7_blocks(_FakeFiling(TOC_AND_ITEM7_HTML))

    assert blocks is not None
    assert len(blocks) >= 2

    first_text = blocks[0]["text"]
    assert "42" not in first_text
    assert "Revenue increased 12%" in blocks[1]["text"]
