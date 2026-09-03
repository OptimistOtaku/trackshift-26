"""Run leave-one-event-out validation over a season.

Fit on each event's practice, predict that event's race, with the fuel coefficient taken
from other events only. Prints both scoring targets and writes results to artifacts/.

Run: python scripts/validate_season.py [year]
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
from pitwall.validate import pool, validate_season

pd.set_option("display.width", 240)

YEAR = int(sys.argv[1]) if len(sys.argv) > 1 else 2026
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ART = os.path.join(ROOT, "artifacts")
os.makedirs(ART, exist_ok=True)

season = pd.read_parquet(os.path.join(ROOT, "data", f"season_{YEAR}.parquet"))
print(f"season {YEAR}: {len(season)} laps, {season['Round'].nunique()} events, "
      f"{season['RunId'].nunique()} runs   "
      f"(race={int(season['IsRace'].sum())}, practice={int((~season['IsRace']).sum())})")

# ---------------- stage A, pooled over every race ---------------- #
print("\n" + "=" * 84)
fr = fit_race(season)
print(f"STAGE A - pooled race fit   n={fr.n_obs} runs={fr.n_groups} "
      f"events={fr.notes['n_events']} R2={fr.notes['r2']:.3f}")
for name, lit in (("FuelKg", "literature ~0.030-0.035 s/kg"),
                  ("TrackEvo", "negative = track gets faster as rubber goes down"),
                  ("frac_close", "cost of a lap spent entirely within 1.0s"),
                  ("TrackTempC", "positive = hotter is slower")):
    if name in fr.res.params.index:
        print(f"  {name:11s} = {fr.res.params[name]:+.4f}  "
              f"(se {fr.res.bse[name]:.4f})   {lit}")

# Is lambda robust to dropping the evolution term? The two are correlated within a race,
# so a large shift here would mean the fuel coefficient is partly absorbing rubber.
alt = fit_race(season.assign(TrackEvo=np.nan))
print(f"\n  robustness: lambda without the evolution term = {alt.lambda_fuel:+.4f} s/kg "
      f"(with = {fr.lambda_fuel:+.4f})")

print("\nrace degradation, pooled across events (season average):")
print(fr.summary_table().round(4).to_string(index=False))

# ---------------- what the ablation does to the practice fit ---------------- #
print("\n" + "=" * 84)
print("PRACTICE FIT, one confounder at a time (pooled practice, s/lap at tyre age 10):")
prac = season.loc[~season["IsRace"]]
ladder = [
    ("B1 naive      ", dict(correct_fuel=False, use_traffic=False, use_evo=False)),
    ("B2 +fuel      ", dict(correct_fuel=True, use_traffic=False, use_evo=False)),
    ("   +traffic   ", dict(correct_fuel=True, use_traffic=True, use_evo=False)),
    ("B3 +evolution ", dict(correct_fuel=True, use_traffic=True, use_evo=True)),
]
rows = []
for label, kw in ladder:
    f = fit_practice(prac, lambda_fuel=fr.lambda_fuel, **kw)
    row = {"spec": label, "R2": f.notes["r2"], "evo_coef": f.notes.get("evo_coef")}
    for c in f.compounds:
        row[f"{c}_deg10"] = f.deg_rate(c, 10)
    rows.append(row)
print(pd.DataFrame(rows).round(4).to_string(index=False))
print("  a negative number means the fit thinks tyres get FASTER as they age")

# ---------------- leave-one-event-out ---------------- #
print("\n" + "=" * 84)
print("LEAVE-ONE-EVENT-OUT   fit practice -> predict race   (RMSE s, lower is better)")
shape, steps, results = validate_season(season)

if not shape.empty:
    print("\n" + "-" * 84)
    print("TARGET 1 - stint shape (expected to be uninformative; see validate.py docstring)")
    print(pool(shape).round(4).to_string(index=False))

if not steps.empty:
    print("\n" + "-" * 84)
    print("TARGET 2 - the pit-stop step: pace bought by fitting a new tyre")
    ps = pool(steps)
    print(ps.round(4).to_string(index=False))
    print(f"\n  mean observed step = {steps['mean_obs_step_s'].mean():+.3f} s")
    print("  mean predicted step by method:")
    print(steps.groupby("method")["mean_pred_step_s"].mean().round(3).to_string())

    b0 = float(ps.loc[ps["method"] == "B0 flat", "rmse_s"].iloc[0])
    b1 = float(ps.loc[ps["method"] == "B1 naive", "rmse_s"].iloc[0])
    b3 = float(ps.loc[ps["method"] == "B3 PITWALL", "rmse_s"].iloc[0])
    print(f"\n  PITWALL vs naive : {(1 - b3 / b1) * 100:+.1f}% RMSE")
    print(f"  PITWALL vs flat  : {(1 - b3 / b0) * 100:+.1f}% RMSE")

    piv = steps.pivot_table(index=["round", "event"], columns="method", values="rmse_s")
    piv["pitwall_wins"] = piv["B3 PITWALL"] < piv["B1 naive"]
    print("\nper-event pit-step RMSE:")
    print(piv.round(3).to_string())
    print(f"\nPITWALL beat naive at {int(piv['pitwall_wins'].sum())} / {len(piv)} events")

for name, df in (("shape", shape), ("steps", steps)):
    if not df.empty:
        df.to_csv(os.path.join(ART, f"validation_{YEAR}_{name}.csv"), index=False)
fr.summary_table().to_csv(os.path.join(ART, f"race_degradation_{YEAR}.csv"), index=False)
print(f"\nwrote artifacts to {ART}")
