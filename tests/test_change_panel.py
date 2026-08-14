"""
Tests for change_panel.py

streamlit.markdown is monkeypatched throughout rather than run inside
a real Streamlit session, so these tests capture the HTML each call
would have rendered and assert against it directly.

Two things matter most here: the three distinct empty states never
get collapsed into each other (see the module's own header comment on
why that distinction is deliberate), and every value pulled from
analyst/database data - not just the hardcoded labels - is escaped
before it reaches unsafe_allow_html=True.

Run with: pytest tests/test_change_panel.py -v
"""

import pytest

import change_panel
from analytics.change_engine import TRACKED_FIELDS


class FakeStreamlit:
    def __init__(self):
        self.calls = []

    def markdown(self, html, unsafe_allow_html=False):
        self.calls.append(html)


@pytest.fixture
def fake_st(monkeypatch):
    fake = FakeStreamlit()
    monkeypatch.setattr(change_panel, "st", fake)
    return fake


def _change(field="target_price", direction="down", percent=-10.0, change=-38.0,
            prior=360.0, current=322.0, days_between=6):
    return {
        "field": field,
        "label": TRACKED_FIELDS[field]["label"],
        "current": current,
        "prior": prior,
        "change": change,
        "percent": percent,
        "direction": direction,
        "days_between": days_between,
    }


def _summary(**overrides):
    base = {
        "has_history": True,
        "readings": 3,
        "first_seen": "2026-08-01",
        "last_seen": "2026-08-14",
        "changes": [],
        "streaks": [],
        "recommendation": None,
    }
    base.update(overrides)
    return base


# ----------------------------------------------------------
# Pure helpers
# ----------------------------------------------------------

def test_escape_neutralizes_html():
    assert change_panel._escape("<script>alert(1)</script>") == (
        "&lt;script&gt;alert(1)&lt;/script&gt;"
    )


@pytest.mark.parametrize(
    "higher_is_better, direction, expected",
    [
        (True, "up", "positive"),
        (True, "down", "negative"),
        (False, "up", "negative"),
        (False, "down", "positive"),
        (None, "up", "neutral"),
        (None, "down", "neutral"),
    ],
)
def test_status_for_maps_direction_through_field_meaning(higher_is_better, direction, expected):
    assert change_panel._status_for({"direction": direction}, higher_is_better) == expected


def test_magnitude_prefers_percent_when_available():
    assert change_panel._magnitude(_change(percent=-10.5)) == "-10.5%"


def test_magnitude_falls_back_to_absolute_change():
    result = change_panel._magnitude(_change(percent=None, change=-0.3803))
    assert result == "-0.38"


@pytest.mark.parametrize(
    "days, expected",
    [
        (0, "since yesterday"),
        (1, "since yesterday"),
        (6, "over the past week"),
        (10, "over the past week"),
        (20, "over 20 days"),
        (30, "over the past month"),
        (60, "over 2 months"),
    ],
)
def test_elapsed_rounds_to_the_unit_a_reader_thinks_in(days, expected):
    assert change_panel._elapsed(days) == expected


# ----------------------------------------------------------
# Empty states - kept deliberately distinct, see module header
# ----------------------------------------------------------

def test_never_recorded_state(fake_st):
    change_panel.change_panel(_summary(has_history=False), TRACKED_FIELDS)

    assert len(fake_st.calls) == 1
    assert "No history recorded" in fake_st.calls[0]


def test_single_reading_state_names_the_start_date(fake_st):
    summary = _summary(readings=1, first_seen="2026-08-10")

    change_panel.change_panel(summary, TRACKED_FIELDS)

    assert len(fake_st.calls) == 1
    assert "Tracking started 2026-08-10" in fake_st.calls[0]


def test_no_moves_state_is_distinguished_from_no_history(fake_st):
    summary = _summary(readings=4, first_seen="2026-07-01")

    change_panel.change_panel(summary, TRACKED_FIELDS)

    assert len(fake_st.calls) == 1
    assert "no meaningful revisions" in fake_st.calls[0]
    assert "No history recorded" not in fake_st.calls[0]


# ----------------------------------------------------------
# Rendering real content
# ----------------------------------------------------------

def test_renders_a_change_line(fake_st):
    summary = _summary(changes=[_change()])

    change_panel.change_panel(summary, TRACKED_FIELDS)

    assert len(fake_st.calls) == 1
    assert "Analyst target" in fake_st.calls[0]
    assert "-10.0%" in fake_st.calls[0]


def test_renders_recommendation_line(fake_st):
    summary = _summary(recommendation={"from": "hold", "to": "buy", "changed_on": "2026-08-10"})

    change_panel.change_panel(summary, TRACKED_FIELDS)

    assert any("Analyst consensus" in call for call in fake_st.calls)
    assert any("hold" in call and "buy" in call for call in fake_st.calls)


def test_recommendation_values_are_escaped(fake_st):
    # 'to'/'from' ultimately trace back to a database column an
    # analyst-feed integration writes, not a hardcoded label, so it
    # goes through the same escaping as everything else user-shaped.
    malicious = {"from": "hold", "to": "<img src=x onerror=alert(1)>", "changed_on": "2026-08-10"}
    summary = _summary(recommendation=malicious)

    change_panel.change_panel(summary, TRACKED_FIELDS)

    rendered = fake_st.calls[0]
    assert "<img" not in rendered
    assert "&lt;img" in rendered


def test_streak_suppresses_the_duplicate_change_line(fake_st):
    # A field already reported as a streak shouldn't repeat as a
    # standalone change line underneath it.
    run = {"field": "target_price", "label": "Analyst target", "direction": "down",
           "count": 3, "spans_days": 21}
    summary = _summary(streaks=[run], changes=[_change(field="target_price")])

    change_panel.change_panel(summary, TRACKED_FIELDS)

    assert len(fake_st.calls) == 1
    assert "in a row" in fake_st.calls[0]


def test_changes_are_capped_at_limit(fake_st):
    changes = [
        _change(field="target_price", percent=-20),
        _change(field="forward_eps", percent=-15),
        _change(field="profit_margin", percent=-10),
    ]
    summary = _summary(changes=changes)

    change_panel.change_panel(summary, TRACKED_FIELDS, limit=2)

    assert len(fake_st.calls) == 2
