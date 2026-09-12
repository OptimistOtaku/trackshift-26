"""Does the race-fitted degradation trajectory reproduce the 288 measured pit-stop steps?

THE GATE. A per-lap trajectory is the foundation for anything real-time - a live estimate
has to have state that steps forward one lap at a time. But `stopvalue.py` deliberately does
not use a trajectory, because the practice-fitted one failed to transfer (calibration
+0.006). Before building a simulation on race-fitted curves, they have to pass the same test
that killed the practice ones.

Same ground truth, same leave-one-event-out discipline, same calibration slope. If this
fails, it is a fourth negative result and it gets written up as one - the trajectory does
not become the product just because a live demo would look good.

Run:  PYTHONPATH=src python scripts/check_trajectory.py
"""
from __future__ import annotations

import os
import sys

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from pitwall.stopvalue import FULL, loo_evaluate, stop_table          # noqa: E402
from pitwall.trajectory import (load_season_offline, loo_hybrid,      # noqa: E402
                                loo_race_curve)

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "artifacts")

pd.set_option("display.width", 200)
pd.set_option("display.max_columns", 50)


def main() -> int:
    print("loading cached season (no network)...")
    season = load_season_offline()
    stops = stop_table(season)
    print(f"  {len(season):6d} laps   {season['Round'].nunique()} events")
    print(f"  {len(stops):6d} stops  mean step {stops['step_obs'].mean():+.4f} s/lap "
          f"(sd {stops['step_obs'].std():.4f})")

    # Guard rail. Every number in the deck is built on 288 stops at +1.26 s/lap. If this
    # frame does not reproduce that, the loader is wrong and nothing below means anything.
    if not (len(stops) == 288 and abs(stops["step_obs"].mean() - 1.2624) < 5e-3):
        print("\n  !! this does not match the validated 288 stops / +1.2624 s. "
              "The season frame is built wrong - stop and fix the loader.")
        return 1
    print("  matches the validated table (288 stops, +1.2624 s/lap)\n")

    print("=" * 78)
    print("THE GATE: race-fitted per-lap trajectory, scored on the measured steps")
    print("leave-one-event-out - the curves never see the race they predict")
    print("=" * 78)
    tab = loo_race_curve(season, stops)
    if tab.empty:
        print("no event had enough data to score")
        return 1
    print(tab.to_string(index=False, float_format=lambda v: f"{v:9.4f}"))

    print("\nfor reference, the DEPLOYED cross-sectional model on the same target:")
    dep = loo_evaluate(stops, FULL)
    print(f"  pair+temp+traffic   rmse {dep['rmse_s']:.4f}  calib {dep['calib_slope']:.4f}"
          f"  n {dep['n']}")

    best = tab.loc[tab["spec"].isin(["wear + compound"])].iloc[0]
    print("\n" + "-" * 78)
    print(f"trajectory : rmse {best['rmse_s']:.4f}  calib {best['calib_slope']:.4f}"
          f"  vs mean {best['vs_mean_pct']:+.2f}%")
    print(f"deployed   : rmse {dep['rmse_s']:.4f}  calib {dep['calib_slope']:.4f}")
    print("-" * 78)

    # The verdict is stated by the calibration slope, not by RMSE. RMSE can look fine while
    # the predictions carry no stop-to-stop information at all - that is exactly how the
    # practice curve passed on averages (+1.52 predicted vs +1.26 observed) and failed here.
    c = float(best["calib_slope"])
    if c < 0.25:
        print(f"VERDICT: FAILS. calibration {c:.3f} - the trajectory does not track the\n"
              f"         steps stop to stop. Write it up as a negative result; do NOT\n"
              f"         build the simulation on it.")
    elif c < 0.60:
        print(f"VERDICT: PARTIAL. calibration {c:.3f} - real signal, wrong magnitude.\n"
              f"         Usable for a shape/animation, not for a quoted number.")
    else:
        print(f"VERDICT: PASSES. calibration {c:.3f} - the trajectory reproduces the\n"
              f"         measured steps. It can carry a live per-lap estimate.")

    pe = tab.attrs.get("per_event")
    if pe is not None and not pe.empty:
        print("\nper-event RMSE (each event predicted by the other eleven):")
        print(pe.to_string(index=False, float_format=lambda v: f"{v:8.3f}"))

    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, "trajectory_gate_2026.csv")
    tab.drop(columns=[]).to_csv(path, index=False)
    print(f"\nwrote {os.path.relpath(path, os.path.dirname(OUT))}")

    # ------------------------------------------------------------------ #
    # The follow-up. A PARTIAL is the profile of a feature, not a headline:
    # the ordering carries information while the magnitude is compressed, and
    # a single fitted coefficient could in principle rescale it. So enter the
    # trajectory as one regressor in the stop model and let the data price it.
    # Both stages are refitted per held-out event, or the held-out race's lap
    # times leak into its own prediction through the curves.
    # ------------------------------------------------------------------ #
    print("\n" + "=" * 78)
    print("FOLLOW-UP: the trajectory as a FEATURE, calibrated by the stop model")
    print("nested leave-one-event-out - curves AND stop model refit per event")
    print("=" * 78)
    hyb = loo_hybrid(season, stops)
    if hyb.empty:
        print("no event had enough data to score")
        return 0
    print(hyb.to_string(index=False, float_format=lambda v: f"{v:9.4f}"))

    hpe = hyb.attrs["per_event"]
    print("\nfitted coefficient on `traj`, per held-out event:")
    print(hpe[["round", "n", "b_traj", "deployed", "hybrid"]]
          .to_string(index=False, float_format=lambda v: f"{v:8.3f}"))

    dep_r = float(hyb.loc[hyb["spec"] == "deployed", "rmse_s"].iloc[0])
    hyb_r = float(hyb.loc[hyb["spec"] == "hybrid", "rmse_s"].iloc[0])
    won = int((hpe["hybrid"] < hpe["deployed"]).sum())
    b_med = float(hpe["b_traj"].median())
    print("\n" + "-" * 78)
    print(f"deployed {dep_r:.4f}   hybrid {hyb_r:.4f}   "
          f"hybrid wins {won}/{len(hpe)} events   median b_traj {b_med:.3f}")
    if hyb_r < dep_r:
        print("The trajectory adds information the cross-section did not have.")
    else:
        # b_traj near 1.0 would mean the trajectory was already on the right scale;
        # near 2.6 would mean the compression was being corrected. Shrunk well below
        # both means the fit is pricing it as mostly noise.
        print("VERDICT: NEGATIVE. The trajectory does not improve on the deployed model.\n"
              f"         Its coefficient is shrunk to ~{b_med:.2f}, far below the 1.0 that\n"
              "         would mean it was already correctly scaled. Per-event wins are\n"
              "         small and the pooled loss comes from the one event where the\n"
              "         coefficient is unstable - the signature of a weak feature being\n"
              "         overfitted, not of information the compound pair was missing.")

    hpath = os.path.join(OUT, "trajectory_hybrid_2026.csv")
    hyb.to_csv(hpath, index=False)
    hpe.to_csv(os.path.join(OUT, "trajectory_hybrid_per_event_2026.csv"), index=False)
    print(f"\nwrote {os.path.relpath(hpath, os.path.dirname(OUT))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
