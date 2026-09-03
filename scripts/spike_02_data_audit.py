"""Spike 2: data quality audit on a real 2026 conventional weekend.

Checks the exact fields the Tyre Degradation problem needs:
  - stint / compound / tyre-life bookkeeping
  - lap accuracy flags and track status
  - weather channels (track evolution proxy)
  - what we can use as a traffic proxy

Run: python scripts/spike_02_data_audit.py
"""
import sys, os, warnings
warnings.filterwarnings("ignore")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import fastf1
import pandas as pd
import numpy as np

CACHE = os.path.join(os.path.dirname(__file__), "..", "data", "cache")
os.makedirs(CACHE, exist_ok=True)
fastf1.Cache.enable_cache(CACHE)

pd.set_option("display.width", 250)
pd.set_option("display.max_columns", 60)

YEAR, GP = 2026, "Hungary"


def audit(session_code):
    print("=" * 78)
    print(f"{YEAR} {GP} — {session_code}")
    print("=" * 78)
    try:
        s = fastf1.get_session(YEAR, GP, session_code)
        s.load(laps=True, telemetry=False, weather=True, messages=True)
    except Exception as e:
        print(f"  LOAD FAILED: {type(e).__name__}: {e}")
        return None

    laps = s.laps
    print(f"laps shape: {laps.shape}")
    print(f"drivers: {laps['Driver'].nunique()}")
    print("\ncolumns:")
    print(sorted(laps.columns.tolist()))

    key = ["Driver", "LapNumber", "LapTime", "Stint", "Compound", "TyreLife",
           "FreshTyre", "TrackStatus", "IsAccurate", "Position", "PitInTime",
           "PitOutTime", "LapStartTime", "Sector1Time"]
    key = [c for c in key if c in laps.columns]
    print("\nnull % on key fields:")
    print((laps[key].isna().mean() * 100).round(1).to_string())

    if "Compound" in laps:
        print("\ncompound counts:")
        print(laps["Compound"].value_counts(dropna=False).to_string())
    if "IsAccurate" in laps:
        print(f"\nIsAccurate True: {int(laps['IsAccurate'].sum())} / {len(laps)}")
    if "TyreLife" in laps:
        tl = laps["TyreLife"].dropna()
        if len(tl):
            print(f"TyreLife range: {tl.min():.0f} .. {tl.max():.0f}")

    # sample of one driver's stint bookkeeping
    if len(laps):
        d = laps["Driver"].value_counts().index[0]
        sub = laps.pick_drivers(d)[key].head(18)
        print(f"\nsample laps for {d}:")
        print(sub.to_string(index=False))

    # weather
    try:
        w = s.weather_data
        print(f"\nweather shape: {w.shape}  cols: {w.columns.tolist()}")
        print(w.describe().loc[["min", "mean", "max"]].round(2).to_string())
    except Exception as e:
        print(f"\nweather unavailable: {e}")

    return s


fp2 = audit("FP2")
race = audit("R")
