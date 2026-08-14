"""
Tests for change_engine.py

This module's whole job is to turn a row history into a claim about
direction, and to say nothing when a claim would be unearned - so the
tests lean hardest on the refusal cases (one reading, a non-positive
base, an all-flat series) rather than the happy path.

Run with: pytest tests/test_change_engine.py -v
"""

from datetime import date

import pytest

from analytics.change_engine import (
    TRACKED_FIELDS,
    latest_change,
    recommendation_change,
    streak,
    summarize,
)


def _row(day, **fields):
    return {"snapshot_date": day, **fields}


# ----------------------------------------------------------
# latest_change
# ----------------------------------------------------------

def test_no_claim_with_fewer_than_two_readings():
    assert latest_change([_row(date(2026, 1, 1), target_price=100)], "target_price") is None
    assert latest_change([], "target_price") is None


def test_rise_is_reported_as_up():
    history = [
        _row(date(2026, 1, 1), target_price=100),
        _row(date(2026, 1, 8), target_price=110),
    ]

    result = latest_change(history, "target_price")

    assert result["direction"] == "up"
    assert result["change"] == pytest.approx(10)
    assert result["percent"] == pytest.approx(10.0)
    assert result["days_between"] == 7


def test_percent_omitted_when_prior_value_is_zero_or_negative():
    # A base of zero makes the percentage undefined; a negative base
    # inverts its sign. Both keep the absolute change and drop percent
    # rather than report a misleading number.
    zero_base = [
        _row(date(2026, 1, 1), forward_eps=0),
        _row(date(2026, 1, 8), forward_eps=0.5),
    ]
    negative_base = [
        _row(date(2026, 1, 1), forward_eps=-0.40),
        _row(date(2026, 1, 8), forward_eps=0.10),
    ]

    zero_result = latest_change(zero_base, "forward_eps")
    negative_result = latest_change(negative_base, "forward_eps")

    assert zero_result["percent"] is None
    assert zero_result["direction"] == "up"

    assert negative_result["percent"] is None
    assert negative_result["change"] == pytest.approx(0.5)
    assert negative_result["direction"] == "up"


def test_move_below_noise_threshold_reads_as_flat():
    history = [
        _row(date(2026, 1, 1), target_price=100),
        _row(date(2026, 1, 8), target_price=100.2),
    ]

    result = latest_change(history, "target_price")

    assert result["direction"] == "flat"
    assert result["percent"] == pytest.approx(0.2)


def test_unordered_input_is_sorted_before_comparing():
    # fetch_history hands back newest-first; summarize's callers should
    # not have to pre-sort, and a caller who passes rows out of order
    # entirely must still get the right prior/current pairing.
    history = [
        _row(date(2026, 1, 8), target_price=110),
        _row(date(2026, 1, 1), target_price=100),
    ]

    result = latest_change(history, "target_price")

    assert result["prior"] == 100
    assert result["current"] == 110
    assert result["from_date"] == date(2026, 1, 1)
    assert result["to_date"] == date(2026, 1, 8)


def test_rows_missing_the_field_are_skipped_not_treated_as_zero():
    # An ETF has no analyst target on some rows and one on others; a
    # gap should shorten the series, not inject a false zero reading.
    history = [
        _row(date(2026, 1, 1), target_price=100),
        _row(date(2026, 1, 8)),
        _row(date(2026, 1, 15), target_price=90),
    ]

    result = latest_change(history, "target_price")

    assert result["prior"] == 100
    assert result["current"] == 90
    assert result["days_between"] == 14


def test_string_dates_from_json_are_normalized():
    history = [
        {"snapshot_date": "2026-01-01T00:00:00", "target_price": 100},
        {"snapshot_date": "2026-01-08", "target_price": 90},
    ]

    result = latest_change(history, "target_price")

    assert result["from_date"] == date(2026, 1, 1)
    assert result["to_date"] == date(2026, 1, 8)


def test_unparseable_date_row_is_dropped():
    history = [
        _row(date(2026, 1, 1), target_price=100),
        {"snapshot_date": "not a date", "target_price": 105},
        _row(date(2026, 1, 8), target_price=90),
    ]

    result = latest_change(history, "target_price")

    # The bad row is dropped entirely, so the comparison is between the
    # two remaining valid readings.
    assert result["prior"] == 100
    assert result["current"] == 90


# ----------------------------------------------------------
# streak
# ----------------------------------------------------------

def test_no_streak_with_fewer_than_two_readings():
    assert streak([_row(date(2026, 1, 1), target_price=100)], "target_price") is None


def test_streak_counts_consecutive_moves_in_one_direction():
    history = [
        _row(date(2026, 1, 1), target_price=100),
        _row(date(2026, 1, 8), target_price=95),
        _row(date(2026, 1, 15), target_price=90),
        _row(date(2026, 1, 22), target_price=85),
    ]

    result = streak(history, "target_price")

    assert result["direction"] == "down"
    assert result["count"] == 3
    assert result["spans_days"] == 21


def test_streak_stops_at_the_first_reversal():
    history = [
        _row(date(2026, 1, 1), target_price=100),
        _row(date(2026, 1, 8), target_price=90),
        _row(date(2026, 1, 15), target_price=95),
        _row(date(2026, 1, 22), target_price=90),
        _row(date(2026, 1, 29), target_price=80),
    ]

    result = streak(history, "target_price")

    # Latest direction is down, and it only runs back through the most
    # recent two moves before hitting the up-move that breaks it.
    assert result["direction"] == "down"
    assert result["count"] == 2


def test_flat_moves_break_the_streak_without_counting():
    history = [
        _row(date(2026, 1, 1), target_price=100),
        _row(date(2026, 1, 8), target_price=90),
        _row(date(2026, 1, 15), target_price=90),
        _row(date(2026, 1, 22), target_price=80),
    ]

    result = streak(history, "target_price")

    assert result["direction"] == "down"
    assert result["count"] == 2


def test_all_flat_series_has_no_streak():
    history = [
        _row(date(2026, 1, 1), target_price=100),
        _row(date(2026, 1, 8), target_price=100),
    ]

    assert streak(history, "target_price") is None


# ----------------------------------------------------------
# recommendation_change
# ----------------------------------------------------------

def test_recommendation_change_reports_the_latest_move():
    history = [
        _row(date(2026, 1, 1), recommendation="hold"),
        _row(date(2026, 1, 8), recommendation="buy"),
    ]

    result = recommendation_change(history)

    assert result == {"from": "hold", "to": "buy", "changed_on": date(2026, 1, 8)}


def test_recommendation_unchanged_reports_none():
    history = [
        _row(date(2026, 1, 1), recommendation="buy"),
        _row(date(2026, 1, 8), recommendation="buy"),
    ]

    assert recommendation_change(history) is None


def test_recommendation_change_needs_two_labeled_readings():
    assert recommendation_change([_row(date(2026, 1, 1), recommendation="buy")]) is None


# ----------------------------------------------------------
# summarize
# ----------------------------------------------------------

def test_summarize_with_no_rows_reports_no_history():
    result = summarize([])

    assert result["has_history"] is False
    assert result["changes"] == []
    assert result["streaks"] == []


def test_summarize_with_one_row_has_history_but_no_changes():
    result = summarize([_row(date(2026, 1, 1), target_price=100)])

    assert result["has_history"] is True
    assert result["readings"] == 1
    assert result["changes"] == []


def test_summarize_reports_first_and_last_seen():
    history = [
        _row(date(2026, 1, 1), target_price=100),
        _row(date(2026, 1, 8), target_price=90),
        _row(date(2026, 1, 15), target_price=80),
    ]

    result = summarize(history)

    assert result["first_seen"] == date(2026, 1, 1)
    assert result["last_seen"] == date(2026, 1, 15)
    assert result["readings"] == 3


def test_summarize_orders_changes_biggest_percent_move_first():
    history = [
        _row(date(2026, 1, 1), target_price=100, forward_eps=1.0),
        _row(date(2026, 1, 8), target_price=95, forward_eps=1.5),
    ]

    result = summarize(history)

    assert [c["field"] for c in result["changes"]] == ["forward_eps", "target_price"]


def test_summarize_drops_flat_fields_from_changes():
    history = [
        _row(date(2026, 1, 1), target_price=100, num_analysts=10),
        _row(date(2026, 1, 8), target_price=90, num_analysts=10),
    ]

    result = summarize(history)

    assert [c["field"] for c in result["changes"]] == ["target_price"]


def test_summarize_only_reports_streaks_of_two_or_more():
    history = [
        _row(date(2026, 1, 1), target_price=100),
        _row(date(2026, 1, 8), target_price=90),
    ]

    result = summarize(history)

    # A single move is already covered by "changes"; streaks should
    # not duplicate it as a "streak" of one.
    assert result["streaks"] == []


def test_summarize_field_labels_come_from_tracked_fields():
    history = [
        _row(date(2026, 1, 1), target_price=100),
        _row(date(2026, 1, 8), target_price=90),
    ]

    result = summarize(history)

    assert result["changes"][0]["label"] == TRACKED_FIELDS["target_price"]["label"]
