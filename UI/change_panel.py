# ==========================================================
# CHANGE PANEL
# ==========================================================
# Renders what change_engine found, and nothing else.
#
# Kept out of components.py because that file is shared markup for
# things two pages already draw, whereas this is one feature's whole
# presentation layer - phrasing, ordering, and the empty states that
# matter more here than anywhere else in the app.
#
# ----------------------------------------------------------
# WHY THE EMPTY STATES GET THIS MUCH ATTENTION
# ----------------------------------------------------------
# For the first few weeks after this ships, the empty state IS the
# feature for most tickers - there is no history yet, and there is no
# way to backfill it. A panel that renders nothing looks broken; one
# that says "tracking started August 14, check back next week" reads
# as a feature that has not finished loading in the calendar sense
# rather than a bug.
#
# Three distinct nothings, deliberately worded differently:
#   never recorded      -> we have not started tracking this
#   one reading         -> tracking started, nothing to compare yet
#   readings, no moves  -> estimates genuinely held steady
# The third is a real finding. Analysts leaving numbers alone through
# an earnings season says something, and collapsing it into the same
# grey box as "no data" would throw that away.
#
# No new CSS: this reuses read-card and kpi-status from styles.css,
# which already carry the design system's spacing and status colours.

import html

import streamlit as st

_STATUS_BY_DIRECTION = {
    # Direction is mapped to colour through the field's own meaning,
    # not through the sign of the number. A falling target price is
    # bad news; a falling forward P/E is cheaper, which is not. Fields
    # where the answer genuinely depends on context render neutral
    # rather than guessing.
    (True, "up"): "positive",
    (True, "down"): "negative",
    (False, "up"): "negative",
    (False, "down"): "positive",
}


def _escape(value):
    return html.escape(str(value))


def _status_for(change, higher_is_better):
    if higher_is_better is None:
        return "neutral"

    return _STATUS_BY_DIRECTION.get(
        (higher_is_better, change["direction"]), "neutral"
    )


def _magnitude(change):
    """How far it moved, as a phrase.

    Percentage where the base allowed one, absolute otherwise - see
    change_engine on why some moves have no meaningful percentage.
    """
    if change["percent"] is not None:
        return f"{change['percent']:+.1f}%"

    return f"{change['change']:+,.2f}"


def _elapsed(days):
    """Say how long the move took, in the units a reader thinks in.

    The scheduled job runs weekly but the app records opportunistically,
    so gaps are genuinely irregular. Rounding a 6- or 8-day gap to "a
    week" is honest; claiming a precise day count nobody asked for is
    just noise.
    """
    if days <= 1:
        return "since yesterday"

    if days <= 10:
        return "over the past week"

    if days <= 24:
        return f"over {days} days"

    return f"over {round(days / 30)} months" if days >= 45 else "over the past month"


def _change_line(change, higher_is_better):
    status = _status_for(change, higher_is_better)
    direction_word = "raised" if change["direction"] == "up" else "cut"

    # "Raised" and "cut" fit an analyst revision, which is what most
    # of these fields are. For the ones that are observations rather
    # than decisions, a neutral verb is more accurate.
    if higher_is_better is None:
        direction_word = "rose" if change["direction"] == "up" else "fell"

    st.markdown(
        f"""
<div class="read-card">
    <div class="read-head">
        <span class="read-title">{_escape(change["label"])}</span>
        <span class="kpi-status {status}">
            <span class="status-dot"></span>{_escape(_magnitude(change))}
        </span>
    </div>
    <div class="read-body">
        {_escape(f"{direction_word.capitalize()} from {change['prior']:,.2f} "
                 f"to {change['current']:,.2f} {_elapsed(change['days_between'])}.")}
    </div>
</div>
""",
        unsafe_allow_html=True,
    )


def _streak_line(run):
    # A run in one direction is the finding worth leading with, so it
    # gets the emphatic treatment - it is the difference between "the
    # target moved" and "the target has moved the same way four times
    # running", and only the second is hard to dismiss as noise.
    plural = "s" if run["count"] != 1 else ""
    verb = "increases" if run["direction"] == "up" else "cuts"

    st.markdown(
        f"""
<div class="read-card">
    <div class="read-head">
        <span class="read-title">{_escape(run["label"])}</span>
        <span class="kpi-status warning">
            <span class="status-dot"></span>{_escape(f"{run['count']} in a row")}
        </span>
    </div>
    <div class="read-body">
        {_escape(f"{run['count']} consecutive {verb[:-1] if run['count'] == 1 else verb} "
                 f"across {run['count'] + 1} readings{plural and ''}.")}
    </div>
</div>
""",
        unsafe_allow_html=True,
    )


def _recommendation_line(move):
    st.markdown(
        f"""
<div class="read-card">
    <div class="read-head">
        <span class="read-title">Analyst consensus</span>
        <span class="kpi-status neutral">
            <span class="status-dot"></span>{_escape(move["to"].replace("_", " ").title())}
        </span>
    </div>
    <div class="read-body">
        {_escape(f"Moved from {move['from'].replace('_', ' ')} to "
                 f"{move['to'].replace('_', ' ')} on {move['changed_on']}.")}
    </div>
</div>
""",
        unsafe_allow_html=True,
    )


def _empty(message):
    st.markdown(
        f"""
<div class="read-card">
    <div class="read-body">{_escape(message)}</div>
</div>
""",
        unsafe_allow_html=True,
    )


def change_panel(summary, tracked_fields, limit=4):
    """
    Render one ticker's recorded change history.

    `summary` is change_engine.summarize output; `tracked_fields` is
    its TRACKED_FIELDS map, passed in rather than imported so this
    module stays a pure renderer with no analytics dependency.

    `limit` caps the numeric changes shown. summarize already sorts
    biggest first, so the cap drops the least consequential rows -
    five near-identical small moves would bury the one that matters.
    """
    if not summary.get("has_history"):
        _empty(
            "No history recorded for this company yet. Estimates are stored "
            "each week from the first time it's looked up, so check back."
        )
        return

    if summary["readings"] < 2:
        _empty(
            f"Tracking started {summary['first_seen']}. One reading so far - "
            "there'll be something to compare after the next one."
        )
        return

    if summary["recommendation"]:
        _recommendation_line(summary["recommendation"])

    for run in summary["streaks"][:2]:
        _streak_line(run)

    shown = 0

    for change in summary["changes"]:
        # A field already reported as a streak doesn't need its latest
        # move repeated underneath - the streak line is strictly more
        # informative about the same number.
        if any(run["field"] == change["field"] for run in summary["streaks"][:2]):
            continue

        meta = tracked_fields.get(change["field"], {})
        _change_line(change, meta.get("higher_is_better"))
        shown += 1

        if shown >= limit:
            break

    if not shown and not summary["streaks"] and not summary["recommendation"]:
        _empty(
            f"{summary['readings']} readings since {summary['first_seen']}, with "
            "no meaningful revisions. Analysts have left their estimates alone."
        )