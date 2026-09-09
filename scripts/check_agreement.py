"""Score the pit window against every stop the season actually made, leave-one-event-out.

Writes artifacts/window_agreement_2026.csv, which scripts/check_window_placebo.py then reads
to ask the question that matters: is the coverage anything more than width and race length?
(It is not - see strategy.py. This script is what established that.)

Run: python scripts/check_agreement.py
"""
from __future__ import annotations

import os
import sys

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from pitwall import strategy as S              # noqa: E402
from pitwall.stopvalue import stop_table       # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT = os.path.join(ROOT, "artifacts", "window_agreement_2026.csv")


def main() -> None:
    season = pd.read_parquet(os.path.join(ROOT, "data", "season_2026.parquet"))
    stops = stop_table(season)
    loss = pd.read_csv(os.path.join(ROOT, "artifacts", "pitloss_2026.csv"))
    pit_loss = dict(zip(loss["Round"].astype(int), loss["median"].astype(float)))

    a = S.agreement(stops, season, pit_loss, loo=True)
    a.to_csv(OUT, index=False)

    ok = a.loc[a["has_window"]]
    print(f"scored stops        : {len(a)}  (window exists for {len(ok)})")
    print(f"chosen lap inside   : {ok['inside'].mean():.1%} "
          f"({int(ok['inside'].sum())}/{len(ok)})")
    print(f"median window width : {ok['width'].median():.0f} laps of "
          f"{ok['race_laps'].median():.0f}  "
          f"({(ok['width'] / ok['race_laps']).median():.0%} of the race)")
    if (~ok["inside"]).any():
        print(f"misses              : median "
              f"{ok.loc[~ok['inside'], 'laps_outside'].median():.0f} laps outside")
    print()
    print(ok.groupby("Round")
          .agg(n=("inside", "size"), inside=("inside", "mean"), width=("width", "median"))
          .to_string(float_format=lambda x: f"{x:.2f}"))
    print(f"\nwrote {os.path.relpath(OUT, ROOT)}")
    print("now run: python scripts/check_window_placebo.py   <- the test that matters")


if __name__ == "__main__":
    main()
