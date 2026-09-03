"""Spike 4: does the lap cleaner produce sane runs?

Run: python scripts/spike_04_clean.py
"""
import sys, os, warnings
warnings.filterwarnings("ignore")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pandas as pd
from pitwall.data import SessionRef, load_session, clean_laps, summarise

pd.set_option("display.width", 220)
pd.set_option("display.max_rows", 200)

for ses in ("FP2", "FP3", "R"):
    ref = SessionRef(2026, "Hungary", ses)
    s = load_session(ref)
    laps = clean_laps(s)
    print("=" * 78)
    print(f"{ref}  raw={len(s.laps)}  kept={len(laps)}  runs={laps['RunId'].nunique() if len(laps) else 0}")
    if laps.empty:
        continue
    print(f"compounds: {laps['Compound'].value_counts().to_dict()}")
    print(f"lap time range: {laps['LapTimeS'].min():.3f} .. {laps['LapTimeS'].max():.3f}")
    print(f"TrackTemp: {laps['TrackTemp'].min():.1f} .. {laps['TrackTemp'].max():.1f}")
    sm = summarise(laps)
    print(f"\nruns (n={len(sm)}), showing up to 25:")
    print(sm.head(25).to_string(index=False))
    # how many runs start on used rubber? this is our practice identification lever
    used = sm[~sm["fresh"].astype(bool)]
    print(f"\nruns starting on USED tyres: {len(used)} / {len(sm)}")
    if len(used):
        print(used[["Driver", "Compound", "age_start", "age_end", "laps_kept"]].head(12).to_string(index=False))
