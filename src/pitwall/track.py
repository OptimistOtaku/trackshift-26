"""Track geometry: map raw XY position samples onto track arc length.

Traffic can only be measured if we know where each car is *along the track*, not just
its XY coordinate. We build a centreline from a fast lap's telemetry - which carries a
`Distance` channel in metres - and then snap every position sample to the nearest
centreline point to recover arc length.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree


@dataclass
class Centreline:
    xy: np.ndarray       # (N, 2) reference points
    s: np.ndarray        # (N,)   arc length in metres at each reference point
    length: float        # total track length in metres
    _tree: cKDTree

    def arc_length(self, x: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Snap XY samples to the centreline.

        Returns `(s, off_line_m)` - arc length in metres, and how far the sample sat
        from the reference line. A large `off_line_m` means the car was not on the
        racing line at all: pit lane, run-off, or stationary in the garage. Callers use
        it to reject those samples rather than letting them masquerade as track
        position.
        """
        pts = np.column_stack([np.asarray(x, float), np.asarray(y, float)])
        ok = np.isfinite(pts).all(axis=1)
        s_out = np.full(len(pts), np.nan)
        d_out = np.full(len(pts), np.nan)
        if ok.any():
            dist, idx = self._tree.query(pts[ok])
            s_out[ok] = self.s[idx]
            d_out[ok] = dist
        return s_out, d_out


def build_centreline(session, *, resample_m: float = 1.0,
                     n_candidates: int = 25) -> Centreline:
    """Build a centreline from session telemetry.

    The fastest lap alone is not reliable: its telemetry is sometimes truncated (which
    silently shortens the track) and sometimes overruns the line (which lengthens it).
    Either way every gap derived from it is corrupted. So we measure the `Distance`
    span of the fastest `n_candidates` laps and keep the lap closest to the *median*
    span, which is robust to both failure modes.

    `resample_m` sets the arc-length quantisation, and therefore the floor on any gap
    we can resolve: at 1m that floor is ~0.02s at racing speed, far below the ~1s
    thresholds the traffic features use.

    Requires the session to have been loaded with `telemetry=True`.
    """
    laps = session.laps
    laps = laps.loc[laps["LapTime"].notna()].sort_values("LapTime").head(n_candidates)

    cands = []
    for _, lap in laps.iterrows():
        try:
            tel = lap.get_telemetry().dropna(subset=["X", "Y", "Distance"])
        except Exception:
            continue
        tel = tel.loc[tel["Distance"] >= 0]
        if len(tel) < 100:
            continue
        span = float(tel["Distance"].max() - tel["Distance"].min())
        cands.append((span, tel))

    if not cands:
        raise RuntimeError("no usable telemetry to build a centreline")

    target = float(np.median([c[0] for c in cands]))
    span, tel = min(cands, key=lambda c: abs(c[0] - target))

    s = tel["Distance"].to_numpy(float)
    xy = tel[["X", "Y"]].to_numpy(float)

    # Distance is monotone within a lap; enforce it so interpolation is well behaved.
    order = np.argsort(s)
    s, xy = s[order], xy[order]
    keep = np.r_[True, np.diff(s) > 1e-6]
    s, xy = s[keep], xy[keep]

    length = float(s[-1] - s[0])
    s = s - s[0]

    # Resample to a uniform grid so nearest-neighbour error is bounded by resample_m.
    grid = np.arange(0.0, length, resample_m)
    xg = np.interp(grid, s, xy[:, 0])
    yg = np.interp(grid, s, xy[:, 1])
    xy_g = np.column_stack([xg, yg])

    return Centreline(xy=xy_g, s=grid, length=length, _tree=cKDTree(xy_g))


def forward_gap_m(s_self: np.ndarray, s_other: np.ndarray, length: float) -> np.ndarray:
    """Distance in metres from each car to the car ahead, wrapping at the line.

    Positive and in [0, length): how far ahead `s_other` is of `s_self`.
    """
    d = (np.asarray(s_other, float) - np.asarray(s_self, float)) % length
    return d
