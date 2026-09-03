"""Spike 5: does measured traffic look like real F1 traffic?

Sanity checks:
  - centreline length should match the known circuit length
  - race gaps should be much tighter than practice gaps
  - laps flagged as close-following should be slower than clean-air laps

Run: python scripts/spike_05_traffic.py
"""
import sys, os, time, warnings
warnings.filterwarnings("ignore")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import numpy as np
import pandas as pd
from pitwall.data import SessionRef, load_session, clean_laps
from pitwall.track import build_centreline
from pitwall.traffic import lap_traffic_features, attach_traffic

pd.set_option("display.width", 220)

for ses in ("FP2", "R"):
    print("=" * 78)
    ref = SessionRef(2026, "Hungary", ses)
    t0 = time.time()
    s = load_session(ref, telemetry=True)
    cl = build_centreline(s)
    print(f"{ref}: centreline length = {cl.length:.0f} m "
          f"(Hungaroring is ~4381 m), points={len(cl.s)}")

    tf = lap_traffic_features(s, cl)
    print(f"traffic rows: {len(tf)}  ({time.time()-t0:.0f}s total)")
    if tf.empty:
        continue
    print(tf[["gap_min_s", "gap_med_s", "frac_close", "frac_near"]]
          .describe().round(3).to_string())

    laps = clean_laps(s)
    laps = attach_traffic(laps, tf)
    print(f"\ncleaned laps with traffic: {len(laps)}, "
          f"gap_min_s null={laps['gap_min_s'].isna().sum()}")

    # does traffic actually cost lap time? compare within compound+driver
    laps["clean_air"] = laps["frac_near"] < 0.10
    laps["dirty_air"] = laps["frac_close"] > 0.50
    g = laps.groupby("clean_air")["LapTimeS"].agg(["size", "median"]).round(3)
    print("\nlap time by clean_air flag:")
    print(g.to_string())
    if laps["dirty_air"].any():
        print(f"\nmedian lap, >50% of lap within 1.0s of car ahead: "
              f"{laps.loc[laps['dirty_air'], 'LapTimeS'].median():.3f}")
        print(f"median lap, clean air:                            "
              f"{laps.loc[laps['clean_air'], 'LapTimeS'].median():.3f}")
