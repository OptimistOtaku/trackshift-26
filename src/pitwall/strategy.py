"""From "what is a fresh tyre worth" to a decision an engineer can act on - and a hard limit
on which decisions this data can support.

WHY THIS IS NOT A RACE-STRATEGY OPTIMISER, AND WHY THAT IS THE HONEST ANSWER.

The first version of this module tried to choose a pit lap by minimising total race time over
candidate strategies. It does not work, and the reason is worth writing down because it is the
same reason the practice curve failed in `validate.py`.

Minimising race time needs the per-lap pace of a stint that was never run - pace at tyre age
`a` on a compound this driver did not fit. Two things go wrong when you try to get it here:

  1. Pooling compounds. `fit_degradation` recovers the age effect within a compound pair, so
     it is the *pure* wear effect: at most 0.56 s/lap at saturation. But the measured mean step
     is +1.26 s/lap. The difference is the compound change itself. In F1 the value of a stop is
     mostly which tyre you fit, not how worn the old one was.

  2. Adding the compound level back. With a constant per-lap benefit L for fitting a quicker
     tyre, total gain grows with laps remaining, so the objective falls monotonically in the
     pit lap and the optimiser recommends stopping on lap one. What prevents that in reality is
     that quicker compounds wear faster - a compound-SPECIFIC degradation rate. Interacting age
     with compound over 288 stops and three compounds is not identified: the old tyre's
     compound is nearly determined by where in the race the stint sits, so the interaction is
     collinear with stint position.

So the full-race optimum is not identified from this data, and the module says so rather than
shipping a number that looks like an answer. Everything below is restricted to horizons short
enough that only measured quantities enter.

AND THE PIT WINDOW DOES NOT SURVIVE EITHER. This is the second negative result and it was
found by trying to validate the window rather than by admiring it, so it is written down here
next to the code that produces it.

`agreement` scores the window against all 288 measured stops, leave-one-event-out. It covers
66.9% of the laps teams actually chose, with a window spanning 47% of the race. That sounds
like a result. It is not:

    PITWALL window placement       66.9%
    width-matched random window    54.2%   (p < 0.0001, 2000 permutations)
    width-matched MID-RACE window  66.2%   <- the whole problem

Placement beats random, so the window is not pure width. But it does not beat "pit halfway
through the race", and per event the mid-race constant tracks the median chosen lap BETTER
than the window centre does (r=+0.72 vs +0.62, MAE 4.8 vs 8.8 laps). Divide race length out
and the window centre carries no information about where in the race teams stopped at all
(r=+0.04, p=0.91).

The cause is structural, not a tuning problem. `dL` does not depend on when it is taken, so
neither edge of the window is set by tyre physics: the early edge is stint feasibility and the
late edge is laps-left-to-repay, and both are arithmetic on race length. A quantity built from
race length reproduces "mid-race" because that is all it knows. `pit_window` is kept because
the payback number inside it is real and useful on its own, but it is NOT reported as a
recommendation and the coverage figure is NOT quoted as validation.

WHAT IS IDENTIFIED, THEN. One question - and it is the one actually asked on a pit wall, into a
radio, with the rival's gap on the screen:

  UNDERCUT  I stop now, they respond k laps later. Do I come out ahead?

            This is the claim that survives, and it survives because of what it does NOT touch.
            The pit loss cancels - both cars serve the same pit lane - so no pit-loss estimate
            enters. Race length never enters, so it cannot decay into "mid-race". The horizon
            is one to eight laps, where the data is densest: most stops in the sample fit a
            tyre about three laps old, so ages 0-15 carry the most observations.

            What it reduces to is the validated step itself: RMSE 0.95 s/lap out of sample,
            calibration slope 0.82, +11.9% on a season-mean baseline. The undercut is that
            number put to work, not a new model layered on top of it.

  PAYBACK   how many laps on the new tyre before the stop repays its own pit loss. Reported as
            a diagnostic, not a recommendation - see above.

THE INGREDIENTS, ALL MEASURED.

  pit loss   `build_pitloss.py`, from the in-laps and out-laps that `clean_laps` discards.
             21.75 s season median, 20.1-23.7 s across circuits after shrinkage.
  the step   `stopvalue.fit_stop_value`, the specification that scores +11.9% RMSE out of
             sample against a season-mean baseline. This supplies the LEVEL.
  the shape  `fit_degradation`, the age terms of the same fit. This supplies how the advantage
             DECAYS as the new tyre ages.

THE SATURATION IS THE ROUND 1 FINDING, NOT A PATCH. The fitted quadratic has b2 < 0, so past
its peak (about 21 laps) it bends down and would claim a tyre gets faster as it wears - the
very sign error this project exists to point at. Past the peak phi is held FLAT. Degradation
accumulates for roughly twenty laps and then stops accumulating; and the region beyond the
peak is where `stopvalue.py` warns that drivers nursing a tyre contaminate the sample, so
flattening there is also the conservative reading.

NO SAFETY-CAR PROBABILITY IS FITTED. Twelve races at twelve different circuits is one
observation per circuit. `sc_sensitivity` takes the probability as an argument and reports how
the answer moves, which is the most this season can support.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
import statsmodels.api as sm

from .stopvalue import MIN_TRAIN_EVENTS, SPECS, fit_stop_value

DECISION_SPEC = SPECS["+ age (curved)"]
LEVEL_SPEC = SPECS["pair+temp+traffic"]

# Reference age of a newly fitted tyre. `pit_steps` averages the first three clean laps of a
# stint, so a "fresh" tyre in this sample is about three laps old, and the measured step is
# phi(a_old) - phi(3) rather than phi(a_old) - phi(0).
FRESH_AGE = 3.0


# ------------------------------------------------------------------------- #
# the shape: how the advantage decays as the new tyre ages
# ------------------------------------------------------------------------- #

@dataclass
class Degradation:
    """Pace lost to tyre age, in seconds per lap, measured from race pit stops.

    Defined up to an additive constant, which cancels in every difference taken below.
    Saturating: beyond `peak` the value is held at its maximum rather than allowed to decline.
    """
    b1: float
    b2: float
    peak: float
    max_age_seen: float

    def phi(self, a: np.ndarray | float) -> np.ndarray:
        a = np.clip(np.asarray(a, float), 0.0, self.peak)
        return self.b1 * a + self.b2 * a ** 2

    def marginal(self, a: np.ndarray | float) -> np.ndarray:
        """Extra pace lost by running one more lap at age `a`. Zero past saturation."""
        a = np.asarray(a, float)
        m = self.b1 + 2.0 * self.b2 * np.clip(a, 0.0, self.peak)
        return np.where(a >= self.peak, 0.0, m)

    def extrapolating(self, age: float) -> bool:
        """True if `age` is older than any tyre a measured stop came off."""
        return bool(age > self.max_age_seen)


def fit_degradation(stops: pd.DataFrame) -> Degradation:
    """Recover phi from the age terms of the stop-value fit.

    Compound-pair fixed effects, so this is the within-pair age effect - the same
    specification `stopvalue.age_test` reports, refitted here so the engine and the reported
    test can never drift apart.
    """
    X = pd.get_dummies(stops["pair"], drop_first=True).astype(float)
    a = stops["age_old"].to_numpy(float)
    X["age_new"] = stops["age_new"].to_numpy(float)
    X["age_old"] = a
    X["age_old2"] = a ** 2
    res = sm.OLS(stops["step_obs"].astype(float), sm.add_constant(X)).fit(
        cov_type="cluster", cov_kwds={"groups": stops["Round"].to_numpy()})

    b1 = float(res.params["age_old"])
    b2 = float(res.params["age_old2"])
    # A positive b2 would mean degradation accelerating without limit, which nothing in the
    # data supports and which would make every horizon unbounded. Saturate at the oldest
    # observed tyre instead of at a peak that does not exist.
    peak = (-b1 / (2.0 * b2)) if b2 < 0 else float(a.max())
    return Degradation(b1=b1, b2=b2, peak=float(peak), max_age_seen=float(a.max()))


# ------------------------------------------------------------------------- #
# the advantage profile: level from the validated model, decay from phi
# ------------------------------------------------------------------------- #

@dataclass
class Advantage:
    """Per-lap pace advantage of a stop, as a function of laps since the stop.

    `step0` is the advantage on the first lap out - the quantity `stopvalue` predicts and
    validates out of sample. `deg` says how it decays as the new tyre ages while the tyre that
    was taken off would have kept ageing too.
    """
    step0: float
    age_old: float
    deg: Degradation

    @property
    def delta_level(self) -> float:
        """Pace difference between the two compounds, net of tyre age, in s/lap.

        Backed out of the validated step rather than fitted separately. The measured step is
        `dL + phi(age_old) - phi(FRESH_AGE)`, so `dL` is what remains once the age effect at
        the moment of the stop is removed. This is the part that does NOT decay - the reason a
        quicker compound stays quicker - and it is why the full-race objective is degenerate.
        """
        return float(self.step0 - self.deg.phi(self.age_old) + self.deg.phi(FRESH_AGE))

    def per_lap(self, k: np.ndarray | float) -> np.ndarray:
        """Advantage k laps after the stop, over the tyre that was taken off.

        At lap k the fitted tyre is `k` laps old and the discarded one would have been
        `age_old + k`. Pinned so that k = FRESH_AGE reproduces the validated step.
        """
        k = np.asarray(k, float)
        return self.delta_level + self.deg.phi(self.age_old + k) - self.deg.phi(k)

    def cumulative(self, laps: int) -> float:
        if laps <= 0:
            return 0.0
        return float(np.sum(self.per_lap(np.arange(1, int(laps) + 1, dtype=float))))


def advantage(deg: Degradation, step0: float, age_old: float) -> Advantage:
    return Advantage(step0=float(step0), age_old=float(age_old), deg=deg)


# ------------------------------------------------------------------------- #
# payback: the window with both ends measured
# ------------------------------------------------------------------------- #

def payback_laps(adv: Advantage, pit_loss: float, max_laps: int = 90) -> int | None:
    """Laps on the new tyre before the stop has paid for its own pit loss.

    `None` means it never pays inside `max_laps` - the old tyre was not worn enough, or the
    compound on offer is not quick enough, to earn back the time spent in the pit lane.
    """
    total = 0.0
    for k in range(1, int(max_laps) + 1):
        total += float(adv.per_lap(float(k)))
        if total >= pit_loss:
            return k
    return None


def pit_window(deg: Degradation, *, step_at, age_at, race_laps: int, pit_loss: float,
               max_stint: float, first_lap: int = 2) -> pd.DataFrame:
    """Every candidate pit lap, with the two constraints that actually bind.

    `step_at(lap)` gives the validated first-lap advantage for a stop made on that lap and
    `age_at(lap)` the age the old tyre would have reached. A lap survives when BOTH hold:

      LATE SIDE   the stop pays back its own pit loss before the race ends. Stop too late and
                  there is no time left to earn the pit lane back. Measured: pit loss from
                  `build_pitloss.py`, advantage from the validated stop-value model.

      EARLY SIDE  the stint that follows is one this season has actually seen. Stop too early
                  and you must run more laps on one set than any car in the sample managed
                  (`max_stint`, the oldest tyre observed). Beyond that the model is
                  extrapolating and says so.

    The early side needs saying because the payback test alone does NOT close it. The
    compound-level benefit `dL` does not depend on when you take it, so payback is nearly flat
    in tyre age and ranking laps by it recommends lap two. That is not a finding about racing,
    it is the identification limit from the module docstring showing through. The honest early
    bound is the range of the data, not a simulated stint.

    No optimal lap is reported. The window is the output.
    """
    rows = []
    for lap in range(int(first_lap), int(race_laps) + 1):
        a = float(age_at(lap))
        remaining = int(race_laps) - lap
        adv = advantage(deg, float(step_at(lap)), a)
        pb = payback_laps(adv, pit_loss, max_laps=max(remaining, 1))
        pays = pb is not None and pb <= remaining
        viable = remaining <= float(max_stint)
        rows.append({
            "lap": lap,
            "age_old": a,
            "laps_remaining": remaining,
            "step0_s_per_lap": float(adv.step0),
            "delta_level_s": float(adv.delta_level),
            "payback_laps": pb,
            "pays_back": pays,
            "stint_viable": viable,
            "in_window": bool(pays and viable),
            "cum_gain_s": adv.cumulative(remaining),
            "extrapolating": deg.extrapolating(a),
        })
    return pd.DataFrame(rows)


def summarise_window(d: pd.DataFrame) -> dict:
    """The window as the demo and the deck quote it."""
    if d.empty:
        return {}
    ok = d.loc[d["in_window"], "lap"]
    if ok.empty:
        return {"has_window": False,
                "reason": "no lap both pays back its pit loss and leaves a stint this "
                          "season has seen"}
    w = d.loc[d["in_window"]]
    return {
        "has_window": True,
        "open_lap": int(ok.min()),
        "close_lap": int(ok.max()),
        "open_limited_by": "stint length seen in data",
        "close_limited_by": "laps left to pay back the pit loss",
        "fastest_payback_laps": int(w["payback_laps"].min()),
        "step_s_per_lap": float(w["step0_s_per_lap"].median()),
    }



# ------------------------------------------------------------------------- #
# undercut: the ten-lap question
# ------------------------------------------------------------------------- #

def undercut(deg: Degradation, *, step0: float, age_mine: float, age_theirs: float,
             gap_s: float, laps: int = 8) -> pd.DataFrame:
    """The undercut, lap by lap: I stop now, they respond `k` laps later. Do I come out ahead?

    THE PIT LOSS CANCELS, and this is the whole reason undercuts work. Both cars serve the same
    pit lane at the same circuit, so the ~22 s is paid by each of us and drops out of the
    difference. What is left is only the laps between my stop and their response, run by me on
    a fresh tyre and by them on a worn one. At Austria that is worth about 1.8 s on the first
    lap - so a rival within 1.8 s who responds immediately is still caught.

    This is why the earlier framing of this function was wrong. Asking whether the stop earns
    back the full pit loss before the rival reacts is the payback question, not the undercut
    question, and it answers "sixteen laps" where the real answer is "one".

    `gap_s` is where I am now: positive means behind. Returns one row per response lap `k`,
    with the gap once they emerge from their own stop.

    THE ASSUMPTION: the rival is a car of equal intrinsic pace on the compound I just took off,
    ageing from `age_theirs`. Exactly right in the ordinary undercut fight - two cars on the
    same compound at a similar age, one blinks first - and it degrades gracefully as the ages
    diverge. It cannot handle a rival on a fundamentally different compound, because a
    compound-specific wear rate is not identified here (see the module docstring).

    THE COST IT DOES NOT HIDE: undercutting leaves me `k` laps further into my tyre life than
    the car I just passed, so `tyre_deficit_laps` is the ground I have to hold afterwards.
    """
    adv = advantage(deg, step0, age_mine)
    dL = adv.delta_level
    rows, gained = [], 0.0
    for k in range(1, int(laps) + 1):
        # laps k-1 -> k: I am on a tyre k laps old, they are on one age_theirs + k
        gained += dL + float(deg.phi(age_theirs + k)) - float(deg.phi(k))
        rows.append({
            "they_respond_after_laps": k,
            "time_gained_s": gained,
            "gap_after_s": float(gap_s) - gained,
            "ahead": (float(gap_s) - gained) < 0.0,
            "tyre_deficit_laps": k,
        })
    return pd.DataFrame(rows)


def summarise_undercut(d: pd.DataFrame, *, gap_s: float) -> dict:
    """Does the undercut work, and how long the rival has to stay out for it to."""
    if d.empty:
        return {}
    ahead = d.loc[d["ahead"], "they_respond_after_laps"]
    return {
        "gap_before_s": float(gap_s),
        "works": bool(not ahead.empty),
        "needs_them_out_for_laps": int(ahead.min()) if not ahead.empty else None,
        "gain_first_lap_s": float(d["time_gained_s"].iloc[0]),
        "max_gap_undercuttable_in_1_lap_s": float(d["time_gained_s"].iloc[0]),
        "tyre_deficit_laps": int(ahead.min()) if not ahead.empty else None,
    }



def sc_sensitivity(deg: Degradation, *, step_at, age_at, race_laps: int, pit_loss: float,
                   max_stint: float, p_sc: float, sc_discount: float = 0.6) -> dict:
    """How the window moves if a safety car is expected. A sensitivity, not a prediction.

    A safety car makes a stop cheaper because the field is slowed while you serve it;
    `sc_discount` is the fraction of the pit loss that survives. `p_sc` is supplied by the
    caller and NEVER fitted - twelve races at twelve circuits is one observation per circuit,
    so a per-circuit safety-car rate is not estimable from this season. Feeding an
    unmeasurable probability into an optimiser and reporting the output as an answer is the
    failure mode this whole project is about.

    Note the asymmetry the output shows: a cheaper stop moves the LATE side of the window
    (there is less to pay back, so you can leave it longer) and leaves the early side where it
    was, because the early side is a stint-length limit and a safety car does not change how
    long a set of tyres lasts.
    """
    eff = float(pit_loss) * ((1.0 - p_sc) + p_sc * sc_discount)
    d = pit_window(deg, step_at=step_at, age_at=age_at, race_laps=race_laps,
                   pit_loss=eff, max_stint=max_stint)
    return {"p_sc": float(p_sc), "effective_pit_loss_s": round(eff, 2),
            **summarise_window(d)}


def max_stint_laps(season: pd.DataFrame, *, quantile: float = 1.0) -> float:
    """The longest stint this season actually ran, which bounds the early side of the window.

    Taken from race laps only. Practice long runs are not stints - they end when the engineer
    says so, not when the tyre is finished - so they say nothing about how long a set can be
    asked to last in a race. The default is the outright maximum because the claim the bound
    makes is "a car has done this", which one observation is enough to establish; pass a
    quantile for a more conservative bound.
    """
    race = season.loc[season["IsRace"]]
    per = race.groupby(["Round", "Driver", "Stint"])["TyreAge"].max()
    return float(per.max() if quantile >= 1.0 else per.quantile(quantile))


# ------------------------------------------------------------------------- #
# validation: does the window contain the lap the pit wall actually chose?
# ------------------------------------------------------------------------- #

def agreement(stops: pd.DataFrame, season: pd.DataFrame,
              pit_loss: dict[int, float], *, loo: bool = True) -> pd.DataFrame:
    """Score the window against 288 real decisions made by people with far more information.

    For every measured stop, rebuild the window the engine would have offered before it and
    ask whether the lap the team chose falls inside. Leave-one-event-out by default: the model
    scoring a stop at Silverstone has never seen Silverstone.

    THIS TEST IS THE REASON THE WINDOW IS NOT THE PRODUCT. It returns 66.9% coverage, which
    looks like a pass until you race it against a width-matched window placed mid-race, which
    returns 66.2%. Run `scripts/check_window_placebo.py` for the full comparison. Kept in the
    codebase because a metric that killed a feature is worth more than one that flattered it,
    and because any future change to the window has to beat the same placebo.

    Coverage is only ever meaningful next to `width`: a window spanning the whole race covers
    everything and has learned nothing. Both are returned per stop.
    """
    race_laps = (season.loc[season["IsRace"]].groupby("Round")["LapNumber"].max()
                 .astype(int).to_dict())
    rows = []
    for rnd, held in stops.groupby("Round"):
        train = stops.loc[stops["Round"] != rnd] if loo else stops
        if train["Round"].nunique() < MIN_TRAIN_EVENTS:
            continue
        deg = fit_degradation(train)
        model = fit_level_model(train)
        ms = max_stint_laps(season.loc[season["Round"] != rnd] if loo else season)
        n_laps = race_laps.get(int(rnd))
        pl = pit_loss.get(int(rnd))
        if n_laps is None or pl is None:
            continue

        for _, s in held.iterrows():
            chosen, age = int(s["PitLap"]), float(s["age_old"])
            start = max(chosen - int(round(age)), 1)
            step_at, age_at = S_scenario(model, s, start_lap=start)
            d = pit_window(deg, step_at=step_at, age_at=age_at, race_laps=n_laps,
                           pit_loss=pl, max_stint=ms, first_lap=start + 1)
            w = summarise_window(d)
            if not w.get("has_window"):
                rows.append({"Round": int(rnd), "Driver": s["Driver"], "PitLap": chosen,
                             "has_window": False, "inside": False})
                continue
            rows.append({
                "Round": int(rnd), "Event": s.get("Event"), "Driver": s["Driver"],
                "PitLap": chosen, "age_old": age, "race_laps": n_laps,
                "open_lap": w["open_lap"], "close_lap": w["close_lap"],
                "width": w["close_lap"] - w["open_lap"] + 1,
                "has_window": True,
                "inside": bool(w["open_lap"] <= chosen <= w["close_lap"]),
                "laps_outside": 0 if w["open_lap"] <= chosen <= w["close_lap"]
                                else min(abs(chosen - w["open_lap"]),
                                         abs(chosen - w["close_lap"])),
            })
    return pd.DataFrame(rows)


def S_scenario(model, stop_row, *, start_lap: int):
    """`scenario` for one row of the stop table, reusing its own recorded conditions."""
    return scenario(model, pair=str(stop_row["pair"]), tt=float(stop_row["tt"]),
                    d_close=float(stop_row.get("d_close", 0.0)),
                    start_age=0, first_lap=start_lap)




def fit_level_model(stops: pd.DataFrame):
    """The validated predictor of the first-lap advantage. Supplies `step_at`."""
    return fit_stop_value(stops, LEVEL_SPEC)


def scenario(model, *, pair: str, tt: float, d_close: float = 0.0,
             start_age: int = 0, first_lap: int = 1, max_lap: int = 120):
    """Turn a fitted model plus a stint into the `(step_at, age_at)` pair `pit_window` wants.

    `start_age` is the age of the tyre at `first_lap`, so a car starting the race on new
    rubber has `start_age=0`, and one already ten laps into a stint has `start_age=10`.

    The whole lap-to-step mapping is predicted in one vectorised call and then looked up. The
    obvious per-lap implementation calls statsmodels once per candidate lap, which is fine for
    a single window and unusably slow across 288 leave-one-event-out replays.
    """
    laps = np.arange(int(first_lap), int(max_lap) + 1)
    ages = start_age + np.maximum(laps - int(first_lap), 0)
    grid = pd.DataFrame({"pair": pair, "age_old": ages.astype(float),
                         "tt": float(tt), "d_close": float(d_close)})
    steps = np.asarray(model.predict(grid), float)
    lookup = dict(zip(laps.tolist(), steps.tolist()))
    age_lookup = dict(zip(laps.tolist(), ages.astype(float).tolist()))

    def age_at(lap: int) -> float:
        return age_lookup.get(int(lap), float(start_age + max(int(lap) - int(first_lap), 0)))

    def step_at(lap: int) -> float:
        return lookup.get(int(lap), float(steps[-1]))

    return step_at, age_at
