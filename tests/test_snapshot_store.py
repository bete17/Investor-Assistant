"""
Tests for snapshot_store.py

No test here touches a real database - _connect() is monkeypatched
throughout, either to a fake connection/cursor or to None, the way a
missing INVESTOR_ASSISTANT_DATABASE_URL would leave it in production.

The module is designed to fail silently everywhere except record_many,
so most of what's worth testing is exactly that: a bad connection or a
driver error degrades to "no history" / "not written", never a raised
exception reaching the caller.

Run with: pytest tests/test_snapshot_store.py -v
"""

from datetime import date
from decimal import Decimal

import pytest

import data.snapshot_store as snapshot_store


class FakeCursor:
    def __init__(self, fetch_rows=None, error=None):
        self.executed = []
        self._fetch_rows = fetch_rows or []
        self._error = error

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def execute(self, statement, params=None):
        if self._error is not None:
            raise self._error
        self.executed.append((statement, params))

    def fetchall(self):
        return self._fetch_rows


class FakeConnection:
    def __init__(self, fetch_rows=None, error=None):
        self.cursor_obj = FakeCursor(fetch_rows, error)
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def cursor(self):
        return self.cursor_obj

    def close(self):
        self.closed = True


def _snapshot(**overrides):
    base = {"ticker": "aapl", "price": 200.0, "target_price": 210.0}
    base.update(overrides)
    return base


# ----------------------------------------------------------
# is_configured / _dsn
# ----------------------------------------------------------

def test_is_configured_true_when_specific_var_set(monkeypatch):
    monkeypatch.setenv(snapshot_store.PATH_ENV_VAR, "postgres://example")
    monkeypatch.delenv("DATABASE_URL", raising=False)

    assert snapshot_store.is_configured() is True


def test_is_configured_true_when_only_generic_var_set(monkeypatch):
    monkeypatch.delenv(snapshot_store.PATH_ENV_VAR, raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgres://example")

    assert snapshot_store.is_configured() is True


def test_is_configured_false_when_neither_var_set(monkeypatch):
    monkeypatch.delenv(snapshot_store.PATH_ENV_VAR, raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)

    assert snapshot_store.is_configured() is False


def test_specific_var_takes_precedence_over_generic(monkeypatch):
    monkeypatch.setenv(snapshot_store.PATH_ENV_VAR, "postgres://specific")
    monkeypatch.setenv("DATABASE_URL", "postgres://generic")

    assert snapshot_store._dsn() == "postgres://specific"


# ----------------------------------------------------------
# record_snapshot
# ----------------------------------------------------------

def test_record_snapshot_rejects_empty_snapshot():
    assert snapshot_store.record_snapshot({}) is False
    assert snapshot_store.record_snapshot(None) is False


def test_record_snapshot_rejects_missing_ticker():
    assert snapshot_store.record_snapshot({"price": 100}) is False


def test_record_snapshot_returns_false_when_unconfigured(monkeypatch):
    monkeypatch.setattr(snapshot_store, "_connect", lambda: None)

    assert snapshot_store.record_snapshot(_snapshot()) is False


def test_record_snapshot_upserts_with_parameterized_values(monkeypatch):
    fake = FakeConnection()
    monkeypatch.setattr(snapshot_store, "_connect", lambda: fake)

    ok = snapshot_store.record_snapshot(_snapshot(), on_date=date(2026, 8, 10))

    assert ok is True
    statement, params = fake.cursor_obj.executed[0]

    assert "INSERT INTO market_snapshot" in statement
    assert "ON CONFLICT (ticker, snapshot_date) DO UPDATE SET" in statement

    # Every value travels as a bind parameter, never formatted into the
    # SQL text itself - only the column names (a fixed, hardcoded set,
    # never attacker-influenced) appear as literal text.
    placeholder_count = statement.count("%s")
    assert placeholder_count == len(["ticker", "snapshot_date"] + snapshot_store._ORDERED)
    assert "AAPL" not in statement
    assert "210.0" not in statement

    assert params[0] == "AAPL"  # ticker is upper-cased before storage
    assert params[1] == date(2026, 8, 10)
    assert params[2 + snapshot_store._ORDERED.index("target_price")] == 210.0


def test_record_snapshot_defaults_to_todays_utc_date(monkeypatch):
    fake = FakeConnection()
    monkeypatch.setattr(snapshot_store, "_connect", lambda: fake)
    monkeypatch.setattr(snapshot_store, "_snapshot_date", lambda: date(2026, 1, 1))

    snapshot_store.record_snapshot(_snapshot())

    _, params = fake.cursor_obj.executed[0]
    assert params[1] == date(2026, 1, 1)


def test_record_snapshot_missing_fields_are_stored_as_none(monkeypatch):
    fake = FakeConnection()
    monkeypatch.setattr(snapshot_store, "_connect", lambda: fake)

    # A sparse snapshot (e.g. an ETF with no analyst target) must not
    # raise a KeyError while building the value list.
    snapshot_store.record_snapshot({"ticker": "SPY"})

    _, params = fake.cursor_obj.executed[0]
    assert params[2:] == [None] * len(snapshot_store._ORDERED)


def test_record_snapshot_swallows_driver_errors(monkeypatch):
    fake = FakeConnection(error=RuntimeError("connection reset"))
    monkeypatch.setattr(snapshot_store, "_connect", lambda: fake)

    assert snapshot_store.record_snapshot(_snapshot()) is False


def test_record_snapshot_closes_the_connection_even_on_failure(monkeypatch):
    fake = FakeConnection(error=RuntimeError("boom"))
    monkeypatch.setattr(snapshot_store, "_connect", lambda: fake)

    snapshot_store.record_snapshot(_snapshot())

    assert fake.closed is True


# ----------------------------------------------------------
# fetch_history
# ----------------------------------------------------------

@pytest.mark.parametrize("bad_ticker", ["", "   ", None])
def test_fetch_history_rejects_blank_ticker(bad_ticker):
    assert snapshot_store.fetch_history(bad_ticker) == []


def test_fetch_history_returns_empty_when_unconfigured(monkeypatch):
    monkeypatch.setattr(snapshot_store, "_connect", lambda: None)

    assert snapshot_store.fetch_history("AAPL") == []


def test_fetch_history_swallows_driver_errors(monkeypatch):
    fake = FakeConnection(error=RuntimeError("timeout"))
    monkeypatch.setattr(snapshot_store, "_connect", lambda: fake)

    assert snapshot_store.fetch_history("AAPL") == []


def test_fetch_history_converts_decimal_columns_to_float(monkeypatch):
    columns = ["snapshot_date"] + snapshot_store._ORDERED
    row = tuple(
        date(2026, 8, 10) if column == "snapshot_date"
        else "buy" if column == "recommendation"
        else Decimal("123.45")
        for column in columns
    )
    fake = FakeConnection(fetch_rows=[row])
    monkeypatch.setattr(snapshot_store, "_connect", lambda: fake)

    history = snapshot_store.fetch_history("AAPL")

    assert len(history) == 1
    record = history[0]
    assert record["snapshot_date"] == date(2026, 8, 10)
    assert record["recommendation"] == "buy"
    assert record["price"] == pytest.approx(123.45)
    assert isinstance(record["price"], float)


def test_fetch_history_leaves_null_fields_as_none(monkeypatch):
    columns = ["snapshot_date"] + snapshot_store._ORDERED
    row = tuple(date(2026, 8, 10) if column == "snapshot_date" else None for column in columns)
    fake = FakeConnection(fetch_rows=[row])
    monkeypatch.setattr(snapshot_store, "_connect", lambda: fake)

    record = snapshot_store.fetch_history("AAPL")[0]

    assert record["target_price"] is None
    assert record["recommendation"] is None


def test_fetch_history_queries_by_upper_ticker_and_limit(monkeypatch):
    fake = FakeConnection()
    monkeypatch.setattr(snapshot_store, "_connect", lambda: fake)

    snapshot_store.fetch_history("aapl", limit=5)

    _, params = fake.cursor_obj.executed[0]
    assert params == ("AAPL", 5)


# ----------------------------------------------------------
# record_many
# ----------------------------------------------------------

def test_record_many_counts_successes_only(monkeypatch):
    results = iter([True, False, True])
    monkeypatch.setattr(snapshot_store, "record_snapshot", lambda snap, on_date=None: next(results))

    written = snapshot_store.record_many([_snapshot(), _snapshot(), _snapshot()])

    assert written == 2


def test_record_many_continues_after_a_failure(monkeypatch):
    calls = []

    def fake_record(snap, on_date=None):
        calls.append(snap["ticker"])
        return snap["ticker"] != "BAD"

    monkeypatch.setattr(snapshot_store, "record_snapshot", fake_record)

    written = snapshot_store.record_many(
        [_snapshot(ticker="AAPL"), _snapshot(ticker="BAD"), _snapshot(ticker="MSFT")]
    )

    assert written == 2
    assert calls == ["AAPL", "BAD", "MSFT"]
