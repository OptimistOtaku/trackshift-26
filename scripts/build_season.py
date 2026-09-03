"""Build the whole season's cleaned lap tables into data/frames/.

Slow on first run (position telemetry for ~40 sessions); instant afterwards.

Run: python scripts/build_season.py [year]
"""
import os
import sys
import warnings

warnings.filterwarnings("ignore")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pandas as pd
from pitwall.pipeline import build_season

YEAR = int(sys.argv[1]) if len(sys.argv) > 1 else 2026

season = build_season(YEAR)
print("\n" + "=" * 70)
print(f"season {YEAR}: {len(season)} laps, {season['RunId'].nunique()} runs, "
      f"{season['Round'].nunique()} events")
print(season.groupby("IsRace")["LapTimeS"].agg(["size", "median"]).round(2).to_string())
print("\nlaps per compound:")
print(season.groupby(["IsRace", "Compound"]).size().to_string())

out = os.path.join(os.path.dirname(__file__), "..", "data", f"season_{YEAR}.parquet")
season.to_parquet(os.path.abspath(out), index=False)
print(f"\nwrote {os.path.abspath(out)}")
