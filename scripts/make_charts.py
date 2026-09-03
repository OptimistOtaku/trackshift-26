"""Generate every figure used in the deck.

Run: python scripts/make_charts.py [year]
"""
import os
import sys
import warnings

warnings.filterwarnings("ignore")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import numpy as np
import pandas as pd
from pitwall import plots
from pitwall.degradation import fit_practice, fit_race
from pitwall.stopvalue import FULL, ablation, age_test, loo_evaluate, stop_table

YEAR = int(sys.argv[1]) if len(sys.argv) > 1 else 2026
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ART = os.path.join(ROOT, "artifacts")
os.makedirs(ART, exist_ok=True)


def p(name: str) -> str:
    return os.path.join(ART, name)


season = pd.read_parquet(os.path.join(ROOT, "data", f"season_{YEAR}.parquet"))
prac = season.loc[~season["IsRace"]]
fr = fit_race(season)
print(f"lambda = {fr.lambda_fuel:+.4f} s/kg")

# ---- 1. the ladder ---------------------------------------------------- #
rows, fits = [], {}
for label, kw in (("naive", dict(correct_fuel=False, use_traffic=False, use_evo=False)),
                  ("+ fuel", dict(correct_fuel=True, use_traffic=False, use_evo=False)),
                  ("+ traffic", dict(correct_fuel=True, use_traffic=True, use_evo=False)),
                  ("+ rubber", dict(correct_fuel=True, use_traffic=True, use_evo=True))):
    f = fit_practice(prac, lambda_fuel=fr.lambda_fuel, **kw)
    fits[label] = f
    rows.append({"spec": label, **{f"{c}_deg10": f.deg_rate(c, 10) for c in f.compounds}})
ladder = pd.DataFrame(rows)
print(plots.fig_ladder(ladder, p("fig1_ladder.png")))

# ---- 2. why rubber is identified -------------------------------------- #
g = []
for (ses, rid), x in season.groupby(["Session", "RunId"]):
    if len(x) >= 5:
        x = x.sort_values("LapNumber")
        g.append({"Session": ses, "slope": np.polyfit(np.arange(len(x)), x["TrackEvo"], 1)[0]})
evo = pd.DataFrame(g).groupby("Session")["slope"].median().reset_index(name="median")
evo["order"] = evo["Session"].map(
    {"Practice 1": 0, "Practice 2": 1, "Practice 3": 2, "Race": 3}).fillna(9)
print(plots.fig_identification(evo, p("fig2_identification.png")))

# ---- 3. the age null: the figure the project turns on ----------------- #
stops = stop_table(season)
at = age_test(stops)
print(plots.fig_age_null(stops, at, p("fig3_age_null.png")))
print(f"  linear p={at['lin_p']:.3f} (finds nothing); quadratic joint p={at['joint_p']:.3f}, "
      f"peak at age {at['peak_age']:.0f}")

# ---- 4. the practice curve does not transfer -------------------------- #
pw = fit_practice(prac, lambda_fuel=fr.lambda_fuel)
pred = np.zeros(len(stops))
for c in pw.compounds:
    for col, age, sign in (("c_old", "age_old", 1.0), ("c_new", "age_new", -1.0)):
        m = (stops[col] == c).to_numpy()
        if m.any():
            pred[m] += sign * pw.curve(c, stops.loc[m, age].to_numpy(float), clip=True)
pred = pred + fr.lambda_fuel * stops["d_fuel"].to_numpy(float)
obs = stops["step_obs"].to_numpy(float)
pc, oc = pred - pred.mean(), obs - obs.mean()
calib = float(pc @ oc / (pc @ pc))
print(plots.fig_transfer_failure(stops, pred, calib, p("fig4_transfer_failure.png")))
print(f"  calibration slope = {calib:+.4f}")

# ---- 5. what does predict it ----------------------------------------- #
ab = ablation(stops)
print(plots.fig_ablation(ab, p("fig5_ablation.png")))
pe = loo_evaluate(stops, FULL)["per_event"].merge(
    loo_evaluate(stops, [])["per_event"], on="round", suffixes=("_pitwall", "_mean"))
pe["pitwall_wins"] = pe["rmse_s_pitwall"] < pe["rmse_s_mean"]
print(plots.fig_per_event(pe, p("fig6_per_event.png")))

# ---- 6. traffic falsification ---------------------------------------- #
r = season.loc[season["IsRace"] & season["traffic_observed"]].copy()
r["PosBand"] = pd.cut(r["Position"], [0, 3, 6, 10, 15, 21],
                      labels=["P1-3", "P4-6", "P7-10", "P11-15", "P16-20"])
by = r.groupby("PosBand", observed=True)[["frac_near", "frac_close"]].mean()
print(plots.fig_traffic_validation(by, p("fig7_traffic.png")))

# ---- 7. the deconfounded curves themselves --------------------------- #
print(plots.fig_curves(pw, p("fig8_curves.png"),
                       title="Deconfounded practice degradation — defensible in sample, "
                             "does not transfer"))
print(f"\nfigures in {ART}")
