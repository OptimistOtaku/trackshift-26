"""Per-lap degradation trajectory, fitted on race stints and validated against the stops.

WHY THIS MODULE EXISTS. `stopvalue.py` is cross-sectional: one row per pit stop, one scalar
out. It answers "what is a fresh tyre worth at this stop" and nothing else. There is no
per-lap state, so there is nothing a live race simulation can step forward. The product
claim is tyre degradation *intelligence*, and a scalar per stop is a thin reading of that.

`degradation.fit_race` already fits the thing we need - per-compound linear and quadratic
tyre-age terms on race laps, with driver fixed effects, fuel, traffic and track evolution -
but every caller in the repo uses it only to pull `lambda_fuel` out and throws the curves
away. Nobody has ever asked whether those race curves reproduce the 288 measured pit-stop
steps. That is the question this module answers, because it is the gate: if the trajectory
cannot reproduce the steps, it has no business driving a simulation, and saying so is a
fourth negative result rather than a failure.

WHY IT MIGHT WORK WHERE PRACTICE FAILED. The practice route died at calibration +0.006
(`validate.py`). The reason was specific to practice: inside a practice run the car burns
one lap of fuel for every lap the tyre ages, so fuel and age are collinear and the age
slope absorbs the fuel effect. Two things are different here.

  1. Fuel is separable. Race stints begin at many different fuel loads, so the same tyre
     age is seen light and heavy. That is the same argument that identifies lambda in the
     first place, applied to the age terms instead.
  2. The compound offset is identified. In a race one driver runs MEDIUM and then HARD
     under a FIXED driver dummy, so the level difference between those stints is
     attributable to the compound. Practice can never do this: every run is a single
     compound, so the run intercept absorbs the compound level entirely, and the practice
     curve carries wear only. Since the compound change is most of the +1.26 s/lap step -
     not the wear - a practice curve was always missing the larger half of the quantity.

So the race fit predicts a step from lap-time data alone, and the step is measured
independently. That makes this a real out-of-sample test with an unusually clean identity
behind it, rather than a curve admired in sample.

THE IDENTITY BEING TESTED. For one driver at one event, across their own pit stop, the
driver and event fixed effects cancel, leaving

    step = [phi(c_old, age_old) - phi(c_new, age_new)]      wear carried off vs carried on
         + [cmp(c_old) - cmp(c_new)]                        which rubber is fitted
         + lambda * (fuel_old - fuel_new)                   heavier car is slower
         + rho   * (close_old - close_new)                  traffic either side

Every term on the right is estimated from race LAP times. The left side is measured from
the pace either side of the stop. Nothing on the right was fitted to the left.
"""
from __future__ import annotations

import glob
import json
import os

import numpy as np
import pandas as pd

from .degradation import Fit, fit_race

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
FRAME_DIR = os.path.join(_ROOT, "data", "frames")
DEMO_INDEX = os.path.join(_ROOT, "artifacts", "demo", "index.json")


def _slug(s: str) -> str:
    """Must match `pipeline._slug` exactly, or the round mapping silently misses."""
    return "".join(c if c.isalnum() else "_" for c in s).strip("_").lower()


def load_season_offline(year: int = 2026) -> pd.DataFrame:
    """Rebuild the season frame from cached parquet, with no network call.

    `pipeline.build_season` is the real loader, but it calls `completed_events`, which hits
    the FastF1 schedule endpoint. That is wrong for this module on two counts: we do not
    want a network dependency in an experiment we may run on a venue's wifi, and
    `completed_events` now returns round 13 (Italian GP, raced 2026-09-06), which has no
    cached frame and would quietly change every headline number away from the deck's.

    Two steps in `build_season` are NOT optional and are the reason a plain
    `pd.concat(parquet files)` gives wrong answers:

      - `Round` is written as 0 into every parquet and filled in only by `build_season`.
        Left at 0, `pit_steps` groups the whole season under one round, pairs the last run
        of one event with the first run of the next, and calls the difference a pit stop.
      - `RunId` is unique only within a session. Left alone, run dummies and cluster groups
        merge different cars' stints across events.

    Skipping them yields 85 stops at mean -1.06 s/lap (sd 9.7) instead of 288 at +1.26
    (sd 1.03), with `fuel_old` below `fuel_new` - a car that gained fuel at its pit stop.
    The rounds are pinned to `artifacts/demo/index.json` so this frame and the exported
    demo always describe the same twelve races.
    """
    with open(DEMO_INDEX, encoding="utf-8") as f:
        want = {_slug(r["event"]): int(r["round"]) for r in json.load(f)["races"]}

    frames = []
    for path in sorted(glob.glob(os.path.join(FRAME_DIR, f"{year}_*.parquet"))):
        slug = os.path.basename(path)[len(f"{year}_"):-len(".parquet")]
        rnd = want.get(slug)
        if rnd is None:
            continue                      # a cached event the demo does not ship
        df = pd.read_parquet(path)
        df["Round"] = rnd
        frames.append(df)

    if len(frames) != len(want):
        got = len(frames)
        raise RuntimeError(f"expected {len(want)} cached events, found {got}. "
                           "Run scripts/build_season.py before this.")

    season = pd.concat(frames, ignore_index=True)
    season["RunId"] = (season["Round"].astype(str) + "|"
                       + season["Session"].astype(str) + "|" + season["RunId"])
    return season


def race_step_prediction(fit: Fit, st: pd.DataFrame, *,
                         use_compound: bool = True,
                         use_fuel: bool = True,
                         use_traffic: bool = True) -> np.ndarray:
    """Predict the pit-stop step from a race fit's per-lap coefficients.

    This is the identity in the module docstring. The flags exist so the ablation runs
    through this one code path instead of a re-implementation - turning `use_compound` off
    is what reproduces "a practice-style curve that carries wear only", which is the
    comparison that shows where the transfer actually comes from.

    `clip=True` on the curve matters more here than anywhere else: race stints reach tyre
    age 40+ while the quadratic was fitted over a narrower range, and an unclipped
    quadratic evaluated at age 45 is not a degradation estimate, it is an extrapolation
    artefact with the wrong sign.
    """
    def phi(compounds: pd.Series, ages: pd.Series) -> np.ndarray:
        z = np.zeros(len(st), float)
        for c in fit.compounds:
            m = (compounds == c).to_numpy()
            if m.any():
                z[m] = fit.curve(c, ages[m].to_numpy(float), clip=True)
        return z

    z = phi(st["c_old"], st["age_old"]) - phi(st["c_new"], st["age_new"])

    if use_compound:
        # cmp[c] is the level of compound c relative to fit.compounds[0]; the reference
        # compound has no dummy and so scores 0.0, which `_b` returns for a missing name.
        off = {c: float(fit.res.params.get(f"cmp[{c}]", 0.0)) for c in fit.compounds}
        z = z + (st["c_old"].map(off).fillna(0.0).to_numpy(float)
                 - st["c_new"].map(off).fillna(0.0).to_numpy(float))
    if use_fuel and fit.lambda_fuel is not None and np.isfinite(fit.lambda_fuel):
        z = z + fit.lambda_fuel * st["d_fuel"].to_numpy(float)
    if use_traffic:
        rho = float(fit.res.params.get("frac_close", 0.0))
        z = z + rho * np.nan_to_num(st["d_close"].to_numpy(float))
    return z


def _metrics(obs: np.ndarray, pred: np.ndarray) -> dict:
    err = pred - obs
    p = pred - pred.mean()
    v = float(p @ p)
    return {
        "rmse_s": float(np.sqrt(np.mean(err ** 2))),
        "mae_s": float(np.mean(np.abs(err))),
        "bias_s": float(err.mean()),
        # Slope of observed on predicted. 1.0 = magnitudes right. This is the number that
        # killed the practice curve (+0.006), so it is the one to read first.
        "calib_slope": float(p @ (obs - obs.mean()) / v) if v > 1e-9 else np.nan,
        "n": int(len(obs)),
    }


def loo_race_curve(season: pd.DataFrame, stops: pd.DataFrame, *,
                   specs: dict | None = None) -> pd.DataFrame:
    """Score the race trajectory against the measured steps, leave-one-event-out.

    For each event: fit the race curves on every OTHER event's race laps, then predict that
    event's stops. The fit never sees the race it is scored on, so no stop contributes to
    the coefficients that predict it.

    The baselines are the honest ones. "zero" is the null that a stop buys nothing; "season
    mean" is the same baseline `stopvalue.loo_evaluate` uses, scored through this same loop
    so the two are comparable rather than merely adjacent numbers.
    """
    specs = specs or {
        "wear only (no compound)": dict(use_compound=False, use_fuel=True, use_traffic=True),
        "wear + compound":         dict(use_compound=True, use_fuel=True, use_traffic=True),
        "+ fuel, no traffic":      dict(use_compound=True, use_fuel=True, use_traffic=False),
    }

    race = season.loc[season["IsRace"]]
    got: dict[str, list[np.ndarray]] = {k: [] for k in specs}
    obs_all, mean_base, per_event = [], [], []

    for rnd in sorted(stops["Round"].unique()):
        test = stops.loc[stops["Round"] == rnd]
        train_laps = race.loc[race["Round"] != rnd]
        train_stops = stops.loc[stops["Round"] != rnd]
        if len(test) < 5 or train_laps["Round"].nunique() < 3:
            continue
        try:
            fit = fit_race(train_laps)
        except ValueError:
            continue
        # only stops whose both compounds the fit actually saw
        m = test["c_old"].isin(fit.compounds) & test["c_new"].isin(fit.compounds)
        test = test.loc[m]
        if len(test) < 5:
            continue

        o = test["step_obs"].to_numpy(float)
        obs_all.append(o)
        mean_base.append(np.full(len(o), float(train_stops["step_obs"].mean())))
        row = {"round": int(rnd), "n": int(len(o))}
        for name, kw in specs.items():
            p = race_step_prediction(fit, test, **kw)
            got[name].append(p)
            row[name] = float(np.sqrt(np.mean((p - o) ** 2)))
        per_event.append(row)

    if not obs_all:
        return pd.DataFrame()

    obs = np.concatenate(obs_all)
    rows = [{"spec": "zero (a stop buys nothing)", **_metrics(obs, np.zeros_like(obs))},
            {"spec": "season mean", **_metrics(obs, np.concatenate(mean_base))}]
    for name in specs:
        rows.append({"spec": name, **_metrics(obs, np.concatenate(got[name]))})

    out = pd.DataFrame(rows)
    base = float(out.loc[out["spec"] == "season mean", "rmse_s"].iloc[0])
    out["vs_mean_pct"] = (1.0 - out["rmse_s"] / base) * 100.0
    out.attrs["per_event"] = pd.DataFrame(per_event)
    return out


# ------------------------------------------------------------------------- #
# the hybrid: trajectory as a feature, calibrated by the stop model
# ------------------------------------------------------------------------- #

def loo_hybrid(season: pd.DataFrame, stops: pd.DataFrame) -> pd.DataFrame:
    """Add the trajectory's prediction to the stop model as one regressor.

    WHY THIS IS THE RIGHT WAY TO USE A PARTIAL RESULT. Scored alone the trajectory lands at
    calibration 0.387 with a -0.54 s bias: it ranks stops with real signal but its magnitude
    is compressed, and its RMSE (1.18) is worse than the season mean (1.08). That is not a
    number to put on screen. It is, however, exactly the profile of a useful FEATURE - the
    ordering carries information and a single fitted coefficient can rescale it.

    So `traj` enters the cross-sectional model as one column and the stop model supplies the
    level. If the fitted coefficient on it is near 1.0 the trajectory was already on the
    right scale; if it is near 2.6 the compression is being corrected; if the RMSE does not
    improve, the trajectory told us nothing the compound pair did not already say, and that
    is the answer.

    NESTING, AND WHY IT MATTERS. For each held-out event, BOTH stages are refitted on the
    other events only: the race curves that build `traj`, and the stop model that weights it.
    A single-stage version - build `traj` once on all twelve races, then LOO the stop model -
    would leak the held-out event's lap times into its own prediction through the curves.
    The gain would be real-looking and wrong, which is the failure mode this whole project
    is about. It costs 11 extra race fits and that is a fair price.
    """
    import statsmodels.api as sm

    race = season.loc[season["IsRace"]]
    rounds = sorted(stops["Round"].unique())
    preds: dict[str, list[np.ndarray]] = {"deployed": [], "hybrid": [], "traj alone": []}
    obs_all, per_event = [], []

    for rnd in rounds:
        test = stops.loc[stops["Round"] == rnd]
        train = stops.loc[stops["Round"] != rnd]
        if len(test) < 5 or train["Round"].nunique() < 3:
            continue
        try:
            # curves fitted WITHOUT the held-out race - this is the join that must not leak
            fit = fit_race(race.loc[race["Round"] != rnd])
        except ValueError:
            continue
        m = test["c_old"].isin(fit.compounds) & test["c_new"].isin(fit.compounds)
        test = test.loc[m]
        if len(test) < 5:
            continue

        # the same trajectory prediction, evaluated on train and test alike
        tr_train = race_step_prediction(fit, train)
        tr_test = race_step_prediction(fit, test)

        pairs = sorted(train["pair"].unique())
        tt_mean = float(train["tt"].mean())

        def design(d: pd.DataFrame, traj: np.ndarray, *, with_traj: bool) -> pd.DataFrame:
            X = pd.DataFrame(index=d.index)
            for p in pairs[1:]:
                X[f"p[{p}]"] = (d["pair"] == p).astype(float)
            X["tt_c"] = d["tt"].astype(float) - tt_mean
            X["d_close"] = d["d_close"].astype(float)
            if with_traj:
                X["traj"] = traj
            return X

        o = test["step_obs"].to_numpy(float)
        obs_all.append(o)
        row = {"round": int(rnd), "n": int(len(o))}

        for name, with_traj in (("deployed", False), ("hybrid", True)):
            Xtr = sm.add_constant(design(train, tr_train, with_traj=with_traj),
                                  has_constant="add")
            res = sm.OLS(train["step_obs"].astype(float), Xtr).fit(
                cov_type="cluster", cov_kwds={"groups": train["Round"].to_numpy()})
            Xte = sm.add_constant(design(test, tr_test, with_traj=with_traj),
                                  has_constant="add").reindex(
                columns=res.params.index, fill_value=0.0)
            p = res.predict(Xte).to_numpy(float)
            preds[name].append(p)
            row[name] = float(np.sqrt(np.mean((p - o) ** 2)))
            if with_traj:
                row["b_traj"] = float(res.params.get("traj", np.nan))
        preds["traj alone"].append(tr_test)
        row["traj alone"] = float(np.sqrt(np.mean((tr_test - o) ** 2)))
        per_event.append(row)

    if not obs_all:
        return pd.DataFrame()

    obs = np.concatenate(obs_all)
    rows = [{"spec": "season mean",
             **_metrics(obs, np.full(len(obs), float(stops["step_obs"].mean())))}]
    for name in ("traj alone", "deployed", "hybrid"):
        rows.append({"spec": name, **_metrics(obs, np.concatenate(preds[name]))})
    out = pd.DataFrame(rows)
    base = float(out.loc[out["spec"] == "season mean", "rmse_s"].iloc[0])
    out["vs_mean_pct"] = (1.0 - out["rmse_s"] / base) * 100.0
    out.attrs["per_event"] = pd.DataFrame(per_event)
    return out
