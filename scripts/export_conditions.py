"""Enrich unfiltered replay from offline sensors; use pre-race track geometry.

Run before build_intelligence.py when refreshing source inputs. No fit-cleaned
table is joined, so feature availability cannot leak a later lap's quality.
"""
from pathlib import Path
import argparse
import json
import sys
import numpy as np
import pandas as pd
import fastf1

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from pitwall.conditions import weather_at
from pitwall.track import build_centreline
from pitwall.traffic import lap_traffic_features
from benchmark_intelligence import write_json


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rounds", nargs="*", type=int)
    args = parser.parse_args()
    fastf1.set_log_level("ERROR")
    fastf1.Cache.enable_cache(str(ROOT / "data/cache"))
    fastf1.Cache.offline_mode(True)
    for path in sorted((ROOT / "artifacts/demo/replay").glob("R*.json")):
        replay = json.loads(path.read_text())
        if args.rounds and replay["round"] not in args.rounds:
            continue
        print(f"R{replay['round']:02d}: loading cached weather and positions", flush=True)
        # Do not call load_session: it re-enables the cache, resetting offline mode.
        cl, geometry_session = None, None
        for session_name in ("FP1", "FP2", "FP3", "Q"):
            try:
                practice = fastf1.get_session(2026, replay["event"], session_name)
                practice.load(laps=True, telemetry=True, weather=False, messages=False)
                cl = build_centreline(practice, resample_m=3., n_candidates=25)
                geometry_session = session_name
                break
            except (RuntimeError, ValueError, OSError, fastf1.exceptions.DataNotLoadedError) as exc:
                print(f"  {session_name} geometry unavailable: {exc}", flush=True)
        session = fastf1.get_session(2026, replay["event"], "R")
        session.load(laps=True, telemetry=True, weather=True, messages=False)
        traffic = lap_traffic_features(session, cl, causal=True) if cl is not None else pd.DataFrame()
        lookup = {(r.Driver, int(r.LapNumber)): r._asdict() for r in traffic.itertuples()}
        laps = {(r.Driver, int(r.LapNumber)): r for r in session.laps.itertuples()
                if pd.notna(r.LapNumber)}
        for row in replay["laps_data"]:
            raw = laps.get((row["driver"], row["lap"]))
            end = raw.Time.total_seconds() if raw is not None and pd.notna(raw.Time) else np.nan
            row.update(weather_at(session.weather_data, end))
            row["completed_s"] = end
            measured = lookup.get((row["driver"], row["lap"]), {})
            for key in ("frac_close", "frac_near", "gap_med_s", "gap_min_s", "traffic_coverage"):
                row[key] = measured.get(key)
            row["traffic_observed"] = bool(measured.get("traffic_observed", False))
        xy = cl.xy[::max(1, len(cl.xy)//350)] if cl is not None else []
        replay["circuit"] = (dict(xy=xy.tolist(), length_m=cl.length, xy_unit="decimetres",
            source=f"{geometry_session} position telemetry; validated pre-race reference line")
            if cl is not None else None)
        replay["conditions_basis"] = dict(weather="Latest sensor at or before lap completion; maximum age 180 s",
            traffic="Past-position sample-and-hold on validated pre-race geometry; metric 20 m off-line gate; at least 50% lap coverage",
            missing="Null means unavailable, not zero. No carcass temperature or pressure feed.",
            animation="Schematic motion on measured geometry; not continuous live GPS")
        write_json(path, replay)
        print(f"R{replay['round']:02d}: {len(lookup)} traffic laps; geometry {len(xy)} points", flush=True)


if __name__ == "__main__":
    main()
