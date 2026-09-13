"""What a fresh tyre is actually worth - modelled directly, not via a degradation curve.

This module exists because of a negative result, and the negative result is the interesting
part. `degradation.py` does the conventional thing properly: fit lap time against tyre age
on practice long runs, having first removed fuel, traffic and track evolution. That fit is
defensible in-sample - it fixes a sign error that the naive version makes. It simply does
not transfer to a race.

WHAT THE RACE DATA SAYS. The pit stop is the one place in a race where tyre age resets and
fuel does not, so the step in pace across a stop measures the tyre effect with fuel almost
entirely cancelled. Measured over 288 stops and 12 events, fitting a new tyre is worth
+1.26 s/lap on average (sd 1.03) - and the way that figure varies with tyre age is not what
a degradation curve assumes:

    linear test      -0.006 +/- 0.011 s per lap of age,  p = 0.58   <- finds nothing
    quadratic test   age +0.070 (p=0.021), age^2 -0.00164 (p=0.002), joint p = 0.005

The linear test finds nothing because the relationship turns over. The value of a stop
climbs to roughly tyre age 21-25 and then flattens and declines. So degradation is real and
does accumulate - for about the first 20 laps of a tyre's life - and then stops accumulating.
A practice-fitted quadratic that keeps climbing therefore over-values a late stop, which is
a bias in the direction of stopping too often.

Two caveats on the decline itself, since it is the least certain part: past age 30 there are
only 24 stops, and drivers who run a tyre that long were nursing it rather than pushing, so
selection plausibly explains some of the fall.

A saturating form does not rescue the practice route either. Profiled on practice data the
timescale is not identified at all - SSR falls by 0.1% between tau=3 and tau=44 laps - and
the resulting curve under-predicts the step badly (calibration -1.77).

WHAT THIS MODEL DOES INSTEAD. It predicts the decision-relevant quantity directly from race
history: the seconds per lap a driver gains by fitting a new tyre. Out of sample,
leave-one-event-out, with no free constants granted to anybody, that beats the season mean by
11.1% RMSE at a calibration slope of 0.79. The signal lives in three places:

  compound pair    which tyre is coming off and which is going on
  track temp       +0.039 s/degC (p=0.001) - a hotter track makes fresh rubber worth more
  traffic          +0.504 s (p=0.003) - measured from position telemetry, not inferred

Tyre age is NOT a regressor in the deployed model, and the reason is worth stating precisely
because it is easy to misreport. Age matters in sample: entered with curvature its terms are
jointly significant (p=0.005) and R2 rises from 0.350 to 0.382. It simply does not pay for
itself out of sample - 11.1% -> 10.3% RMSE, calibration 0.79 -> 0.73 - because the effect is
small against the stop-to-stop noise and partly redundant with what compound and temperature
already encode. `age_test` reports the effect; the model omits it.

HONEST LIMITS. The pooled gain is weighted by stop count and is carried by the larger
events; by event count the model wins at 7 of 11. Track temperature is a causal expanding
mean - each stop sees only the laps run before it, see `stop_table` - so it is a covariate
the pit wall could really hold, but that fixes only the timing problem and not the
identification one: 99.9% of its variance is still between events (within an event the
stop-to-stop spread averages 0.32 degC), so it still largely proxies for circuit identity,
and with 12 events it cannot be cleanly separated from other circuit characteristics. All of
these caveats are reported by the scripts rather than smoothed over.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
import statsmodels.api as sm

from .validate import pit_steps

# Regressor sets. `FULL` is the specification the leave-one-event-out comparison selected;
# the others exist so the ablation is run from this same code path rather than reimplemented.
SPECS: dict[str, list[str]] = {
    "mean only": [],
    "temp": ["tt"],
    "traffic": ["traf"],
    "temp+traffic": ["tt", "traf"],
    "pair+temp+traffic": ["pair", "tt", "traf"],
    "+ age (linear)": ["pair", "tt", "traf", "age"],
    "+ age (curved)": ["pair", "tt", "traf", "age", "age2"],
}
# The deployed specification. Age is left out deliberately, and the reason is not that age
# does not matter - it does, see `age_test` - but that it buys nothing out of sample
# (11.1% -> 10.3% RMSE gain, calibration 0.79 -> 0.73) while costing two parameters.
FULL = SPECS["pair+temp+traffic"]
MIN_TEST_STOPS = 5      # an event with fewer scored stops is too noisy to rank
MIN_TRAIN_EVENTS = 3    # fewer than this and the training fit is not meaningful


@dataclass
class StopValue:
    """Fitted model for the pace bought by a pit stop."""
    res: object
    spec: list[str]
    pairs: list[str]
    tt_mean: float
    n_obs: int
    notes: dict = field(default_factory=dict)

    def predict(self, stops: pd.DataFrame) -> np.ndarray:
        X = _design(stops, self.spec, self.pairs, self.tt_mean)
        X = sm.add_constant(X, has_constant="add")
        X = X.reindex(columns=self.res.params.index, fill_value=0.0)
        return self.res.predict(X).to_numpy(float)


# ------------------------------------------------------------------------- #
# building the target
# ------------------------------------------------------------------------- #

def stop_table(season: pd.DataFrame) -> pd.DataFrame:
    """One row per race pit stop, with everything the model is allowed to know.

    "Allowed to know" is meant literally, and track temperature is where it bites. This
    column used to be the event's whole-race mean, which is not a covariate a pit wall
    could ever hold: a stop on lap 10 of 71 was being described by a temperature averaged
    over laps 11-71, laps that had not been run when the call was made. In a live replay
    that is a model reading the future, and the earlier the stop the more future it reads.

    It is now the mean over that race's laps up to and including the stop lap - an
    expanding mean, recomputed at every stop. Including the stop lap itself is deliberate
    and is not a leak: `PitLap` is the last clean lap on the old tyre, so its temperature
    reading is already in hand at the moment the driver is told to box.

    Two honest consequences. The mean is taken over the laps that survived cleaning, since
    those are the rows this frame has, so a race whose opening laps were all filtered out
    starts its average later than lap 1. And an early stop now averages few laps, so its
    temperature is noisier than a late stop's - correctly so, because that is how much the
    pit wall actually knows at that point.
    """
    race = season.loc[season["IsRace"]]
    st = pit_steps(race)
    if st.empty:
        return st

    st["tt"] = _causal_track_temp(race, st)
    # A stop with no track temperature at all before it is dropped rather than filled: `tt`
    # is a level in degC, not a centred deviation, so there is no neutral value to invent.
    st = st.dropna(subset=["step_obs", "age_old", "age_new", "tt"]).copy()
    # A missing traffic reading means the position feed was unavailable, not that the car
    # was in clear air; zero is the sample mean of the centred variable, i.e. "typical".
    st["d_close"] = st["d_close"].fillna(0.0)
    return st


def _causal_track_temp(race: pd.DataFrame, st: pd.DataFrame) -> np.ndarray:
    """Mean track temperature over laps 1..PitLap of each stop's own race.

    Returned in `st` row order. Vectorised on purpose - a per-round expanding mean over lap
    number, then an as-of join onto the stops - because the loop version is 288 groupbys
    over the race frame and gets slower every time the season grows.

    Sums and counts are carried separately and divided at the end rather than averaging
    per-lap averages. Those differ whenever laps carry different numbers of cars, and the
    sum/count form is the one that matches what the leaking version computed, so the
    before/after comparison isolates the causal fix instead of also changing the weighting.
    Carrying the count also handles missing readings for free: a lap whose weather feed was
    unavailable contributes nothing to either total, exactly as `Series.mean` skips it.
    """
    lap = (race.groupby(["Round", "LapNumber"], as_index=False)
           .agg(tt_sum=("TrackTemp", "sum"), tt_n=("TrackTemp", "count"))
           .sort_values(["Round", "LapNumber"], kind="stable"))
    g = lap.groupby("Round")
    # replace(0, nan): no readings yet in this race means undefined, not zero degrees.
    lap["tt_cum"] = g["tt_sum"].cumsum() / g["tt_n"].cumsum().replace(0, np.nan)

    left = st[["Round", "PitLap"]].copy()
    left["_row"] = np.arange(len(left), dtype=int)
    # merge_asof needs both join keys globally sorted, not merely sorted within `by`.
    left = left.sort_values("PitLap", kind="stable")
    lap = lap.sort_values("LapNumber", kind="stable")

    # direction="backward": take the latest lap at or before the stop lap. An exact match is
    # the normal case; the fallback matters only if the stop lap itself was filtered out,
    # and then it uses the laps before it rather than reaching forward past the stop.
    joined = pd.merge_asof(left, lap[["Round", "LapNumber", "tt_cum"]],
                           left_on="PitLap", right_on="LapNumber", by="Round",
                           direction="backward")

    out = np.full(len(st), np.nan)
    out[joined["_row"].to_numpy(int)] = joined["tt_cum"].to_numpy(float)
    return out


def _design(d: pd.DataFrame, spec: list[str], pairs: list[str],
            tt_mean: float) -> pd.DataFrame:
    X = pd.DataFrame(index=d.index)
    if "pair" in spec:
        # drop_first: with a constant in the model, a full set of pair dummies is a
        # rank-deficient design and statsmodels will warn rather than fail.
        for p in pairs[1:]:
            X[f"p[{p}]"] = (d["pair"] == p).astype(float)
    if "age" in spec:
        X["age_old"] = d["age_old"].astype(float)
    if "age2" in spec:
        # Age enters with curvature or not at all. A linear term alone tests the wrong
        # hypothesis: the value of a stop rises to roughly age 21 and then falls, so a
        # straight line through it averages to zero and reports "no effect" (p=0.97 over
        # the dense range) while a quadratic finds the two terms jointly significant
        # (p=0.005 over the full range).
        X["age_old2"] = d["age_old"].astype(float) ** 2
    if "tt" in spec:
        X["tt_c"] = d["tt"].astype(float) - tt_mean
    if "traf" in spec:
        X["d_close"] = d["d_close"].astype(float)
    return X


# ------------------------------------------------------------------------- #
# fitting
# ------------------------------------------------------------------------- #

def fit_stop_value(stops: pd.DataFrame, spec: list[str] | None = None) -> StopValue:
    """Fit the stop-value model. Standard errors are clustered by event."""
    spec = FULL if spec is None else spec
    pairs = sorted(stops["pair"].unique())
    tt_mean = float(stops["tt"].mean())

    X = _design(stops, spec, pairs, tt_mean)
    keep = X.std(numeric_only=True) > 0
    X = X.loc[:, keep[keep].index]
    X = sm.add_constant(X, has_constant="add")
    y = stops["step_obs"].astype(float)

    # Clustered by event: stops at the same race share the safety-car history, the weather
    # and the track surface, so treating 288 stops as independent overstates precision.
    res = sm.OLS(y, X).fit(cov_type="cluster",
                           cov_kwds={"groups": stops["Round"].to_numpy()})
    return StopValue(res=res, spec=list(spec), pairs=pairs, tt_mean=tt_mean,
                     n_obs=int(len(stops)),
                     notes={"r2": float(res.rsquared),
                            "n_events": int(stops["Round"].nunique())})


# ------------------------------------------------------------------------- #
# leave-one-event-out evaluation
# ------------------------------------------------------------------------- #

def loo_evaluate(stops: pd.DataFrame, spec: list[str] | None = None) -> dict:
    """Score a specification out of sample, one event at a time.

    Every parameter - including the compound-pair effects and the intercept - is estimated
    on other events only. No free constant is granted at scoring time, unlike the stint
    and step targets in `validate.py`: here the model must get the *level* right too, which
    is the harder and more honest test.
    """
    spec = FULL if spec is None else spec
    preds, obs, per_event = [], [], []

    for rnd in sorted(stops["Round"].unique()):
        train = stops.loc[stops["Round"] != rnd]
        test = stops.loc[stops["Round"] == rnd]
        if len(test) < MIN_TEST_STOPS or train["Round"].nunique() < MIN_TRAIN_EVENTS:
            continue
        m = fit_stop_value(train, spec)
        p = m.predict(test)
        o = test["step_obs"].to_numpy(float)
        preds.append(p)
        obs.append(o)
        per_event.append({"round": int(rnd), "n": int(len(o)),
                          "rmse_s": float(np.sqrt(np.mean((o - p) ** 2)))})

    if not preds:
        return {"n": 0}
    p = np.concatenate(preds)
    o = np.concatenate(obs)
    pc, oc = p - p.mean(), o - o.mean()
    return {
        "rmse_s": float(np.sqrt(np.mean((o - p) ** 2))),
        "mae_s": float(np.mean(np.abs(o - p))),
        "bias_s": float(p.mean() - o.mean()),
        # 1.0 means the spread of predictions matches the spread of outcomes
        "calib_slope": float(pc @ oc / (pc @ pc)) if pc @ pc > 1e-9 else np.nan,
        "n": int(len(o)),
        "events": int(len(per_event)),
        "per_event": pd.DataFrame(per_event),
    }


def ablation(stops: pd.DataFrame, specs: dict | None = None) -> pd.DataFrame:
    """Out-of-sample score for each specification, against the mean-only baseline."""
    specs = SPECS if specs is None else specs
    rows = []
    for name, spec in specs.items():
        r = loo_evaluate(stops, spec)
        if r.get("n"):
            rows.append({"spec": name, "rmse_s": r["rmse_s"], "mae_s": r["mae_s"],
                         "calib_slope": r["calib_slope"], "n": r["n"]})
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    base = float(out.loc[out["spec"] == "mean only", "rmse_s"].iloc[0])
    out["vs_mean_pct"] = (1.0 - out["rmse_s"] / base) * 100.0
    return out


def age_test(stops: pd.DataFrame) -> dict:
    """Does the pace bought by a stop depend on how worn the old tyre was?

    Compound-pair fixed effects, so this is a within-pair question. It is the central
    empirical claim of the project and so is computed here rather than quoted.

    The linear and quadratic tests disagree, and the disagreement is the point. A straight
    line finds nothing (p=0.97 over the dense age range) because the true relationship turns
    over: the value of a stop climbs to roughly tyre age 21-25 and then flattens and falls.
    Testing only the linear term would have produced a confident and wrong headline. Both
    are reported, and the quadratic is the one to believe - its two terms are jointly
    significant at p=0.005.
    """
    X0 = pd.get_dummies(stops["pair"], drop_first=True).astype(float)
    a = stops["age_old"].to_numpy(float)
    X0["age_new"] = stops["age_new"].to_numpy(float)
    y = stops["step_obs"].astype(float)
    g = stops["Round"].to_numpy()

    lin = X0.copy()
    lin["age_old"] = a
    m1 = sm.OLS(y, sm.add_constant(lin)).fit(cov_type="cluster", cov_kwds={"groups": g})

    quad = lin.copy()
    quad["age_old2"] = a ** 2
    m2 = sm.OLS(y, sm.add_constant(quad)).fit(cov_type="cluster", cov_kwds={"groups": g})
    b1, b2 = float(m2.params["age_old"]), float(m2.params["age_old2"])

    return {
        # linear: the test that looks decisive and is not
        "lin_slope": float(m1.params["age_old"]),
        "lin_se": float(m1.bse["age_old"]),
        "lin_p": float(m1.pvalues["age_old"]),
        # quadratic: the specification that fits
        "quad_age": b1, "quad_age_p": float(m2.pvalues["age_old"]),
        "quad_age2": b2, "quad_age2_p": float(m2.pvalues["age_old2"]),
        "joint_p": float(m2.f_test("age_old=0, age_old2=0").pvalue),
        "peak_age": (-b1 / (2 * b2)) if b2 < 0 else np.nan,
        "mean_step_s": float(stops["step_obs"].mean()),
        "sd_step_s": float(stops["step_obs"].std()),
        "age_range": (float(stops["age_old"].min()), float(stops["age_old"].max())),
        "n": int(len(stops)), "r2_quad": float(m2.rsquared),
    }


def robustness(stops: pd.DataFrame, caps=(None, 3.0, 2.5)) -> pd.DataFrame:
    """Re-run the headline comparison under tighter outlier cuts.

    The cut is method-blind - it looks only at the observed step, never at any model
    output - so it cannot flatter the model. If the gain survives, it is not an artefact of
    a handful of extreme stops.
    """
    rows = []
    for cap in caps:
        d = stops if cap is None else stops.loc[stops["step_obs"].abs() <= cap]
        base = loo_evaluate(d, SPECS["mean only"])
        best = loo_evaluate(d, FULL)
        if not base.get("n") or not best.get("n"):
            continue
        rows.append({"cap_s": cap if cap else np.inf, "n": best["n"],
                     "mean_only_rmse": base["rmse_s"], "pitwall_rmse": best["rmse_s"],
                     "gain_pct": (1.0 - best["rmse_s"] / base["rmse_s"]) * 100.0,
                     "calib_slope": best["calib_slope"]})
    return pd.DataFrame(rows)
