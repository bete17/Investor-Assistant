# ==========================================================
# CHANGE ENGINE
# ==========================================================
# What moved, and for how long it has been moving.
#
# ----------------------------------------------------------
# WHAT THIS IS FOR
# ----------------------------------------------------------
# Every other analytics module in this project reads a company's
# current condition: what the margins are, what the multiple is,
# whether the balance sheet is sound. This one reads the derivative -
# not where a number is, but which way it has been going.
#
# That distinction matters because the fields snapshot_store records
# are forecasts, and a forecast's direction carries information its
# level does not. A $170 target price says almost nothing on its own;
# knowing it was $185 a month ago and has been cut at every revision
# since says a great deal. Analysts are famously reluctant to move
# estimates, so when they do, and repeatedly in one direction, it is
# rarely noise.
#
# ----------------------------------------------------------
# WHY THE DATES TRAVEL WITH THE NUMBERS
# ----------------------------------------------------------
# The scheduled job records weekly, but the app also records any
# ticker somebody happens to look up on a cold cache. So consecutive
# rows are usually a week apart and sometimes a day, and no function
# here may assume otherwise. Every result carries the actual dates it
# was computed between, so a caller can say "cut 8% since August 3"
# rather than an unearned "cut 8% this week".
#
# ----------------------------------------------------------
# WHERE IT REFUSES TO COMPUTE
# ----------------------------------------------------------
# Same posture as kpi_engine: a percentage off a zero or negative
# base is arithmetic that produces a number without producing a
# meaning, so it is described in words instead. Forward EPS is the
# field where this actually bites - an estimate can legitimately sit
# below zero for a lossmaking company, and a swing from -0.40 to 0.10
# is unambiguously good news that the standard formula renders as
# -125%.

from datetime import date

# Below this, a move is rounding rather than a revision. Analyst
# targets get nudged by fractions of a percent constantly; treating
# every one as a signal would bury the moves that matter.
NOISE_THRESHOLD_PERCENT = 0.5

# Fields worth reporting on, and whether a rise is good news. Used to
# describe direction without the caller having to know that a falling
# target price is bad while a falling number of analysts is merely
# fewer opinions.
TRACKED_FIELDS = {
    "target_price": {"label": "Analyst target", "higher_is_better": True},
    "forward_eps": {"label": "Forward EPS estimate", "higher_is_better": True},
    "profit_margin": {"label": "Profit margin", "higher_is_better": True},
    "forward_pe": {"label": "Forward P/E", "higher_is_better": None},
    "num_analysts": {"label": "Analysts covering", "higher_is_better": None},
}


def _as_date(value):
    """Snapshot dates arrive as date objects from psycopg2 and as
    strings from anything that has been through JSON. Normalizing
    here keeps every caller from having to care which."""
    if isinstance(value, date):
        return value

    if isinstance(value, str):
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None

    return None


def _ordered(history):
    """Oldest first, rows without a usable date dropped.

    fetch_history returns newest first because that is what a caller
    displaying "latest" wants. Everything here reasons forward
    through time, and reversing once at the entrance is safer than
    each function remembering which way the list runs.
    """
    dated = []

    for row in history or []:
        when = _as_date(row.get("snapshot_date"))

        if when is not None:
            dated.append((when, row))

    dated.sort(key=lambda pair: pair[0])

    return [row for _, row in dated]


def _series(history, field):
    """(date, value) pairs for one field, skipping rows where it is
    missing. A field absent from some rows is normal - an ETF has no
    analyst target, and a company can lose coverage entirely - and a
    gap should shorten the series rather than break it."""
    points = []

    for row in _ordered(history):
        value = row.get(field)
        when = _as_date(row.get("snapshot_date"))

        if value is not None and when is not None:
            points.append((when, float(value)))

    return points


def latest_change(history, field):
    """
    How the most recent reading compares with the one before it.

    Returns None when there is nothing to compare - fewer than two
    readings, or a base the percentage would be meaningless against.
    None means "no claim", which is the honest output when a single
    observation is all that exists; a caller should say nothing
    rather than imply stability.
    """
    points = _series(history, field)

    if len(points) < 2:
        return None

    (prior_date, prior_value), (current_date, current_value) = points[-2], points[-1]

    change = current_value - prior_value

    result = {
        "field": field,
        "label": TRACKED_FIELDS.get(field, {}).get("label", field),
        "current": current_value,
        "prior": prior_value,
        "change": change,
        "from_date": prior_date,
        "to_date": current_date,
        "days_between": (current_date - prior_date).days,
        "percent": None,
        "direction": "flat",
    }

    # A percentage needs a positive base to mean anything. Zero makes
    # it undefined; a negative base inverts its sign, so a loss
    # narrowing reads as a decline. Both cases keep the absolute
    # change, which is always well defined, and drop the percentage.
    if prior_value > 0:
        result["percent"] = (change / prior_value) * 100

    reference = result["percent"]

    if reference is None:
        # With no percentage available, fall back to whether the raw
        # value moved at all.
        moved = abs(change) > 0
    else:
        moved = abs(reference) >= NOISE_THRESHOLD_PERCENT

    if moved:
        result["direction"] = "up" if change > 0 else "down"

    return result


def streak(history, field):
    """
    How many consecutive readings have moved the same way.

    A single revision is a data point; four in a row is a view. This
    counts back from the latest reading and stops at the first move
    in the other direction.

    Readings that did not move break nothing and count for nothing -
    an unchanged estimate is analysts declining to revise, which
    neither confirms nor contradicts the run either side of it.
    """
    points = _series(history, field)

    if len(points) < 2:
        return None

    moves = []

    for (_, earlier), (_, later) in zip(points, points[1:]):
        if later > earlier:
            moves.append("up")
        elif later < earlier:
            moves.append("down")
        else:
            moves.append("flat")

    directed = [move for move in moves if move != "flat"]

    if not directed:
        return None

    direction = directed[-1]
    count = 0

    for move in reversed(directed):
        if move != direction:
            break
        count += 1

    return {
        "field": field,
        "label": TRACKED_FIELDS.get(field, {}).get("label", field),
        "direction": direction,
        "count": count,
        "spans_days": (points[-1][0] - points[0][0]).days,
    }


def recommendation_change(history):
    """
    The most recent move in the analyst consensus label, if any.

    Handled separately from the numeric fields because it is
    categorical: "buy" to "hold" is a real event with no percentage
    attached, and it is often the clearest single line the app can
    show.
    """
    rows = _ordered(history)
    labels = [
        (_as_date(row.get("snapshot_date")), row.get("recommendation"))
        for row in rows
        if row.get("recommendation")
    ]

    if len(labels) < 2:
        return None

    (_, prior), (changed_on, current) = labels[-2], labels[-1]

    if prior == current:
        return None

    return {
        "from": prior,
        "to": current,
        "changed_on": changed_on,
    }


def summarize(history):
    """
    Everything worth saying about one ticker's recorded history.

    Returns a dict the UI can render without doing any arithmetic of
    its own - the same division of labour as the rest of analytics/,
    where the page decides what to show and this decides what is
    true.

    `has_history` is separated from an empty `changes` list on
    purpose. No rows means the store has never seen this ticker and
    the app should explain that; rows with nothing moving means the
    estimates genuinely held steady, which is itself worth saying.
    """
    rows = _ordered(history)

    summary = {
        "has_history": bool(rows),
        "readings": len(rows),
        "first_seen": _as_date(rows[0].get("snapshot_date")) if rows else None,
        "last_seen": _as_date(rows[-1].get("snapshot_date")) if rows else None,
        "changes": [],
        "streaks": [],
        "recommendation": recommendation_change(history),
    }

    for field in TRACKED_FIELDS:
        change = latest_change(history, field)

        if change and change["direction"] != "flat":
            summary["changes"].append(change)

        run = streak(history, field)

        # A run of one is just the latest change already reported.
        if run and run["count"] >= 2:
            summary["streaks"].append(run)

    # Biggest mover first, so a caller showing only the top line shows
    # the most consequential one. Changes without a percentage sort
    # last rather than being dropped - they are still real, just not
    # comparable on the same scale.
    summary["changes"].sort(
        key=lambda item: abs(item["percent"]) if item["percent"] is not None else -1,
        reverse=True,
    )

    return summary