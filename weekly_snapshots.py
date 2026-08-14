# ==========================================================
# WEEKLY SNAPSHOT JOB
# ==========================================================
# Guarantees the history the app cannot guarantee for itself.
#
# ----------------------------------------------------------
# WHY A JOB AT ALL
# ----------------------------------------------------------
# market_fetcher already records a snapshot whenever it fetches
# fresh data, so ordinary use of the app fills the table. That is
# enough to be useful and not enough to be trustworthy: it only
# covers tickers somebody happened to look up, on days somebody
# happened to be looking. A revision series with holes in it is
# worse than no series, because the gaps are invisible once the
# rows are in the table - a target price that appears to have moved
# once in a month may simply be two observations three weeks apart.
#
# This job makes coverage a property of the schedule rather than of
# traffic. Run it weekly and every ticker in the universe has a row
# every week, whether anyone opened the app or not.
#
# ----------------------------------------------------------
# WHY THIS UNIVERSE
# ----------------------------------------------------------
# The obvious candidate was the watchlist, and it is the wrong one:
# data/watchlist.json is gitignored local state, so a CI runner has
# no watchlist to read. CURATED_UNIVERSE is committed, deliberately
# spread across sectors and risk tiers, and is already the pool
# Discover ranks - so recording it also warms the exact data the
# slowest page in the app needs.
#
# ----------------------------------------------------------
# WHY THIS ONE FAILS LOUDLY
# ----------------------------------------------------------
# Everything in snapshot_store is silent by design, because there a
# failed write costs a user nothing. Here it costs a week of history
# that cannot be backfilled, and nobody is watching the logs. So this
# script exits non-zero when the run is materially incomplete, which
# is what turns a silent data gap into a red mark in the Actions tab.

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analytics.discover_engine import CURATED_UNIVERSE
from data.market_fetcher import fetch_market_snapshot
from data.snapshot_store import is_configured, record_snapshot

# yfinance is an unofficial API with undocumented rate limits, and
# roughly 290 sequential calls is enough to find them. A small pause
# costs a few minutes of runner time - which is free and unattended -
# and buys a far better chance of a complete run.
DELAY_SECONDS = 0.7

# Some failures are normal: symbols get delisted, acquired, or renamed,
# and CURATED_UNIVERSE is hand-maintained so it drifts. A handful of
# misses is drift; a large fraction is a broken run worth alerting on.
FAILURE_THRESHOLD = 0.15


def universe():
    """Every ticker in the curated pool, deduplicated and sorted.

    A ticker can appear in more than one sector/tier cell. Recording
    it once per appearance would be wasted calls against the same
    row, since the upsert collapses them anyway.
    """
    tickers = set()

    for tiers in CURATED_UNIVERSE.values():
        for candidates in tiers.values():
            tickers.update(candidates)

    return sorted(tickers)


def main():
    if not is_configured():
        print("No database configured - set INVESTOR_ASSISTANT_DATABASE_URL")
        return 1

    tickers = universe()
    print(f"Recording {len(tickers)} tickers")

    written = 0
    failed = []

    for index, ticker in enumerate(tickers, start=1):
        try:
            snapshot = fetch_market_snapshot(ticker)
        except Exception as error:  # noqa: BLE001
            snapshot = None
            print(f"  {ticker}: fetch raised {error}")

        # fetch_market_snapshot already writes on a cache miss, but a
        # runner starts with an empty cache every time, so in practice
        # this call is what records the row. Calling record_snapshot
        # explicitly keeps the job correct even if that changes - the
        # upsert makes a duplicate write harmless.
        if snapshot and record_snapshot(snapshot):
            written += 1
        else:
            failed.append(ticker)

        if index % 25 == 0:
            print(f"  {index}/{len(tickers)} - {written} written")

        time.sleep(DELAY_SECONDS)

    print(f"\nWrote {written}/{len(tickers)} rows")

    if failed:
        print(f"Failed: {', '.join(failed)}")

    failure_rate = len(failed) / len(tickers)

    if failure_rate > FAILURE_THRESHOLD:
        print(f"Failure rate {failure_rate:.0%} exceeds threshold")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())