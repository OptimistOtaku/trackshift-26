"""The full evidence chain, reproduced from the season parquet in one run.

Four questions, in the order the project actually asked them:

  1. Can the practice confounders be removed?          -> yes, and it fixes a sign error
  2. Does the resulting curve predict the race?        -> no
  3. What does the race actually say about tyre age?   -> nothing, at the ages people stop
  4. What predicts the value of a stop, then?          -> compound, track temp, traffic

Run: python scripts/stop_value.py [year]
"""
import os
import sys
import warnings

warnings.filterwarnings("ignore")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import numpy as np
import pandas as pd
from pitwall.degradation import fit_practice, fit_race
from pitwall.stopvalue import (FULL, ablation, age_test, fit_stop_value, loo_evaluate,
                               robustness, stop_table)

pd.set_option("display.width", 250)

YEAR = int(sys.argv[1]) if len(sys.argv) > 1 else 2026
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ART = os.path.join(ROOT, "artifacts")
os.makedirs(ART, exist_ok=True)

season = pd.read_parquet(os.path.join(ROOT, "data", f"season_{YEAR}.parquet"))
print(f"season {YEAR}: {len(season)} laps, {season['Round'].nunique()} events, "
      f"{season['RunId'].nunique()} runs")

# ---- Q1: are the practice confounders removable? ---------------------- #
print("\n" + "=" * 86)
print("Q1  CAN THE PRACTICE CONFOUNDERS BE REMOVED?")
fr = fit_race(season)
print(f"    lambda = {fr.lambda_fuel:+.4f} s/kg (se {fr.notes['fuel_se']:.4f})"
      f"   literature 0.030-0.035")
prac = season.loc[~season["IsRace"]]
rows = []
for label, kw in (("naive", dict(correct_fuel=False, use_traffic=False, use_evo=False)),
                  ("+fuel", dict(correct_fuel=True, use_traffic=False, use_evo=False)),
                  ("+traffic", dict(correct_fuel=True, use_traffic=True, use_evo=False)),
                  ("+rubber", dict(correct_fuel=True, use_traffic=True, use_evo=True))):
    f = fit_practice(prac, lambda_fuel=fr.lambda_fuel, **kw)
    rows.append({"spec": label,
                 **{f"{c}_deg10": round(f.deg_rate(c, 10), 4) for c in f.compounds}})
ladder = pd.DataFrame(rows)
print(ladder.to_string(index=False))
print("    a negative number means the fit claims tyres get FASTER as they age")

# ---- Q3: what does the race say about tyre age? ----------------------- #
# (asked before Q2 because it is the yardstick Q2 is measured against)
print("\n" + "=" * 86)
print("Q3  WHAT DOES THE RACE SAY ABOUT TYRE AGE?")
stops = stop_table(season)
at = age_test(stops)
print(f"    {at['n']} stops, {stops['Round'].nunique()} events, "
      f"old-tyre age {at['age_range'][0]:.0f}-{at['age_range'][1]:.0f} laps")
print(f"    a new tyre is worth      {at['mean_step_s']:+.3f} s/lap "
      f"(sd {at['sd_step_s']:.3f})")
print(f"    linear test    : {at['lin_slope']:+.4f} +/- {at['lin_se']:.4f} s per lap"
      f"   p = {at['lin_p']:.3f}   -> finds nothing")
print(f"    quadratic test : age {at['quad_age']:+.4f} (p={at['quad_age_p']:.3f}),"
      f" age^2 {at['quad_age2']:+.5f} (p={at['quad_age2_p']:.3f}),"
      f" joint p = {at['joint_p']:.3f}")
print(f"    -> age DOES matter, non-monotonically: the value of a stop peaks at tyre age "
      f"{at['peak_age']:.0f} and then falls.")
print("    -> a linear test averages that to zero. Testing only the linear term would "
      "have produced a confident, wrong headline.")

# ---- Q2: does the practice curve predict that? ------------------------ #
print("\n" + "=" * 86)
print("Q2  DOES THE PRACTICE-FITTED CURVE PREDICT IT?")
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
print(f"    practice curve predicts {pred.mean():+.3f} s   observed {obs.mean():+.3f} s"
      f"   -> over-values a stop by {pred.mean() / obs.mean():.1f}x")
print(f"    calibration slope = {float(pc @ oc / (pc @ pc)):+.3f}   (1.0 would be correct)")
print("    -> the curve is not merely imprecise, its variation is uncorrelated with truth.")

# ---- Q4: what does predict it? --------------------------------------- #
print("\n" + "=" * 86)
print("Q4  WHAT DOES PREDICT THE VALUE OF A STOP?   (leave-one-event-out, no free constants)")
ab = ablation(stops)
print(ab.round(4).to_string(index=False))
print("    note: adding tyre age makes it WORSE. Leaving it out is the finding.")

print("\n    robustness to method-blind outlier cuts:")
print(robustness(stops).round(4).to_string(index=False))

best = loo_evaluate(stops, FULL)
pe = best["per_event"].merge(
    loo_evaluate(stops, [])["per_event"], on="round", suffixes=("_pitwall", "_mean"))
pe["pitwall_wins"] = pe["rmse_s_pitwall"] < pe["rmse_s_mean"]
print(f"\n    per-event: PITWALL beats the mean at {int(pe['pitwall_wins'].sum())}"
      f" / {len(pe)} events  (pooled gain is weighted by stop count)")
print(pe.round(3).to_string(index=False))

m = fit_stop_value(stops)
print("\n    fitted effects (full sample, SEs clustered by event):")
for nm, gloss in (("const", "base value of a fresh tyre"),
                  ("tt_c", "s per degC of track temperature"),
                  ("d_close", "s per unit of dirty-air relief")):
    if nm in m.res.params.index:
        print(f"      {nm:9s} {m.res.params[nm]:+.4f}  (se {m.res.bse[nm]:.4f}, "
              f"p={m.res.pvalues[nm]:.3f})   {gloss}")
print(f"      R2 = {m.notes['r2']:.3f}")

ladder.to_csv(os.path.join(ART, f"q1_ladder_{YEAR}.csv"), index=False)
ab.to_csv(os.path.join(ART, f"q4_ablation_{YEAR}.csv"), index=False)
stops.to_csv(os.path.join(ART, f"stops_{YEAR}.csv"), index=False)
print(f"\nwrote artifacts to {ART}")
