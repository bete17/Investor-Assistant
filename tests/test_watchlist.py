"""
Tests for watchlist.py

The watchlist is the only thing in this app that persists to disk on
the user's behalf, so the bar for not losing or corrupting it is
higher than for anything else here.

Run with: pytest tests/test_watchlist.py -v
"""

import json

import pytest

from analytics.watchlist import (
    MAX_ENTRIES,
    add_ticker,
    get_tickers,
    is_watched,
    load_watchlist,
    normalize_ticker,
    remove_ticker,
    save_watchlist,
    toggle_ticker,
)


@pytest.fixture
def store(tmp_path):
    """An isolated watchlist file, so tests never touch the real one."""
    return str(tmp_path / "watchlist.json")


# ----------------------------------------------------------
# normalize_ticker
# ----------------------------------------------------------

@pytest.mark.parametrize(
    "raw, expected",
    [
        ("aapl", "AAPL"),
        ("  msft  ", "MSFT"),
        ("BRK-B", "BRK-B"),
        ("BF.B", "BF.B"),
        ("", None),
        ("   ", None),
        (None, None),
        ("NOT A TICKER", None),
        ("WAYTOOLONGSYMBOL", None),
        ("<script>", None),
        (123, None),
    ],
)
def test_normalize_ticker(raw, expected):
    assert normalize_ticker(raw) == expected


# ----------------------------------------------------------
# Basic operations
# ----------------------------------------------------------

def test_missing_file_reads_as_empty(store):
    assert load_watchlist(store) == []
    assert get_tickers(store) == []


def test_add_then_read_back(store):
    assert add_ticker("aapl", store) is True
    assert get_tickers(store) == ["AAPL"]


def test_adding_is_idempotent(store):
    add_ticker("AAPL", store)

    assert add_ticker("AAPL", store) is False
    assert get_tickers(store) == ["AAPL"]


def test_adding_is_case_insensitive(store):
    add_ticker("AAPL", store)

    assert add_ticker("aapl", store) is False
    assert get_tickers(store) == ["AAPL"]


def test_invalid_tickers_are_never_stored(store):
    assert add_ticker("NOT A TICKER", store) is False
    assert add_ticker("", store) is False
    assert get_tickers(store) == []


def test_most_recent_addition_comes_first(store):
    add_ticker("AAPL", store)
    add_ticker("MSFT", store)
    add_ticker("NVDA", store)

    assert get_tickers(store) == ["NVDA", "MSFT", "AAPL"]


def test_remove(store):
    add_ticker("AAPL", store)
    add_ticker("MSFT", store)

    assert remove_ticker("aapl", store) is True
    assert get_tickers(store) == ["MSFT"]


def test_removing_something_absent_reports_false(store):
    assert remove_ticker("AAPL", store) is False


def test_is_watched(store):
    add_ticker("AAPL", store)

    assert is_watched("aapl", store) is True
    assert is_watched("MSFT", store) is False
    assert is_watched("not a ticker", store) is False


def test_toggle_adds_then_removes(store):
    assert toggle_ticker("AAPL", store) is True
    assert is_watched("AAPL", store) is True

    assert toggle_ticker("AAPL", store) is False
    assert is_watched("AAPL", store) is False


def test_entries_record_when_they_were_added(store):
    add_ticker("AAPL", store)
    entry = load_watchlist(store)[0]

    assert entry["ticker"] == "AAPL"
    assert entry["added_at"]


# ----------------------------------------------------------
# Resilience
# ----------------------------------------------------------

def test_corrupt_file_reads_as_empty_rather_than_crashing(store):
    with open(store, "w", encoding="utf-8") as handle:
        handle.write("{ this is not json")

    assert load_watchlist(store) == []


def test_unexpected_json_shape_reads_as_empty(store):
    with open(store, "w", encoding="utf-8") as handle:
        json.dump({"tickers": ["AAPL"]}, handle)

    assert load_watchlist(store) == []


def test_a_hand_edited_plain_list_is_still_readable(store):
    # The file is plain JSON in a user's own directory, so it will get
    # hand-edited. A bare list of symbols is the obvious thing someone
    # would write, and it should work.
    with open(store, "w", encoding="utf-8") as handle:
        json.dump(["aapl", "msft"], handle)

    assert get_tickers(store) == ["AAPL", "MSFT"]


def test_invalid_entries_in_the_file_are_dropped_on_read(store):
    with open(store, "w", encoding="utf-8") as handle:
        json.dump(
            [
                {"ticker": "AAPL"},
                {"ticker": "<script>alert(1)</script>"},
                {"nonsense": True},
                "MSFT",
                42,
            ],
            handle,
        )

    assert get_tickers(store) == ["AAPL", "MSFT"]


def test_duplicates_in_the_file_are_collapsed_on_read(store):
    with open(store, "w", encoding="utf-8") as handle:
        json.dump(["AAPL", "aapl", "AAPL"], handle)

    assert get_tickers(store) == ["AAPL"]


def test_the_list_is_capped(store):
    entries = [{"ticker": f"T{index}"} for index in range(MAX_ENTRIES + 10)]
    save_watchlist(entries, store)

    assert len(get_tickers(store)) == MAX_ENTRIES


def test_saving_replaces_the_file_atomically(store):
    add_ticker("AAPL", store)
    add_ticker("MSFT", store)

    # No temporary file should be left behind after a successful write.
    import os

    assert not os.path.exists(f"{store}.tmp")
    assert get_tickers(store) == ["MSFT", "AAPL"]
