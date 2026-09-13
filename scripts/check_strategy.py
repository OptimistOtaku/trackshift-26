"""Sanity check on the strategy engine, and the reconciliation the docstrings owe the reader.

Run: python scripts/check_strategy.py
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from pitwall import strategy as S                    # noqa: E402
from pitwall.stopvalue import stop_table             # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def main() -> None:
    season = pd.read_parquet(os.path.join(ROOT, "data", "season_2026.parquet"))
    stops = stop_table(season)
    deg = S.fit_degradation(stops)
    loss = pd.read_csv(os.path.join(ROOT, "artifacts", "pitloss_2026.csv"))

    print(f"stops={len(stops)}  events={stops['Round'].nunique()}")
    print(f"phi(a) = {deg.b1:+.4f}a {deg.b2:+.5f}a^2   peak={deg.peak:.1f}  "
          f"max age seen={deg.max_age_seen:.0f}")
    ages = [0, 3, 5, 10, 15, 20, 25, 35]
    print("phi at " + "/".join(str(a) for a in ages) + ": "
          + "  ".join(f"{float(deg.phi(a)):.2f}" for a in ages))
    print(f"observed mean step        : {stops['step_obs'].mean():+.3f} s/lap")

    # --- the level term, which is what the first version was missing ----------
    model = S.fit_level_model(stops)
    pred = model.predict(stops)
    print(f"model mean predicted step : {pred.mean():+.3f} s/lap")

    common = stops["pair"].value_counts()
    print("\ncommonest compound transitions:")
    print(common.head(5).to_string())

    # --- Austria: 71 laps, measured pit loss ---------------------------------
    rnd = 8
    row = loss.loc[loss["Round"] == rnd].iloc[0]
    pl = float(row["median"])
    race = season.loc[season["IsRace"] & (season["Round"] == rnd)]
    laps_n = int(race["LapNumber"].max())
    tt = float(race["TrackTemp"].mean())
    pair = str(common.index[0])
    print(f"\n=== {row['Event']} : {laps_n} laps, pit loss {pl:.2f}s, "
          f"tt {tt:.1f}C, pair {pair} ===")

    step_at, age_at = S.scenario(model, pair=pair, tt=tt, start_age=0, first_lap=1)
    ms = S.max_stint_laps(season)
    print(f"longest stint run this season: {ms:.0f} laps  ->  earliest viable stop "
          f"= lap {laps_n - ms:.0f}")
    for lap in (5, 10, 20, 25, 30, 40, 55):
        a = age_at(lap)
        adv = S.advantage(deg, step_at(lap), a)
        pb = S.payback_laps(adv, pl, max_laps=laps_n - lap if lap < laps_n else 1)
        print(f"  lap {lap:2d}  age {a:4.0f}  step0 {adv.step0:+.2f}  "
              f"dL {adv.delta_level:+.2f}  payback {str(pb):>5s}  "
              f"remaining {laps_n - lap:2d}")

    d = S.pit_window(deg, step_at=step_at, age_at=age_at, race_laps=laps_n,
                     pit_loss=pl, max_stint=ms)
    print("\nwindow:", S.summarise_window(d))

    # --- undercut on a rival on an equally old tyre --------------------------
    for gap in (0.8, 1.5, 3.0):
        u = S.undercut(deg, step0=step_at(25), age_mine=age_at(25), age_theirs=24.0,
                       gap_s=gap, laps=6)
        s = S.summarise_undercut(u, gap_s=gap)
        print(f"\nundercut from lap 25, {gap:.1f}s behind: works={s['works']}  "
              f"needs them out {s['needs_them_out_for_laps']} lap(s)  "
              f"first lap worth {s['gain_first_lap_s']:+.2f}s")
    print(u.to_string(index=False, float_format=lambda x: f"{x:.2f}"))

    # --- safety-car sensitivity ---------------------------------------------
    print("\nsafety-car sensitivity (probability supplied, never fitted):")
    for p in (0.0, 0.25, 0.5):
        r = S.sc_sensitivity(deg, step_at=step_at, age_at=age_at, race_laps=laps_n,
                             pit_loss=pl, max_stint=ms, p_sc=p)
        print(f"   p_sc={p:.2f}  pit loss {r['effective_pit_loss_s']:.1f}s  "
              f"window {r['open_lap']}-{r['close_lap']}")


if __name__ == "__main__":
    main()
