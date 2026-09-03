"""Spike 6: is the traffic measurement actually measuring traffic?

Independent check - the race leader runs in clean air, backmarkers do not. If
`frac_near` is real, it should rise as we move down the running order. Nothing in the
traffic computation ever sees finishing position, so this is a genuine falsification
test rather than a restatement.

Run: python scripts/spike_06_traffic_validate.py
"""
import sys, os, warnings
warnings.filterwarnings("ignore")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import numpy as np
import pandas as pd
from pitwall.data import SessionRef, load_session, clean_laps
from pitwall.track import build_centreline
from pitwall.traffic import lap_traffic_features, attach_traffic

pd.set_option("display.width", 220)

s = load_session(SessionRef(2026, "Hungary", "R"), telemetry=True)
cl = build_centreline(s)
tf = lap_traffic_features(s, cl)
laps = attach_traffic(clean_laps(s), tf)
laps = laps.loc[laps["traffic_observed"]]

res = s.results[["Abbreviation", "Position"]].rename(
    columns={"Abbreviation": "Driver", "Position": "FinishPos"})
laps = laps.merge(res, on="Driver", how="left")

print("traffic exposure by finishing position (race):")
by = (laps.groupby(["FinishPos", "Driver"])
      .agg(laps=("LapTimeS", "size"),
           frac_near=("frac_near", "mean"),
           frac_close=("frac_close", "mean"),
           gap_med_s=("gap_med_s", "median"))
      .reset_index().sort_values("FinishPos"))
print(by.round(3).to_string(index=False))

r = laps.groupby("Driver")[["frac_near", "FinishPos"]].mean().dropna()
print(f"\nSpearman(frac_near, finishing position) = "
      f"{r['frac_near'].corr(r['FinishPos'], method='spearman'):+.3f}")
print("  (expect clearly positive: further back = more traffic)")

# in-race position is also available per lap, which is a tighter test
laps["PosBand"] = pd.cut(laps["Position"], [0, 3, 6, 10, 15, 21],
                         labels=["P1-3", "P4-6", "P7-10", "P11-15", "P16-20"])
print("\nby live track position:")
print(laps.groupby("PosBand", observed=True)[["frac_near", "frac_close", "gap_med_s"]]
      .mean().round(3).to_string())
