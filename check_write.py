from dotenv import load_dotenv
load_dotenv()

import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from data.market_fetcher import fetch_market_snapshot
from data.snapshot_store import record_snapshot, is_configured

print("configured:", is_configured())

snap = fetch_market_snapshot("AAPL")
print("fetched keys:", sorted(snap.keys()))
print("target_price:", snap.get("target_price"))
print("recommendation:", snap.get("recommendation"))

ok = record_snapshot(snap)
print("write result:", ok)