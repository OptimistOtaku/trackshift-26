"""Measured traffic exposure, per lap.

Most tyre-degradation write-ups treat traffic as unmeasurable and either ignore it or
throw away any lap that looks slow - which biases the degradation slope, because the
slow laps at the end of a stint are exactly the ones that carry the signal.

Here traffic is an observed covariate. We put every car on a common time grid, snap it
to track arc length, find the gap to the car ahead, and summarise per lap.
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

from .track import Centreline, build_centreline, forward_gap_m

# A car within ~1.0s is in dirty air with a real pace cost; by ~2.5s the effect has
# largely gone. Both thresholds are reported so the model can pick.
CLOSE_S = 1.0
NEAR_S = 2.5

# A sample this far from the racing line is not on the track: pit lane, run-off, or
# parked in the garage. Track width is ~15m and our reference is a racing line rather
# than a true centreline, so a car on the far side of the track can legitimately sit
# ~10m off it.
MAX_OFF_LINE_M = 20.0

# Never interpolate a car's position across a gap longer than this. A car sitting in
# the garage for ten minutes would otherwise be interpolated into a ghost that slides
# around the lap and manufactures traffic for everyone else.
MAX_INTERP_GAP_S = 2.0


def _resample_positions(pos: dict, cl: Centreline, grid_hz: float = 2.0) -> pd.DataFrame:
    """Return a long frame [t, car, s] on a common time grid."""
    frames = []
    for car, df in pos.items():
        d = df
        if "Status" in d.columns:
            d = d.loc[d["Status"] == "OnTrack"]
        d = d.dropna(subset=["X", "Y", "SessionTime"])
        # FastF1 emits (0,0,0) as a placeholder when a car is not being tracked.
        d = d.loc[~((d["X"] == 0) & (d["Y"] == 0))]
        if len(d) < 10:
            continue
        t = d["SessionTime"].dt.total_seconds().to_numpy(float)
        s, off = cl.arc_length(d["X"].to_numpy(), d["Y"].to_numpy())
        ok = np.isfinite(s) & (off <= MAX_OFF_LINE_M)
        if ok.sum() < 10:
            continue
        frames.append(pd.DataFrame({"t": t[ok], "car": str(car), "s": s[ok]}))

    if not frames:
        return pd.DataFrame(columns=["t", "car", "s"])

    long = pd.concat(frames, ignore_index=True)

    step = 1.0 / grid_hz
    t0, t1 = long["t"].min(), long["t"].max()
    grid = np.arange(t0, t1, step)

    out = []
    for car, g in long.groupby("car", sort=False):
        g = g.sort_values("t")
        ts = g["t"].to_numpy()
        # Interpolating arc length directly would smear across the start/finish wrap,
        # so interpolate on the unwrapped signal and re-wrap afterwards. Unwrap only
        # ever adds whole multiples of the lap length, so the re-wrap is exact.
        s_unwrapped = (np.unwrap(g["s"].to_numpy() * (2 * np.pi / cl.length))
                       * (cl.length / (2 * np.pi)))
        gi = np.interp(grid, ts, s_unwrapped, left=np.nan, right=np.nan)

        # Invalidate any grid point whose bracketing samples are too far apart in time.
        j = np.searchsorted(ts, grid).clip(1, len(ts) - 1)
        bracket = ts[j] - ts[j - 1]
        gi[bracket > MAX_INTERP_GAP_S] = np.nan

        out.append(pd.DataFrame({"t": grid, "car": car, "s": np.mod(gi, cl.length)}))

    return pd.concat(out, ignore_index=True).dropna(subset=["s"])


def _gap_matrix(wide_s: pd.DataFrame, length: float) -> pd.DataFrame:
    """Gap in metres to the nearest car ahead, for every car at every timestep."""
    cars = wide_s.columns.tolist()
    S = wide_s.to_numpy(float)                      # (T, C)
    T, C = S.shape
    gaps = np.full((T, C), np.nan)

    for j in range(C):
        d = (S - S[:, [j]]) % length                # (T, C) forward distance to each car
        d[:, j] = np.inf                            # ignore self
        d[~np.isfinite(S)] = np.inf                 # ignore untracked cars
        d[d <= 0.5] = np.inf                        # numerical self-matches
        with np.errstate(invalid="ignore"):
            gaps[:, j] = np.nanmin(np.where(np.isfinite(d), d, np.inf), axis=1)

    gaps[~np.isfinite(S)] = np.nan
    gaps[np.isinf(gaps)] = np.nan
    return pd.DataFrame(gaps, index=wide_s.index, columns=cars)


def lap_traffic_features(session, cl: Centreline | None = None,
                         grid_hz: float = 2.0) -> pd.DataFrame:
    """Per-lap traffic exposure.

    Returns one row per (Driver, LapNumber) with:
      `gap_min_s`    closest the car ahead came, in seconds
      `gap_med_s`    median gap over the lap
      `frac_close`   fraction of the lap spent within CLOSE_S of a car ahead
      `frac_near`    fraction of the lap spent within NEAR_S of a car ahead
    """
    if cl is None:
        cl = build_centreline(session)

    pos = session.pos_data
    grid = _resample_positions(pos, cl, grid_hz=grid_hz)
    if grid.empty:
        return pd.DataFrame(columns=["Driver", "LapNumber", "gap_min_s", "gap_med_s",
                                     "frac_close", "frac_near"])

    wide = grid.pivot_table(index="t", columns="car", values="s", aggfunc="first")
    gaps_m = _gap_matrix(wide, cl.length)

    # number -> code, because pos_data is keyed by driver number
    num_to_code = {}
    for _, r in session.results.iterrows():
        num_to_code[str(r["DriverNumber"])] = r["Abbreviation"]

    laps = session.laps
    rows = []
    for _, lap in laps.iterrows():
        code = lap["Driver"]
        num = str(lap["DriverNumber"])
        col = num if num in gaps_m.columns else None
        if col is None:
            continue
        t0 = lap["LapStartTime"]
        t1 = lap["Time"]
        if pd.isna(t0) or pd.isna(t1):
            continue
        t0, t1 = t0.total_seconds(), t1.total_seconds()
        if not (t1 > t0):
            continue

        sl = gaps_m[col].loc[(gaps_m.index >= t0) & (gaps_m.index < t1)].dropna()
        if len(sl) < 3:
            continue

        # metres -> seconds using this lap's own average speed
        lap_s = lap["LapTime"].total_seconds() if pd.notna(lap["LapTime"]) else (t1 - t0)
        v = cl.length / max(lap_s, 1e-6)
        gap_s = sl.to_numpy() / v

        rows.append({
            "Driver": code,
            "LapNumber": float(lap["LapNumber"]),
            "gap_min_s": float(np.min(gap_s)),
            "gap_med_s": float(np.median(gap_s)),
            "frac_close": float(np.mean(gap_s < CLOSE_S)),
            "frac_near": float(np.mean(gap_s < NEAR_S)),
            "traffic_observed": True,
        })

    return pd.DataFrame(rows)


def attach_traffic(laps: pd.DataFrame, traffic: pd.DataFrame) -> pd.DataFrame:
    """Left-join traffic features onto a cleaned lap table.

    Laps with no position coverage are marked `traffic_observed=False` rather than
    silently imputed as clean air, so downstream code can choose to exclude them.
    """
    cols = ("gap_min_s", "gap_med_s", "frac_close", "frac_near")
    if traffic.empty:
        out = laps.copy()
        for c in cols:
            out[c] = np.nan
        out["traffic_observed"] = False
        return out

    out = laps.merge(traffic, on=["Driver", "LapNumber"], how="left")
    out["traffic_observed"] = out["traffic_observed"].fillna(False).astype(bool)
    # Absence of coverage is not evidence of clean air; fill only so models that use
    # these columns do not crash, and keep the flag to gate on.
    out["frac_close"] = out["frac_close"].fillna(0.0)
    out["frac_near"] = out["frac_near"].fillna(0.0)
    for c in ("gap_min_s", "gap_med_s"):
        out[c] = out[c].fillna(out[c].median() if out[c].notna().any() else 99.0)
    return out
