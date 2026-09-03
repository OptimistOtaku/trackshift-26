"""Spike 3: can we detect traffic in a practice session?

Position is 100% NaN in FP, so we need another route. Two candidates:
  A) sector session-times  -> cheap, lap-data only, ~3 track-position samples/lap
  B) session.pos_data      -> accurate XY at ~10Hz, but heavy download

This measures cost and coverage of both.

Run: python scripts/spike_03_traffic.py
"""
import sys, os, time, warnings
warnings.filterwarnings("ignore")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import fastf1
import pandas as pd
import numpy as np

CACHE = os.path.join(os.path.dirname(__file__), "..", "data", "cache")
fastf1.Cache.enable_cache(CACHE)
pd.set_option("display.width", 250)

YEAR, GP, SES = 2026, "Hungary", "FP2"

# ---------- A) sector session times (no telemetry) ----------
t0 = time.time()
s = fastf1.get_session(YEAR, GP, SES)
s.load(laps=True, telemetry=False, weather=False, messages=False)
print(f"[A] laps-only load: {time.time()-t0:.1f}s")

laps = s.laps
sec = ["Sector1SessionTime", "Sector2SessionTime", "Sector3SessionTime"]
print("[A] sector session-time null %:")
print((laps[sec].isna().mean() * 100).round(1).to_string())
print(f"[A] laps with all 3 sector stamps: "
      f"{int(laps[sec].notna().all(axis=1).sum())} / {len(laps)}")

# ---------- B) position data ----------
t0 = time.time()
ok = False
try:
    s2 = fastf1.get_session(YEAR, GP, SES)
    s2.load(laps=True, telemetry=True, weather=False, messages=False)
    pos = s2.pos_data
    dt = time.time() - t0
    ok = True
    print(f"\n[B] telemetry load: {dt:.1f}s")
    print(f"[B] pos_data cars: {len(pos)}")
    k = list(pos.keys())[0]
    df = pos[k]
    print(f"[B] sample car {k}: shape={df.shape} cols={df.columns.tolist()}")
    print(df.head(3).to_string(index=False))
    rows = sum(len(v) for v in pos.values())
    print(f"[B] total position rows: {rows:,}")
    span = df["SessionTime"].max() - df["SessionTime"].min()
    print(f"[B] sample rate: ~{len(df)/span.total_seconds():.1f} Hz over {span}")
except Exception as e:
    print(f"\n[B] FAILED after {time.time()-t0:.1f}s: {type(e).__name__}: {e}")

print(f"\nVERDICT: sector-stamp route usable = "
      f"{bool(laps[sec].notna().all(axis=1).mean() > 0.7)}; pos_data usable = {ok}")
