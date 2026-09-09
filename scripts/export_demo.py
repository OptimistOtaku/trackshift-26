"""Emit the static JSON the demo runs on. No server at demo time, nothing to go wrong on stage.

Writes artifacts/demo/ per docs/DEMO_CONTRACT.md: an index with the headline numbers, the
fitted coefficients so the UI can compute undercuts client-side, and one file per race for the
replay scrubber.

The coefficients are exported rather than the predictions because the hero feature is
interactive - the user moves a gap or a tyre age and the answer changes. Shipping predictions
would mean a round trip we do not have, or a pre-computed grid we would have to guess the
extent of.

Run: python scripts/export_demo.py
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from pitwall import strategy as S                                  # noqa: E402
from pitwall.stopvalue import loo_evaluate, stop_table             # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ART = os.path.join(ROOT, "artifacts")
OUT = os.path.join(ART, "demo")

# Columns the replay needs. Kept explicit: dumping every column would put the fitted
# RunPaceRef and TrackEvo in the UI's hands, and those are model internals, not observations.
LAP_COLS = ["lap", "driver", "lap_time_s", "compound", "tyre_age", "position",
            "fuel_kg", "frac_close"]


def _round_floats(o, nd: int = 4):
    """Trim float noise so the JSON is readable and small. 4dp is 0.1 ms on a lap time."""
    if isinstance(o, float):
        return None if not np.isfinite(o) else round(o, nd)
    if isinstance(o, dict):
        return {k: _round_floats(v, nd) for k, v in o.items()}
    if isinstance(o, list):
        return [_round_floats(v, nd) for v in o]
    if isinstance(o, (np.floating,)):
        return _round_floats(float(o), nd)
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    return o


def model_json(model, deg: S.Degradation) -> dict:
    """Fitted coefficients, in the form the JS in DEMO_CONTRACT.md expects."""
    p = model.res.params
    pairs = {model.pairs[0]: 0.0}                 # the dropped reference pair
    for name in p.index:
        if name.startswith("p[") and name.endswith("]"):
            pairs[name[2:-1]] = float(p[name])
    return {
        "spec": list(model.spec),
        "intercept": float(p.get("const", 0.0)),
        "tt_mean": float(model.tt_mean),
        "tt_coef": float(p.get("tt_c", 0.0)),
        "traf_coef": float(p.get("d_close", 0.0)),
        "pairs": pairs,
        "reference_pair": model.pairs[0],
        "degradation": {
            "b1": deg.b1, "b2": deg.b2,
            "peak_age": deg.peak, "max_age_seen": deg.max_age_seen,
            "note": ("phi(a) = b1*a + b2*a^2, HELD FLAT past peak_age. Never let it decline - "
                     "a declining phi claims tyres get faster as they wear, which is the sign "
                     "error this project exists to point at."),
        },
        "fresh_age": S.FRESH_AGE,
        "n_obs": int(model.n_obs),
    }


def race_json(season: pd.DataFrame, stops: pd.DataFrame, model, rnd: int,
              pit_loss: float) -> dict:
    race = season.loc[season["IsRace"] & (season["Round"] == rnd)]
    d = race.rename(columns={"LapNumber": "lap", "Driver": "driver", "LapTimeS": "lap_time_s",
                             "Compound": "compound", "TyreAge": "tyre_age",
                             "Position": "position", "FuelKg": "fuel_kg"})
    d = d.reindex(columns=LAP_COLS)
    d = d.dropna(subset=["lap", "driver", "lap_time_s"]).sort_values(["lap", "driver"])
    for c in ("lap", "tyre_age", "position"):
        d[c] = pd.to_numeric(d[c], errors="coerce")

    st = stops.loc[stops["Round"] == rnd].copy()
    if not st.empty:
        st["step_pred_s"] = model.predict(st)
    sj = [{"driver": str(r["Driver"]), "pit_lap": int(r["PitLap"]), "pair": str(r["pair"]),
           "age_old": float(r["age_old"]), "step_obs_s": float(r["step_obs"]),
           "step_pred_s": float(r["step_pred_s"])} for _, r in st.iterrows()]

    ev = str(race["Event"].iloc[0])
    return {
        "round": int(rnd), "event": ev, "laps": int(d["lap"].max()),
        "pit_loss_s": float(pit_loss), "track_temp_c": float(race["TrackTemp"].mean()),
        "drivers": sorted(d["driver"].astype(str).unique().tolist()),
        "laps_data": d.to_dict(orient="records"),
        "stops": sj,
    }


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    season = pd.read_parquet(os.path.join(ROOT, "data", "season_2026.parquet"))
    stops = stop_table(season)
    loss = pd.read_csv(os.path.join(ART, "pitloss_2026.csv"))
    pit_loss = dict(zip(loss["Round"].astype(int), loss["median"].astype(float)))

    deg = S.fit_degradation(stops)
    model = S.fit_level_model(stops)
    ev = loo_evaluate(stops, S.LEVEL_SPEC)

    with open(os.path.join(OUT, "model.json"), "w", encoding="utf-8") as f:
        json.dump(_round_floats(model_json(model, deg), 6), f, indent=2)

    races, race_meta = [], []
    for rnd in sorted(stops["Round"].unique()):
        rnd = int(rnd)
        if rnd not in pit_loss:
            print(f"[R{rnd:02d}] skipped: no measured pit loss")
            continue
        rj = race_json(season, stops, model, rnd, pit_loss[rnd])
        name = f"R{rnd:02d}.json"
        os.makedirs(os.path.join(OUT, "races"), exist_ok=True)
        with open(os.path.join(OUT, "races", name), "w", encoding="utf-8") as f:
            json.dump(_round_floats(rj), f, separators=(",", ":"))
        races.append(rj)
        race_meta.append({"round": rnd, "event": rj["event"], "laps": rj["laps"],
                          "file": f"races/{name}", "pit_loss_s": rj["pit_loss_s"],
                          "track_temp_c": rj["track_temp_c"], "stops": len(rj["stops"])})
        print(f"[R{rnd:02d}] {rj['event'][:26]:26s} laps={rj['laps']:3d} "
              f"rows={len(rj['laps_data']):5d} stops={len(rj['stops']):3d}")

    base = float(ev["rmse_s"]) / (1.0 - 0.119) if ev.get("rmse_s") else None
    index = {
        "season": int(season["Year"].iloc[0]),
        "generated": pd.Timestamp.now().strftime("%Y-%m-%d"),
        "headline": {
            "stops": int(len(stops)), "events": int(stops["Round"].nunique()),
            "rmse_s": float(ev["rmse_s"]), "calib_slope": float(ev["calib_slope"]),
            "mae_s": float(ev["mae_s"]), "bias_s": float(ev["bias_s"]),
            "n_scored": int(ev["n"]), "events_scored": int(ev["events"]),
        },
        "pit_loss": {
            "season_median_s": float(loss["season_median"].iloc[0]),
            "min_s": float(loss["median"].min()), "max_s": float(loss["median"].max()),
        },
        "window_is_not_reported": (
            "A pit-lap recommendation is deliberately absent. It covers 66.9% of real stops "
            "but a width-matched mid-race window covers 66.2%, so it adds nothing over 'pit "
            "halfway through'. See scripts/check_window_placebo.py."),
        "races": race_meta,
    }
    with open(os.path.join(OUT, "index.json"), "w", encoding="utf-8") as f:
        json.dump(_round_floats(index, 6), f, indent=2)

    total = sum(os.path.getsize(os.path.join(dp, fn))
                for dp, _, fns in os.walk(OUT) for fn in fns)
    print(f"\nwrote {len(race_meta)} races to {os.path.relpath(OUT, ROOT)}  "
          f"({total / 1e6:.1f} MB total)")
    print(f"headline: RMSE {ev['rmse_s']:.3f} s/lap, calib {ev['calib_slope']:.2f}, "
          f"{len(stops)} stops")


if __name__ == "__main__":
    main()
