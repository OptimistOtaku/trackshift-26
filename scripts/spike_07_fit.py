"""Spike 7: fit stage A (race) and stage B (practice) on one event.

The number that matters: does correcting for fuel change the measured degradation, and
does it move it in the direction physics says it must (upwards)?

Run: python scripts/spike_07_fit.py
"""
import sys, os, warnings
warnings.filterwarnings("ignore")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import numpy as np
import pandas as pd
from pitwall.data import (SessionRef, load_session, clean_laps, fuel_burn_rate,
                          race_laps_of)
from pitwall.track import build_centreline
from pitwall.traffic import lap_traffic_features, attach_traffic
from pitwall.degradation import fit_race, fit_practice, identification_report

pd.set_option("display.width", 220)

GP, YEAR = "Hungary", 2026


def prep(ses, burn=None):
    s = load_session(SessionRef(YEAR, GP, ses), telemetry=True)
    cl = build_centreline(s)
    tf = lap_traffic_features(s, cl)
    return s, attach_traffic(clean_laps(s, burn_kg_per_lap=burn), tf)


# The race sets the fuel burn rate for every session at this event. Practice must be
# cleaned with that rate, not with its own lap count.
s_race, race = prep("R")
RACE_LAPS = race_laps_of(s_race)
BURN = fuel_burn_rate(YEAR, RACE_LAPS)
print(f"race distance {RACE_LAPS:.0f} laps -> fuel burn {BURN:.3f} kg/lap")

prac = pd.concat([prep(s, burn=BURN)[1] for s in ("FP1", "FP2", "FP3")],
                 ignore_index=True)
print(f"practice laps={len(prac)} runs={prac['RunId'].nunique()}   "
      f"race laps={len(race)} runs={race['RunId'].nunique()}")

# ---------------- stage A ---------------- #
fr = fit_race(race)
print("\n" + "=" * 70)
print(f"STAGE A (race)  n={fr.n_obs} runs={fr.n_groups} R2={fr.notes['r2']:.3f}")
print(f"  lambda_fuel = {fr.lambda_fuel:+.4f} s/kg  (se {fr.notes['fuel_se']:.4f})")
print(f"  literature range for fuel sensitivity is ~0.030-0.035 s/kg")
print(f"  frac_close  = {fr.res.params.get('frac_close', np.nan):+.3f} s "
      f"(cost of spending a whole lap within 1.0s)")
print(f"  TrackTempC  = {fr.res.params.get('TrackTempC', np.nan):+.4f} s/degC")
print("\nrace degradation:")
print(fr.summary_table().round(4).to_string(index=False))

# ---------------- identification lever ---------------- #
print("\n" + "=" * 70)
print("practice runs available for identification:")
ir = identification_report(prac)
print(ir.round(1).to_string(index=False))
print(f"\nruns starting on used rubber: {int((~ir['fresh'].astype(bool)).sum())} / {len(ir)}")
print(f"spread of starting tyre age: {ir['age_start'].min():.0f} .. {ir['age_start'].max():.0f} laps")

# ---------------- stage B, with and without fuel correction ---------------- #
print("\n" + "=" * 70)
naive = fit_practice(prac, lambda_fuel=fr.lambda_fuel, correct_fuel=False)
deconf = fit_practice(prac, lambda_fuel=fr.lambda_fuel, correct_fuel=True)

cmp = (naive.summary_table()[["compound", "deg_at_10", "loss_0_15_s"]]
       .rename(columns={"deg_at_10": "naive_deg10", "loss_0_15_s": "naive_loss15"})
       .merge(deconf.summary_table()[["compound", "deg_at_10", "loss_0_15_s"]]
              .rename(columns={"deg_at_10": "pitwall_deg10",
                               "loss_0_15_s": "pitwall_loss15"}),
              on="compound"))
cmp["understated_by"] = cmp["pitwall_deg10"] - cmp["naive_deg10"]
print("NAIVE vs DECONFOUNDED practice degradation (s/lap at age 10):")
print(cmp.round(4).to_string(index=False))

burn = BURN
print(f"\nexpected shift from fuel alone = lambda * burn_per_lap "
      f"= {fr.lambda_fuel:.4f} * {burn:.3f} = {fr.lambda_fuel*burn:+.4f} s/lap")
print("observed shifts:", " ".join(f"{c}={v:+.4f}" for c, v in
                                  zip(cmp["compound"], cmp["understated_by"])))
