"""Measure the cost of a pit stop, per circuit, from the laps the model normally throws away.

The strategy engine needs to know what a stop costs before it can say whether one is worth
making, and that number is not in `data/season_2026.parquet`: `clean_laps` drops in-laps and
out-laps, which are precisely the laps the pit loss lives in. So this script goes back to the
cached sessions for them.

WHAT IS MEASURED. For one stop, with the driver's own pace either side of it as the reference:

    pit_loss = (t_inlap - t_old) + (t_outlap - t_new)

Referencing the in-lap against the OLD stint's pace and the out-lap against the NEW stint's
pace matters. The in-lap is run on a worn tyre carrying more fuel and the out-lap on a fresh
one carrying less, so a single reference pace would charge the tyre difference to the pit
stop. Taking each side against its own stint nets the tyre and fuel state out and leaves the
part that is genuinely attributable to driving through the pit lane.

The cold-tyre penalty on the out-lap is deliberately left INSIDE the number. A strategist
choosing whether to stop pays it either way, so it belongs in the cost of stopping rather
than in a separate term.

Both laps must be green. A stop made under a safety car is cheap for reasons that have
nothing to do with this circuit's pit lane, and averaging those in would understate the cost
of a green-flag stop - the only kind the optimiser is ever asked about.

Run: python scripts/build_pitloss.py
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from pitwall.data import SessionRef, _green_flag, load_session  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ART = os.path.join(ROOT, "artifacts")
SEASON = os.path.join(ROOT, "data", "season_2026.parquet")

# A stop whose in-lap sits further than this before the last clean lap of the old stint is
# not a stop we can reference reliably - too many laps were filtered out in between.
MAX_MATCH_GAP = 4

# Method-blind cap on the measurement. The pooled distribution has median 21.8s and MAD
# 1.6s, so 30s is about five MADs out - beyond any pit lane transit. What sits past it is
# not this circuit's pit loss: it is a slow stop, a double-stack, or a damaged car limping
# in (out-laps of 132-141s against a 96s reference). The cut looks only at the measured
# loss, never at any model output, and the season median is insensitive to where it is put
# (21.74s at a 28s cap, 21.79s at 36s) - it only matters for the low-n circuits.
CAP_S = 30.0

# Per-circuit medians rest on between 1 and 35 stops, so the thin ones are shrunk toward the
# season median as if the season were worth this many local observations. Without it China's
# single surviving clean stop would set that circuit's pit loss on its own.
SHRINK_K = 8.0

# The cut cannot be applied per side. Pit entry sits before the timing line at some circuits
# and after it at others, so the in-lap carries a median 3.9s and the out-lap 17.8s at some
# venues and the reverse at others. Only the sum is comparable across circuits.


def raw_pit_laps(year: int, gp: str) -> pd.DataFrame:
    """In-lap and out-lap times for one race, straight from the cached session."""
    s = load_session(SessionRef(year, gp, "R"), telemetry=False)
    laps = s.laps.copy()
    if laps.empty:
        return pd.DataFrame()

    laps["LapTimeS"] = laps["LapTime"].dt.total_seconds()
    laps["Green"] = laps["TrackStatus"].apply(_green_flag)
    laps["IsInLap"] = laps["PitInTime"].notna()
    laps["IsOutLap"] = laps["PitOutTime"].notna()
    return laps[["Driver", "LapNumber", "LapTimeS", "Green", "IsInLap", "IsOutLap",
                 "Stint", "Compound"]]


def stop_costs(laps: pd.DataFrame) -> pd.DataFrame:
    """Pair each in-lap with the out-lap that follows it."""
    rows = []
    for drv, d in laps.groupby("Driver", sort=False):
        d = d.sort_values("LapNumber")
        for _, inlap in d.loc[d["IsInLap"]].iterrows():
            nxt = d.loc[d["LapNumber"] == inlap["LapNumber"] + 1]
            if nxt.empty or not bool(nxt["IsOutLap"].iloc[0]):
                continue                      # retired in the pits, or a red-flag stop
            out = nxt.iloc[0]
            rows.append({
                "Driver": str(drv),
                "InLap": float(inlap["LapNumber"]),
                "t_inlap": float(inlap["LapTimeS"]),
                "t_outlap": float(out["LapTimeS"]),
                "green": bool(inlap["Green"]) and bool(out["Green"]),
            })
    return pd.DataFrame(rows)


def aggregate(d: pd.DataFrame) -> pd.DataFrame:
    """Per-circuit pit loss: robust, capped, and shrunk toward the season."""
    g = d.loc[d["green"] & (d["pit_loss_s"] <= CAP_S)]
    season = float(g["pit_loss_s"].median())
    per = (g.groupby(["Round", "Event"])["pit_loss_s"]
           .agg(n="size", raw="median",
                mad=lambda x: float(np.median(np.abs(x - x.median()))))
           .reset_index())
    per["median"] = (per["n"] * per["raw"] + SHRINK_K * season) / (per["n"] + SHRINK_K)
    per["season_median"] = season
    per["shrunk_by_s"] = per["median"] - per["raw"]
    return per.sort_values("Round")


def main(refresh: bool = False) -> None:
    stops_path = os.path.join(ART, "pitloss_stops_2026.csv")

    if not refresh and os.path.exists(stops_path):
        # The cache read is the slow part and its output does not change unless the season
        # is rebuilt, so re-aggregating a saved measurement is the default.
        d = pd.read_csv(stops_path)
        print(f"reusing {len(d)} measured stops from {os.path.basename(stops_path)}"
              "   (pass --refresh to re-read the cache)")
    else:
        d = extract()
        if d.empty:
            print("no pit losses measured")
            return
        d.to_csv(stops_path, index=False)

    per = aggregate(d)
    per.to_csv(os.path.join(ART, "pitloss_2026.csv"), index=False)

    g = d.loc[d["green"]]
    kept = g.loc[g["pit_loss_s"] <= CAP_S]
    print()
    print(per[["Round", "Event", "n", "raw", "median", "shrunk_by_s"]]
          .to_string(index=False, float_format=lambda x: f"{x:.2f}"))
    print()
    print(f"green-flag stops measured : {len(g)} of {len(d)}")
    print(f"kept after the {CAP_S:.0f}s cap  : {len(kept)}  "
          f"({len(g) - len(kept)} incident stops dropped)")
    print(f"season median pit loss    : {kept['pit_loss_s'].median():.2f} s")
    print(f"circuit spread (shrunk)   : "
          f"{per['median'].min():.1f} - {per['median'].max():.1f} s")


def extract() -> pd.DataFrame:
    """Read every race from the cache and measure the cost of each stop."""
    season = pd.read_parquet(SEASON)
    stops = pd.read_csv(os.path.join(ART, "stops_2026.csv"))
    events = (season[["Round", "Event", "Year"]].drop_duplicates()
              .sort_values("Round").reset_index(drop=True))

    out = []
    for _, ev in events.iterrows():
        rnd, gp, yr = int(ev["Round"]), str(ev["Event"]), int(ev["Year"])
        try:
            laps = raw_pit_laps(yr, gp)
        except Exception as e:                # a cache miss should not kill the whole run
            print(f"[R{rnd:02d}] {gp[:26]:26s} FAILED: {type(e).__name__}: {e}")
            continue
        if laps.empty:
            print(f"[R{rnd:02d}] {gp[:26]:26s} no laps")
            continue

        costs = stop_costs(laps)
        st = stops.loc[stops["Round"] == rnd]
        matched = 0
        for _, c in costs.iterrows():
            # the stop row whose last clean old-tyre lap sits just before this in-lap
            cand = st.loc[(st["Driver"] == c["Driver"])
                          & (st["PitLap"] <= c["InLap"])
                          & (st["PitLap"] >= c["InLap"] - MAX_MATCH_GAP)]
            if cand.empty:
                continue
            row = cand.nlargest(1, "PitLap").iloc[0]
            loss = (c["t_inlap"] - row["t_old"]) + (c["t_outlap"] - row["t_new"])
            out.append({
                "Round": rnd, "Event": gp, "Driver": c["Driver"],
                "PitLap": float(row["PitLap"]), "InLap": c["InLap"],
                "t_inlap": c["t_inlap"], "t_outlap": c["t_outlap"],
                "t_old": float(row["t_old"]), "t_new": float(row["t_new"]),
                "pit_loss_s": float(loss), "green": bool(c["green"]),
            })
            matched += 1
        print(f"[R{rnd:02d}] {gp[:26]:26s} stops={len(costs):3d} matched={matched:3d}")

    return pd.DataFrame(out)


if __name__ == "__main__":
    main(refresh="--refresh" in sys.argv)
