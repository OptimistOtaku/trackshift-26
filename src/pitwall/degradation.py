"""The deconfounding model.

Two stages, because the fuel coefficient is identified in one place and needed in
another.

STAGE A - race. Fuel mass is a linear-burn proxy, not measured telemetry. Its scale
comes from an assumed starting load and lap number. We regress on it with driver effects but deliberately
no run intercepts. Identification comes from the fact that stints begin at different
points in the race, so the same tyre age is observed at many different fuel loads.

STAGE B - practice. Each run leaves the pits with an unknown fuel load, so every run
needs its own intercept - and once a run has an intercept, fuel and tyre age are
perfectly collinear inside that run. Nothing in the practice data can separate them.
So we import lambda from stage A, subtract the fuel effect, and what remains of the
within-run slope is degradation. Cross-run variation in *starting* tyre age (teams send
cars out on scrubbed rubber) then identifies the curvature.

CONFOUNDERS, AND WHICH ONES WE MEASURE. Three things move lap time monotonically over a
run and are therefore candidates to be mistaken for degradation: fuel burn, traffic, and
track evolution. All three are measured rather than assumed away.

  fuel        modelled from an assumed load and linear burn (stage A)
  traffic     measured from position telemetry as time spent within 1.0s of a car ahead
  evolution   measured as log rubber laid down - see `_evo_terms`

That last one was the largest single error in an earlier version of this model. With no
evolution term, the linear degradation coefficient has to absorb the green-track effect,
which on a Friday morning is large and has the opposite sign to degradation. The fit then
reports that tyres get FASTER with age - which is not a subtle bias, it is a sign error
on the headline number.

WHAT IS STILL NOT FULLY IDENTIFIED. Within a race, fuel decline and track evolution are
strongly correlated: the field laps at a near-constant rate, so rubber accumulates in
step with fuel burning off. They are separable only by shape - fuel is linear in lap
number, log rubber is concave - so the two coefficients are identified but correlated,
and their standard errors are inflated accordingly. We report both and check that lambda
is stable when the evolution term is removed, rather than claiming the problem away.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
import statsmodels.api as sm

SLICKS = ("SOFT", "MEDIUM", "HARD")
REF_AGE = 10.0  # laps; degradation rate is quoted at this tyre age


@dataclass
class Fit:
    kind: str                      # 'race' | 'practice'
    res: object                    # statsmodels results
    compounds: list[str]
    lambda_fuel: float | None      # s/kg
    n_obs: int
    n_groups: int
    design_cols: list[str] = field(default_factory=list)
    # observed tyre-age range per compound, so reporting never extrapolates
    age_support: dict = field(default_factory=dict)
    notes: dict = field(default_factory=dict)

    # -- degradation curve ------------------------------------------------- #
    def _b(self, name: str) -> float:
        return float(self.res.params.get(name, 0.0))

    def curve(self, compound: str, ages: np.ndarray, *, clip: bool = False) -> np.ndarray:
        """Pace loss in seconds due to tyre age alone, relative to age 0.

        With `clip=True` the tyre age is held at the edge of the range the fit actually
        observed. A quadratic fitted on ages 2-25 does not become trustworthy at age 50
        just because someone evaluates it there - race stints run far longer than practice
        runs, so out-of-sample prediction must clamp rather than extrapolate.
        """
        a = np.asarray(ages, float)
        if clip:
            lo, hi = self.support(compound)
            if np.isfinite(lo):
                a = np.clip(a, lo, hi)
        return self._b(f"age[{compound}]") * a + self._b(f"age2[{compound}]") * a ** 2

    def deg_rate(self, compound: str, age: float = REF_AGE) -> float:
        """Instantaneous degradation in s/lap at a given tyre age."""
        return self._b(f"age[{compound}]") + 2.0 * self._b(f"age2[{compound}]") * age

    def stint_loss(self, compound: str, a0: float, a1: float) -> float:
        """Total pace lost between two tyre ages, in seconds."""
        return float(self.curve(compound, np.array([a1]))[0]
                     - self.curve(compound, np.array([a0]))[0])

    def support(self, compound: str) -> tuple[float, float]:
        return self.age_support.get(compound, (np.nan, np.nan))

    def summary_table(self) -> pd.DataFrame:
        """Per-compound degradation, quoted over the tyre ages actually observed.

        A quadratic fitted to runs starting at tyre age 5-15 says nothing reliable about
        age 0, so `loss_support_s` is reported over the observed range and `loss_0_15_s`
        is kept only for comparison against write-ups that quote a fresh-tyre figure.
        """
        rows = []
        for c in self.compounds:
            lo, hi = self.support(c)
            mid = float(np.nanmean([lo, hi])) if np.isfinite(lo) else REF_AGE
            rows.append({
                "compound": c,
                "age_lo": lo,
                "age_hi": hi,
                "deg_at_mid": self.deg_rate(c, mid),
                "deg_at_10": self.deg_rate(c, 10),
                "loss_support_s": self.stint_loss(c, lo, hi) if np.isfinite(lo) else np.nan,
                "loss_0_15_s": self.stint_loss(c, 0, 15),
                "lin_s_per_lap": self._b(f"age[{c}]"),
                "quad_s_per_lap2": self._b(f"age2[{c}]"),
            })
        return pd.DataFrame(rows)


def _support(laps: pd.DataFrame, compounds: list[str]) -> dict:
    """Observed tyre-age range per compound, on the laps that entered the fit."""
    out = {}
    for c in compounds:
        a = laps.loc[laps["Compound"] == c, "TyreAge"].astype(float)
        if len(a):
            out[c] = (float(a.min()), float(a.max()))
    return out


# ------------------------------------------------------------------------- #
# design matrices
# ------------------------------------------------------------------------- #

def _dummies(series: pd.Series, prefix: str, drop_first: bool = True) -> pd.DataFrame:
    d = pd.get_dummies(series.astype(str), prefix=prefix, drop_first=drop_first)
    return d.astype(float)


def _age_terms(laps: pd.DataFrame, compounds: list[str]) -> pd.DataFrame:
    """Per-compound linear and quadratic tyre-age terms.

    Fuel burn is linear in lap index by construction, so giving tyre age a quadratic
    term is what lets the fit use *shape* as identifying information rather than
    relying on level differences alone.
    """
    out = {}
    for c in compounds:
        m = (laps["Compound"] == c).astype(float).to_numpy()
        a = laps["TyreAge"].to_numpy(float)
        out[f"age[{c}]"] = m * a
        out[f"age2[{c}]"] = m * a ** 2
    return pd.DataFrame(out, index=laps.index)


def _traffic_terms(laps: pd.DataFrame) -> pd.DataFrame:
    """Traffic exposure.

    `frac_close` (share of the lap within 1.0s of the car ahead) is the operative
    feature. `gap_min_s` is deliberately unused as a regressor: it dips to ~0 whenever
    a car *passes* another, so it measures overtaking rather than being held up.
    """
    out = pd.DataFrame(index=laps.index)
    if "frac_close" in laps.columns:
        out["frac_close"] = laps["frac_close"].astype(float).fillna(0.0)
    return out


def _evo_terms(laps: pd.DataFrame) -> pd.DataFrame:
    """Track evolution, measured as log rubber laid down by the field.

    This is the term that rescues the practice fit. Without it, the linear degradation
    coefficient has to absorb the whole green-track effect, and on a Friday morning that
    effect is large and has the opposite sign to degradation - which is how a naive fit
    ends up reporting that tyres get faster as they age.

    It is identified because the log saturates. Inside a run the increment is roughly
    (field laps per lap) / (rubber so far), so an early-FP1 run sees a steep evolution
    slope and a late-FP3 run sees almost none, while the tyre-age slope is the same in
    both. That difference in cross-run shape is the identifying variation. A linear
    rubber count would be collinear with tyre age within a run and would not be
    identified at all.
    """
    out = pd.DataFrame(index=laps.index)
    if "TrackEvo" in laps.columns:
        e = laps["TrackEvo"].astype(float)
        out["TrackEvo"] = (e - e.mean()).fillna(0.0)
    return out


# ------------------------------------------------------------------------- #
# stage A - race
# ------------------------------------------------------------------------- #

def fit_race(laps: pd.DataFrame, *, min_laps_per_compound: int = 25) -> Fit:
    """Estimate the fuel coefficient and race degradation curves.

    Accepts one event or many. Pooling races across events is the preferred way to get
    lambda, because lambda is a property of the cars and the regulations rather than of
    any one circuit, and because using a race to estimate lambda and then scoring
    predictions on that same race would leak. Event fixed effects absorb the tens of
    seconds of pace difference between circuits; track temperature is centred within
    event so its coefficient is a within-event effect rather than a proxy for climate.
    """
    laps = laps.loc[laps["IsRace"]].copy()
    if laps.empty:
        raise ValueError("fit_race needs race laps")

    counts = laps["Compound"].value_counts()
    compounds = [c for c in SLICKS if counts.get(c, 0) >= min_laps_per_compound]
    if not compounds:
        raise ValueError("no compound has enough race laps")
    laps = laps.loc[laps["Compound"].isin(compounds)].copy()

    multi_event = "Round" in laps.columns and laps["Round"].nunique() > 1
    tt = laps["TrackTemp"].astype(float)
    if multi_event:
        track_temp_c = tt - laps.groupby("Round")["TrackTemp"].transform("mean").astype(float)
    else:
        track_temp_c = tt - tt.mean()
    # A session with no weather feed would otherwise put NaN into the design matrix and
    # take the whole fit down. Zero is the centred mean, i.e. "assume typical".
    track_temp_c = track_temp_c.fillna(0.0)

    blocks = [
        _dummies(laps["Driver"], "drv"),
        _age_terms(laps, compounds),
        _traffic_terms(laps),
        _evo_terms(laps),
        pd.DataFrame({
            "FuelKg": laps["FuelKg"].astype(float),
            "TrackTempC": track_temp_c,
        }, index=laps.index),
    ]
    if multi_event:
        blocks.insert(0, _dummies(laps["Round"], "ev"))

    X = pd.concat(blocks, axis=1)
    # compound offsets (relative to the first compound), separate from the age terms
    for c in compounds[1:]:
        X[f"cmp[{c}]"] = (laps["Compound"] == c).astype(float)

    # Drop degenerate columns BEFORE adding the constant: a constant column has zero
    # variance, so filtering afterwards would silently delete the intercept and force
    # the continuous regressors to absorb the ~86s mean lap time.
    X = X.loc[:, X.std(numeric_only=True) > 0]
    X = sm.add_constant(X, has_constant="add")
    y = laps["LapTimeS"].astype(float)

    # Clustered by run: laps within a stint share setup, fuel error and track state, so
    # treating them as independent would badly understate the standard errors.
    res = sm.OLS(y, X).fit(cov_type="cluster",
                           cov_kwds={"groups": laps["RunId"].to_numpy()})

    return Fit(
        kind="race",
        res=res,
        compounds=compounds,
        lambda_fuel=float(res.params.get("FuelKg", np.nan)),
        n_obs=int(len(laps)),
        n_groups=int(laps["RunId"].nunique()),
        design_cols=X.columns.tolist(),
        age_support=_support(laps, compounds),
        notes={"fuel_se": float(res.bse.get("FuelKg", np.nan)),
               "r2": float(res.rsquared),
               "n_events": int(laps["Round"].nunique()) if "Round" in laps else 1},
    )


# ------------------------------------------------------------------------- #
# stage B - practice
# ------------------------------------------------------------------------- #

def fit_practice(laps: pd.DataFrame, lambda_fuel: float, *,
                 min_laps_per_compound: int = 12,
                 correct_fuel: bool = True,
                 use_traffic: bool = True,
                 use_evo: bool = True) -> Fit:
    """Estimate degradation curves from practice, with fuel handed in from stage A.

    The three flags exist so the ablation ladder in `pitwall.validate` is built from the
    same code path rather than from a re-implementation of "what a naive analyst does".
    Setting all three off reproduces the standard approach: regress lap time on tyre age
    with a run intercept, and call the slope degradation.
    """
    laps = laps.loc[~laps["IsRace"]].copy()
    if laps.empty:
        raise ValueError("fit_practice needs practice laps")

    counts = laps["Compound"].value_counts()
    compounds = [c for c in SLICKS if counts.get(c, 0) >= min_laps_per_compound]
    if not compounds:
        raise ValueError("no compound has enough practice laps")
    laps = laps.loc[laps["Compound"].isin(compounds)].copy()

    y = laps["LapTimeS"].astype(float)
    if correct_fuel:
        # Remove the known fuel effect. What is left of the within-run slope is tyre
        # degradation - this single subtraction is the whole point of stage A.
        y = y - lambda_fuel * laps["FuelKg"].astype(float)

    blocks = [
        # Run intercepts absorb unknown starting fuel, driver, car and setup, plus each
        # run's track-state *level*. What they cannot absorb is the within-run trend,
        # which is why TrackEvo is in the model as well.
        _dummies(laps["RunId"], "run"),
        _age_terms(laps, compounds),
    ]
    if use_traffic:
        blocks.append(_traffic_terms(laps))
    if use_evo:
        blocks.append(_evo_terms(laps))

    X = pd.concat(blocks, axis=1)
    # See fit_race: filter before adding the constant, never after.
    X = X.loc[:, X.std(numeric_only=True) > 0]
    X = sm.add_constant(X, has_constant="add")

    res = sm.OLS(y, X).fit(cov_type="cluster",
                           cov_kwds={"groups": laps["RunId"].to_numpy()})

    return Fit(
        kind="practice",
        res=res,
        compounds=compounds,
        lambda_fuel=float(lambda_fuel) if correct_fuel else None,
        n_obs=int(len(laps)),
        n_groups=int(laps["RunId"].nunique()),
        design_cols=X.columns.tolist(),
        age_support=_support(laps, compounds),
        notes={"r2": float(res.rsquared), "fuel_corrected": bool(correct_fuel),
               "traffic": bool(use_traffic), "evo": bool(use_evo),
               "evo_coef": float(res.params.get("TrackEvo", np.nan))},
    )


def identification_report(laps_practice: pd.DataFrame) -> pd.DataFrame:
    """How much of the practice identification actually comes from used tyres?

    If every run started on fresh rubber, starting tyre age would equal run-lap-index
    everywhere and the curvature would be unidentified. This quantifies the lever.
    """
    g = (laps_practice.groupby("RunId")
         .agg(compound=("Compound", "first"),
              fresh=("FreshTyre", "first"),
              age_start=("TyreAge", "min"),
              age_end=("TyreAge", "max"),
              laps=("LapTimeS", "size"))
         .reset_index())
    return g.sort_values(["compound", "age_start"])
