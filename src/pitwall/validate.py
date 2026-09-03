"""Out-of-sample validation: fit on practice, predict the race.

Fit on an event's practice sessions, score against that event's race - a genuine
forecast, made only from data that exists before the race is run. The fuel coefficient
comes from OTHER events' races (leave-one-event-out), never from the race being predicted.

TWO TARGETS, AND WHY THE OBVIOUS ONE IS USELESS.

Target 1, stint shape: how much slower is lap 18 of a stint than lap 3. This is the
natural thing to score and it CANNOT distinguish a fuel-corrected model from a naive one.
The reason is algebraic, not statistical. Inside a race stint, fuel mass is an exact
affine function of tyre age - both advance one lap at a time - so adding `lambda*FuelKg`
to a prediction only re-shifts the linear age coefficient. It shifts it by exactly the
`lambda*burn` that the naive practice fit had already absorbed into its own age slope.
Once each stint is granted its own constant, the two predictions are identical to machine
precision. We report this target anyway, because it is the metric most write-ups would
have quoted, and quoting it without noticing the identity would be a mistake.

Target 2, the pit-stop step: how much lap time a driver gets back by fitting a new tyre.
This is where the confounding actually bites. Across a pit stop, tyre age resets to zero
but fuel does NOT - the car burns the same lap of fuel either way. So the step measures
`phi(a_old) - phi(a_new)` with the fuel effect almost entirely cancelled, and a model
whose age slope is short by `lambda*burn` will under-predict the step by
`lambda*burn*a_old` - around 0.6s at a 20-lap-old tyre. That is not a rounding error, it
is the difference between calling a stop and staying out.

THE LADDER. Each rung handles one more confounder, so any improvement is attributable:
  B0  flat        no degradation model at all
  B1  naive       practice curve fitted ignoring fuel, traffic and track evolution
  B2  +fuel       fuel handled in the practice fit and in the prediction
  B3  PITWALL     B2 plus measured traffic and measured track evolution

WHAT PRACTICE CANNOT TELL US. With one intercept per run, the compound *base* offset is
perfectly collinear with the run dummies - each run is a single compound, so nothing
identifies whether a SOFT is intrinsically faster than a MEDIUM. Practice gives
degradation *shapes*, not offsets. Both targets are therefore scored with a free constant
per stint (target 1) or per compound pair (target 2), granted equally to every method.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .degradation import SLICKS, Fit, fit_practice, fit_race

MIN_RUN_LAPS_SCORED = 6      # a stint needs this many clean laps to have a shape
PIT_EDGE_LAPS = 3            # laps averaged either side of a stop
MAX_PIT_LAP_GAP = 4          # reject stops where too many laps were filtered out
MIN_PAIR_OBS = 3             # compound pairs rarer than this cannot support a constant


# ------------------------------------------------------------------------- #
# shared scoring helper
# ------------------------------------------------------------------------- #

def _demeaned_metrics(obs: np.ndarray, pred: np.ndarray, groups: np.ndarray,
                      label: str) -> dict:
    """RMSE after removing a free constant per group.

    The constant is the nuisance parameter every method is entitled to (a car's base pace
    at this event, or an unidentified compound offset). Removing it by group means the
    score reflects only what the model claims to know.
    """
    r = obs - pred
    s = pd.Series(r).groupby(pd.Series(groups)).transform("mean").to_numpy()
    r = r - s
    return {
        "method": label,
        "rmse_s": float(np.sqrt(np.mean(r ** 2))),
        "mae_s": float(np.mean(np.abs(r))),
        "p90_abs_s": float(np.percentile(np.abs(r), 90)),
        "n": int(len(r)),
    }


# ------------------------------------------------------------------------- #
# target 1 - stint shape
# ------------------------------------------------------------------------- #

def _shape_prediction(fit: Fit, laps: pd.DataFrame, *,
                      use_fuel: bool, use_traffic: bool) -> np.ndarray:
    """Model terms that vary within a race stint, in seconds.

    Excludes anything constant within a run - intercepts, compound offsets, driver
    effects - because the free per-stint constant absorbs those. Track evolution is
    excluded too: its coefficient was estimated on practice runs and a race is a single
    long run at a rubber level practice never reaches, so applying it here would be
    extrapolation dressed up as a correction.
    """
    z = np.zeros(len(laps), float)
    ages = laps["TyreAge"].to_numpy(float)
    for c in fit.compounds:
        m = (laps["Compound"] == c).to_numpy()
        if m.any():
            z[m] = fit.curve(c, ages[m], clip=True)

    if use_fuel and fit.lambda_fuel is not None and np.isfinite(fit.lambda_fuel):
        z = z + fit.lambda_fuel * laps["FuelKg"].to_numpy(float)

    if use_traffic and "frac_close" in laps.columns:
        rho = float(fit.res.params.get("frac_close", 0.0))
        z = z + rho * np.nan_to_num(laps["frac_close"].to_numpy(float))

    return z


def score_stint_shape(race: pd.DataFrame, naive: Fit, deconf: Fit) -> pd.DataFrame:
    keep = race.groupby("RunId")["LapTimeS"].transform("size") >= MIN_RUN_LAPS_SCORED
    r = race.loc[keep & race["Compound"].isin(deconf.compounds)].copy()
    if r.empty:
        return pd.DataFrame()

    obs = r["LapTimeS"].to_numpy(float)
    grp = r["RunId"].to_numpy()
    rows = [
        _demeaned_metrics(obs, np.zeros(len(r)), grp, "B0 flat"),
        _demeaned_metrics(obs, _shape_prediction(naive, r, use_fuel=False,
                                                 use_traffic=False), grp, "B1 naive"),
        _demeaned_metrics(obs, _shape_prediction(deconf, r, use_fuel=True,
                                                 use_traffic=False), grp, "B2 +fuel"),
        _demeaned_metrics(obs, _shape_prediction(deconf, r, use_fuel=True,
                                                 use_traffic=True), grp, "B3 PITWALL"),
    ]
    return pd.DataFrame(rows)


# ------------------------------------------------------------------------- #
# target 2 - the pit-stop step
# ------------------------------------------------------------------------- #

def pit_steps(race: pd.DataFrame, *, edge: int = PIT_EDGE_LAPS) -> pd.DataFrame:
    """One row per race pit stop: pace either side of it.

    In/out laps were already dropped during cleaning, so `before` is the last clean lap
    on the old tyre and `after` the first clean lap on the new one. A stop is rejected if
    too many laps between the two were filtered out, which is the signature of a stop made
    under a safety car - there the surrounding laps are not representative pace and the
    step would be measuring the safety car, not the tyre.

    Grouping is by (event, driver), never driver alone. Handed a whole season, a
    driver-only grouping would pair that driver's last run at one event with their first run
    at the next and call the difference a pit stop - a Monaco-to-Spa "stop" of 34 seconds.
    `MAX_PIT_LAP_GAP` cannot catch it either, because lap numbers restart every race.
    """
    key = ["Round", "Driver"] if "Round" in race.columns else ["Driver"]
    rows = []
    for _, d in race.groupby(key, sort=False):
        drv = str(d["Driver"].iloc[0])
        runs = (d.groupby("RunId")
                .agg(lo=("LapNumber", "min"), hi=("LapNumber", "max"),
                     n=("LapTimeS", "size"), compound=("Compound", "first"))
                .sort_values("lo"))
        ids = runs.index.tolist()
        for i in range(len(ids) - 1):
            r1, r2 = runs.loc[ids[i]], runs.loc[ids[i + 1]]
            if r1["n"] < edge or r2["n"] < edge:
                continue
            if r2["lo"] - r1["hi"] > MAX_PIT_LAP_GAP:
                continue

            a = d.loc[d["RunId"] == ids[i]].nlargest(edge, "LapNumber")
            b = d.loc[d["RunId"] == ids[i + 1]].nsmallest(edge, "LapNumber")

            def mean(df, col):
                return float(df[col].mean()) if col in df.columns else np.nan

            rows.append({
                "Round": int(d["Round"].iloc[0]) if "Round" in d.columns else 0,
                "Driver": drv,
                "PitLap": float(r1["hi"]),
                "c_old": r1["compound"], "c_new": r2["compound"],
                "age_old": mean(a, "TyreAge"), "age_new": mean(b, "TyreAge"),
                "t_old": mean(a, "LapTimeS"), "t_new": mean(b, "LapTimeS"),
                "fuel_old": mean(a, "FuelKg"), "fuel_new": mean(b, "FuelKg"),
                "close_old": mean(a, "frac_close"), "close_new": mean(b, "frac_close"),
            })

    out = pd.DataFrame(rows)
    if out.empty:
        return out
    # positive step = the old tyre was slower, i.e. the stop bought pace
    out["step_obs"] = out["t_old"] - out["t_new"]
    out["pair"] = out["c_old"] + ">" + out["c_new"]
    out["d_fuel"] = out["fuel_old"] - out["fuel_new"]
    out["d_close"] = out["close_old"] - out["close_new"]
    return out


def _step_prediction(fit: Fit, st: pd.DataFrame, *,
                     use_fuel: bool, use_traffic: bool) -> np.ndarray:
    """Predicted pace gained by fitting a new tyre."""
    def phi(compounds, ages):
        z = np.zeros(len(st), float)
        for c in fit.compounds:
            m = (compounds == c).to_numpy()
            if m.any():
                z[m] = fit.curve(c, ages[m].to_numpy(float), clip=True)
        return z

    z = phi(st["c_old"], st["age_old"]) - phi(st["c_new"], st["age_new"])

    if use_fuel and fit.lambda_fuel is not None and np.isfinite(fit.lambda_fuel):
        z = z + fit.lambda_fuel * st["d_fuel"].to_numpy(float)
    if use_traffic:
        rho = float(fit.res.params.get("frac_close", 0.0))
        z = z + rho * np.nan_to_num(st["d_close"].to_numpy(float))
    return z


def _calibration(obs: np.ndarray, pred: np.ndarray) -> float:
    """Slope of observed on predicted. 1.0 means the model has the magnitude right."""
    p = pred - pred.mean()
    v = float(np.dot(p, p))
    return float(np.dot(p, obs - obs.mean()) / v) if v > 1e-9 else np.nan


def score_pit_steps(race: pd.DataFrame, naive: Fit, deconf: Fit) -> tuple[pd.DataFrame, pd.DataFrame]:
    st = pit_steps(race)
    if st.empty:
        return pd.DataFrame(), st
    # only compound pairs seen often enough to support their own constant
    st = st.loc[st.groupby("pair")["step_obs"].transform("size") >= MIN_PAIR_OBS].copy()
    st = st.loc[st["c_old"].isin(deconf.compounds) & st["c_new"].isin(deconf.compounds)]
    if st.empty:
        return pd.DataFrame(), st

    obs = st["step_obs"].to_numpy(float)
    grp = st["pair"].to_numpy()
    specs = [
        ("B0 flat", np.zeros(len(st))),
        ("B1 naive", _step_prediction(naive, st, use_fuel=False, use_traffic=False)),
        ("B2 +fuel", _step_prediction(deconf, st, use_fuel=True, use_traffic=False)),
        ("B3 PITWALL", _step_prediction(deconf, st, use_fuel=True, use_traffic=True)),
    ]
    rows = []
    for label, pred in specs:
        m = _demeaned_metrics(obs, pred, grp, label)
        m["calib_slope"] = _calibration(obs, pred) if np.any(pred) else np.nan
        m["mean_pred_step_s"] = float(np.mean(pred))
        rows.append(m)
    out = pd.DataFrame(rows)
    out["mean_obs_step_s"] = float(np.mean(obs))
    return out, st


# ------------------------------------------------------------------------- #
# per event / per season
# ------------------------------------------------------------------------- #

def validate_event(season: pd.DataFrame, target_round: int, *,
                   min_practice_laps: int = 120) -> dict:
    tgt = season.loc[season["Round"] == target_round]
    prac = tgt.loc[~tgt["IsRace"]].copy()
    race = tgt.loc[tgt["IsRace"]].copy()

    if len(prac) < min_practice_laps or race.empty:
        return {"round": target_round, "skipped": True,
                "reason": f"practice laps={len(prac)}, race laps={len(race)}"}

    # lambda from every OTHER event's race - the target race is never seen
    others = season.loc[(season["Round"] != target_round) & season["IsRace"]]
    if others["Round"].nunique() < 2:
        return {"round": target_round, "skipped": True, "reason": "not enough other events"}
    fr = fit_race(others)
    lam = fr.lambda_fuel

    naive = fit_practice(prac, lambda_fuel=lam, correct_fuel=False, use_evo=False)
    deconf = fit_practice(prac, lambda_fuel=lam, correct_fuel=True, use_evo=True)

    shape = score_stint_shape(race, naive, deconf)
    steps, step_rows = score_pit_steps(race, naive, deconf)

    return {
        "round": target_round, "skipped": False,
        "event": str(tgt["Event"].iloc[0]),
        "lambda_fuel": lam, "lambda_se": fr.notes.get("fuel_se"),
        "lambda_events": fr.notes.get("n_events"),
        "practice_laps": int(len(prac)), "practice_runs": int(prac["RunId"].nunique()),
        "shape": shape, "steps": steps, "step_rows": step_rows,
        "naive": naive, "pitwall": deconf,
    }


def validate_season(season: pd.DataFrame, **kw) -> tuple[pd.DataFrame, pd.DataFrame, list[dict]]:
    """Leave-one-event-out validation. Returns (shape_long, steps_long, results)."""
    shape_rows, step_rows, results = [], [], []
    for rnd in sorted(season["Round"].unique()):
        out = validate_event(season, int(rnd), **kw)
        results.append(out)
        if out.get("skipped"):
            print(f"[R{rnd:02d}] skipped: {out['reason']}")
            continue

        msg = f"[R{rnd:02d}] {out['event'][:24]:24s}"
        if not out["shape"].empty:
            t = out["shape"].set_index("method")["rmse_s"]
            msg += "  shape " + " ".join(f"{m.split()[0]}={v:.3f}" for m, v in t.items())
            for _, r in out["shape"].iterrows():
                shape_rows.append({"round": rnd, "event": out["event"], **r.to_dict()})
        if not out["steps"].empty:
            t = out["steps"].set_index("method")["rmse_s"]
            msg += " | step " + " ".join(f"{m.split()[0]}={v:.3f}" for m, v in t.items())
            for _, r in out["steps"].iterrows():
                step_rows.append({"round": rnd, "event": out["event"], **r.to_dict()})
        print(msg)

    return pd.DataFrame(shape_rows), pd.DataFrame(step_rows), results


def pool(long: pd.DataFrame) -> pd.DataFrame:
    """Pool per-event results, weighted by observation count."""
    if long.empty:
        return pd.DataFrame()
    g = long.groupby("method")
    cols = {
        "events": g["round"].nunique(),
        "n": g["n"].sum(),
        "rmse_s": np.sqrt(g.apply(lambda d: np.average(d["rmse_s"] ** 2, weights=d["n"]))),
        "mae_s": g.apply(lambda d: np.average(d["mae_s"], weights=d["n"])),
    }
    if "calib_slope" in long.columns:
        cols["calib_slope"] = g.apply(
            lambda d: np.average(d["calib_slope"].fillna(0.0), weights=d["n"]))
    out = pd.DataFrame(cols).reset_index()
    base = float(out.loc[out["method"] == "B0 flat", "rmse_s"].iloc[0])
    out["vs_flat_pct"] = (1.0 - out["rmse_s"] / base) * 100.0
    return out.sort_values("method")
