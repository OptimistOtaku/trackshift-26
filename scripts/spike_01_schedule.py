"""Spike 1: what does FastF1 actually give us for the 2026 season?

Run: python scripts/spike_01_schedule.py
"""
import sys, os, warnings
warnings.filterwarnings("ignore")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import fastf1
import pandas as pd

CACHE = os.path.join(os.path.dirname(__file__), "..", "data", "cache")
os.makedirs(CACHE, exist_ok=True)
fastf1.Cache.enable_cache(CACHE)

pd.set_option("display.width", 200)
pd.set_option("display.max_columns", 50)

for year in (2026, 2025):
    print("=" * 72)
    print(f"SEASON {year}")
    try:
        sched = fastf1.get_event_schedule(year, include_testing=False)
    except Exception as e:
        print(f"  schedule FAILED: {type(e).__name__}: {e}")
        continue
    cols = [c for c in ["RoundNumber", "EventName", "Location", "EventDate",
                        "EventFormat", "Session1", "Session1DateUtc",
                        "Session5", "Session5DateUtc"] if c in sched.columns]
    print(sched[cols].to_string(index=False))
