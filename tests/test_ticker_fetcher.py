"""Tests for data/ticker_fetcher.py"""

import pytest

import ticker_fetcher
from ticker_fetcher import find_valid_ticker, is_valid_ticker, normalize_text


@pytest.fixture(autouse=True)
def clear_index_cache():
    ticker_fetcher._load_index.cache_clear()
    yield
    ticker_fetcher._load_index.cache_clear()


def test_normalize_text_strips_suffixes():
    assert normalize_text("Apple Inc.") == "apple"
    assert normalize_text("Alphabet Inc.") == "alphabet"


def test_find_valid_ticker_by_symbol():
    assert find_valid_ticker("aapl") == "AAPL"
    assert find_valid_ticker("BRK-B") == "BRK-B"


def test_find_valid_ticker_by_company_name():
    assert find_valid_ticker("Apple Inc.") == "AAPL"
    assert find_valid_ticker("Alphabet Inc.") == "GOOGL"


def test_find_valid_ticker_by_alias():
    assert find_valid_ticker("Google") == "GOOGL"
    assert find_valid_ticker("facebook") == "META"


def test_find_valid_ticker_unknown():
    assert find_valid_ticker("Not A Real Company XYZ") is None
    assert find_valid_ticker("") is None


def test_is_valid_ticker():
    assert is_valid_ticker("AAPL") is True
    assert is_valid_ticker("GOOGL") is True
    assert is_valid_ticker("FAKE123") is False
    assert is_valid_ticker("Google") is False
