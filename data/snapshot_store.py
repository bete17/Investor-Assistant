# ==========================================================
# SNAPSHOT STORE
# ==========================================================
# Durable history for the fields that only ever exist as "now".
#
# ----------------------------------------------------------
# WHY THIS EXISTS
# ----------------------------------------------------------
# Prices are already historical: yfinance will hand back years of
# daily closes in one call, so storing them ourselves would buy
# nothing. Analyst expectations are the opposite. Ask for a target
# price and you get today's number; there is no way to ask what it
# was three weeks ago, because each revision overwrites the last.
# The same is true of forward EPS, the recommendation key and the
# analyst count.
#
# That data is only observable in passing. If it isn't written down
# as it goes by, it is gone permanently - and a revision trend is
# considerably more informative than any single point on it. A target
# price of $170 says very little; a target price cut from $185 to
# $178 to $170 over three weeks says quite a lot.
#
# So this module records one row per ticker per day, and nothing in
# the app has to change to make that happen.
#
# ----------------------------------------------------------
# HOW IT FILLS UP
# ----------------------------------------------------------
# market_fetcher._build_snapshot() is the single place where every
# market snapshot in this app is constructed, so one call from there
# captures history across every page - the dashboard, Compare, and
# every candidate Discover scores on its way to a ranking. Ordinary
# use of the app populates the table as a side effect.
#
# The 15-minute market cache means a heavily viewed ticker produces
# a handful of writes an hour. The primary key on
# (ticker, snapshot_date) collapses all of them into a single row,
# so the write path stays deliberately dumb: always upsert, never
# check first.
#
# What organic traffic cannot guarantee is coverage on days nobody
# opens the app. A scheduled job over the watchlist closes that gap;
# this module is what that job would call.
#
# ----------------------------------------------------------
# FAILURE POSTURE
# ----------------------------------------------------------
# Recording history is a side effect, never the point of the request
# the user is waiting on. A database that is unreachable, slow to
# resolve, or simply not configured must degrade to exactly the
# behaviour this app had before it existed: show the data, say
# nothing. Every public function here swallows its own errors for
# that reason, and record_snapshot() returns a bool rather than
# raising so a caller can log without having to handle anything.
#
# The one place that silence would be wrong is a scheduled job, where
# a failed write is the whole story - hence the return value, and
# hence the __main__ block below reporting it.

import os
from datetime import date, datetime, timezone

from dotenv import load_dotenv

# Loaded here rather than assumed: the dashboard's own import chain
# never touches storyline_engine/storyline_fetcher, the only other
# modules that call this, so without it INVESTOR_ASSISTANT_DATABASE_URL
# never reaches os.environ and every function below quietly no-ops.
load_dotenv()

# psycopg2 is imported lazily inside the connection helper, for the
# same reason yfinance is elsewhere in this package: the import is not
# free, and an app running without DATABASE_URL set should never pay
# for a dependency it will not use.

PATH_ENV_VAR = "INVESTOR_ASSISTANT_DATABASE_URL"

# Resolved per call rather than at import time so that setting the
# variable after the module loads still takes effect - the same
# reasoning as watchlist.py's path resolution, and what lets tests
# point at a throwaway database.


def _dsn():
    return os.environ.get(PATH_ENV_VAR) or os.environ.get("DATABASE_URL")


def is_configured():
    """True if a connection string is available to be tried."""
    return bool(_dsn())


# Columns written per snapshot. The keys are the column names; the
# values are the keys market_fetcher produces. They mostly match,
# which is the point - _build_snapshot already normalizes yfinance's
# shape into ours, so this module inherits that work instead of
# re-doing it.
_COLUMNS = {
    "price": "price",
    "market_cap": "market_cap",
    "trailing_pe": "trailing_pe",
    "forward_pe": "forward_pe",
    "price_to_sales": "price_to_sales",
    "price_to_book": "price_to_book",
    "dividend_yield": "dividend_yield",
    "beta": "beta",
    "trailing_eps": "trailing_eps",
    "shares_outstanding": "shares_outstanding",
    "range_position": "range_position",
    "target_price": "target_price",
    "forward_eps": "forward_eps",
    "recommendation": "recommendation",
    "num_analysts": "num_analysts",
    "profit_margin": "profit_margin",
}

_ORDERED = list(_COLUMNS.keys())


def _connect():
    dsn = _dsn()

    if not dsn:
        return None

    try:
        import psycopg2  # lazy: see note at top of module

        return psycopg2.connect(dsn, connect_timeout=5)
    except Exception as error:  # noqa: BLE001 - driver raises many shapes
        print(f"Snapshot store unavailable: {error}")
        return None


def _snapshot_date():
    """
    The date a snapshot is filed under.

    UTC rather than local time, so that the same observation lands on
    the same date regardless of where the app is running. A local-date
    convention would file an evening US session and the following
    morning's Asian session under different dates on one machine and
    the same date on another, which quietly corrupts any comparison
    built on top of it.

    This is a filing convention, not a claim about market sessions:
    a row dated 2026-08-13 means "observed on that UTC day", not
    "the close of that trading day".
    """
    return datetime.now(timezone.utc).date()


def record_snapshot(snapshot, on_date=None):
    """
    Write one row for this ticker and day. Returns True on success.

    Repeat calls within the same day overwrite that day's row rather
    than accumulating duplicates, so the caller never has to know
    whether today has already been recorded. The last observation of
    a day wins, which is the useful one - it is the closest to that
    day's settled figure.

    Any field the snapshot lacks is stored as NULL. Missing data is
    normal here for the same reasons it is everywhere else in this
    app: ETFs, ADRs, recent IPOs and lossmaking companies all
    legitimately lack some of these fields.
    """
    if not snapshot:
        return False

    ticker = snapshot.get("ticker")

    if not ticker:
        return False

    connection = _connect()

    if connection is None:
        return False

    columns = ["ticker", "snapshot_date"] + _ORDERED
    values = [ticker.upper(), on_date or _snapshot_date()] + [
        snapshot.get(source) for source in _COLUMNS.values()
    ]

    placeholders = ", ".join(["%s"] * len(columns))
    updates = ", ".join(f"{column} = EXCLUDED.{column}" for column in _ORDERED)

    statement = (
        f"INSERT INTO market_snapshot ({', '.join(columns)}) "
        f"VALUES ({placeholders}) "
        f"ON CONFLICT (ticker, snapshot_date) DO UPDATE SET {updates}"
    )

    try:
        with connection, connection.cursor() as cursor:
            cursor.execute(statement, values)
        return True
    except Exception as error:  # noqa: BLE001
        print(f"Snapshot write failed for {ticker.upper()}: {error}")
        return False
    finally:
        try:
            connection.close()
        except Exception:  # noqa: BLE001
            pass


def fetch_history(ticker, limit=52):
    """
    Return this ticker's stored snapshots, newest first.

    Rows come back as plain dicts so that analytics/ can work on them
    without importing a database driver - the same reason the fetchers
    hand back dicts rather than DataFrames.

    Returns [] when the store is unreachable or has never seen this
    ticker. Callers should treat both the same way: with no history
    there is nothing to say about change, which is the correct thing
    to say rather than an error to report.
    """
    if not ticker or not ticker.strip():
        return []

    connection = _connect()

    if connection is None:
        return []

    columns = ["snapshot_date"] + _ORDERED

    statement = (
        f"SELECT {', '.join(columns)} FROM market_snapshot "
        f"WHERE ticker = %s ORDER BY snapshot_date DESC LIMIT %s"
    )

    try:
        with connection, connection.cursor() as cursor:
            cursor.execute(statement, (ticker.upper(), limit))
            rows = cursor.fetchall()
    except Exception as error:  # noqa: BLE001
        print(f"Snapshot read failed for {ticker.upper()}: {error}")
        return []
    finally:
        try:
            connection.close()
        except Exception:  # noqa: BLE001
            pass

    history = []

    for row in rows:
        record = dict(zip(columns, row))

        # psycopg2 returns NUMERIC as Decimal, which does not mix with
        # the floats the rest of the app computes on. Converting here
        # keeps that detail from leaking into analytics/.
        for key, value in record.items():
            if key in ("snapshot_date", "recommendation"):
                continue
            record[key] = float(value) if value is not None else None

        history.append(record)

    return history


def record_many(snapshots, on_date=None):
    """
    Write several snapshots, returning how many succeeded.

    Written for the scheduled job that keeps watchlist tickers covered
    on days nobody opens the app. One failure does not abort the rest:
    a single delisted or rate-limited ticker should cost one row, not
    the whole day's coverage.
    """
    written = 0

    for snapshot in snapshots:
        if record_snapshot(snapshot, on_date=on_date):
            written += 1

    return written


if __name__ == "__main__":
    from market_fetcher import fetch_market_snapshot

    if not is_configured():
        raise SystemExit(f"Set {PATH_ENV_VAR} first.")

    for symbol in ("AAPL", "MSFT", "NVDA"):
        ok = record_snapshot(fetch_market_snapshot(symbol))
        print(f"{symbol}: {'written' if ok else 'FAILED'}")

    for row in fetch_history("AAPL", limit=5):
        print(row["snapshot_date"], row["price"], row["target_price"])