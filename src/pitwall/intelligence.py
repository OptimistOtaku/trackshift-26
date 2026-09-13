"""Causal, lap-synchronous race intelligence.

Observations update a robust local-linear state; supervised models learn its
short-horizon residuals across earlier events. Prediction and target construction
are separate: no future lap, retrospectively cleaned run, or future traffic enters
an input. Forecasts are conditional on continuing this stint under green flags.
The local trend includes fuel, track and traffic effects; it is not tyre wear alone.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import json

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

SLICKS = ("SOFT", "MEDIUM", "HARD")
HORIZONS = (1, 3, 5)
FEATURES = ["horizon", "age", "progress", "race_laps", "n_recent", "spread",
            "last_minus_median", "median3_minus_last", "median8_minus_last",
            "slope", "slope_h", "kalman_minus_last", "kalman_trend", "kalman_h",
            "last_delta", "field_delta", "soft", "medium", "hard"]


def finite(value) -> bool:
    return isinstance(value, (int, float, np.number)) and np.isfinite(value)


def usable(row: dict) -> bool:
    """An instantaneous quality gate, independent of whole-stint cleaning.

    Deleted-lap decisions and `clean` are deliberately ignored: both may be known
    only retrospectively. Slow green laps remain in the evaluation, including errors.
    """
    return (row.get("track_status") == "1" and not row.get("in_lap")
            and not row.get("out_lap") and row.get("compound") in SLICKS
            and finite(row.get("tyre_age")) and row["tyre_age"] >= 1
            and finite(row.get("lap_time_s")) and row["lap_time_s"] > 0
            and int(row["lap"]) > 1)


@dataclass
class PaceState:
    history: list[tuple[int, float]] = field(default_factory=list)
    x: np.ndarray | None = None
    covariance: np.ndarray = field(default_factory=lambda: np.diag([1., .04]))
    last_row: dict | None = None
    segment: int = 0
    innovation: float = 0.

    def observe(self, row: dict) -> bool:
        if self.last_row is not None and row["lap"] <= self.last_row["lap"]:
            raise ValueError("Observations must arrive in increasing lap order per driver")
        old = self.last_row
        reset = old is not None and (
            row.get("out_lap") or old.get("in_lap")
            or row.get("compound") != old.get("compound")
            or (finite(row.get("tyre_age")) and finite(old.get("tyre_age"))
                and row["tyre_age"] < old["tyre_age"]))
        # A neutralisation invalidates the green-pace trend. Re-initialize on restart.
        if reset or row.get("track_status") != "1":
            self.history.clear()
            self.x = None
            self.covariance = np.diag([1., .04])
            self.segment += 1
        self.last_row = dict(row)
        if not usable(row):
            return False
        lap, pace = int(row["lap"]), float(row["lap_time_s"])
        if self.x is None:
            self.x = np.array([pace, 0.])
            self.innovation = 0.
        else:
            dt = lap - self.history[-1][0]
            transition = np.array([[1., dt], [0., 1.]])
            prior = transition @ self.x
            cov = transition @ self.covariance @ transition.T + np.diag([.015 * dt, .001 * dt])
            residual = pace - prior[0]
            # Huber observation weighting: incidents cannot kick the trend arbitrarily.
            scale = np.sqrt(cov[0, 0] + .25)
            noise = .25 * max(1., abs(residual) / (2.5 * scale)) ** 2
            gain = cov[:, 0] / (cov[0, 0] + noise)
            self.x = prior + gain * residual
            identity = np.eye(2) - np.outer(gain, [1., 0.])
            self.covariance = identity @ cov @ identity.T + noise * np.outer(gain, gain)
            self.innovation = float(residual)
        self.history.append((lap, pace))
        self.history = self.history[-12:]
        return True

    def features(self, horizon: int, race_laps: int, field_delta: float) -> dict:
        if self.x is None or not self.history:
            raise ValueError("No usable pace observations")
        recent = self.history[-8:]
        times = np.array([p for _, p in recent])
        laps = np.array([l for l, _ in recent], float)
        # Pairwise median slopes resist one unusually slow lap.
        slopes = [(times[j] - times[i]) / (laps[j] - laps[i])
                  for j in range(len(times)) for i in range(j)]
        slope = float(np.clip(np.median(slopes), -.4, .4)) if slopes else 0.
        last = float(times[-1])
        c = self.last_row["compound"]
        return dict(horizon=horizon, age=float(self.last_row["tyre_age"]),
                    progress=laps[-1] / race_laps, race_laps=race_laps,
                    n_recent=len(times), spread=float(np.median(abs(times - np.median(times)))),
                    last_minus_median=last - float(np.median(times[-5:])),
                    median3_minus_last=float(np.median(times[-3:])) - last,
                    median8_minus_last=float(np.median(times)) - last,
                    slope=slope, slope_h=slope * horizon,
                    kalman_minus_last=float(self.x[0] - last),
                    kalman_trend=float(self.x[1]), kalman_h=float(self.x[1] * horizon),
                    last_delta=float(times[-1] - times[-2]) if len(times) > 1 else 0.,
                    field_delta=field_delta, soft=int(c == "SOFT"),
                    medium=int(c == "MEDIUM"), hard=int(c == "HARD"))


def replay_features(race: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Run forward once. The only data read at lap L are rows at/before L.

    A snapshot means *after the field completed lap L*, not an exact wall-clock
    instant at the leader's crossing. We do not have crossing timestamps in this feed.
    """
    grouped: dict[int, list[dict]] = {}
    seen = set()
    for row in race["laps_data"]:
        key = (row["driver"], int(row["lap"]))
        if key in seen:
            raise ValueError(f"Duplicate timing row: {key}")
        seen.add(key)
        grouped.setdefault(int(row["lap"]), []).append(row)
    states: dict[str, PaceState] = {}
    features, observations = [], []
    for lap, rows in sorted(grouped.items()):
        deltas = []
        for row in rows:
            state = states.setdefault(row["driver"], PaceState())
            old = state.last_row
            if (old and usable(old) and usable(row) and old["lap"] == lap - 1
                    and old["compound"] == row["compound"]
                    and row["tyre_age"] == old["tyre_age"] + 1):
                deltas.append(row["lap_time_s"] - old["lap_time_s"])
        field_delta = float(np.median(deltas)) if deltas else 0.
        for row in sorted(rows, key=lambda r: r["driver"]):
            state = states[row["driver"]]
            ok = state.observe(row)
            obs = dict(round=int(race["round"]), driver=row["driver"], lap=lap,
                       segment=state.segment, usable=ok, compound=row.get("compound"),
                       age=row.get("tyre_age"), actual_s=row.get("lap_time_s"))
            observations.append(obs)
            if not ok or len(state.history) < 3:
                continue
            for h in HORIZONS:
                if lap + h > int(race["laps"]):
                    continue
                f = state.features(h, int(race["laps"]), field_delta)
                features.append(dict(f, round=int(race["round"]), driver=row["driver"],
                                     lap=lap, target_lap=lap+h, segment=state.segment,
                                     compound=row["compound"], current_s=row["lap_time_s"]))
    return pd.DataFrame(features), pd.DataFrame(observations)


def attach_targets(features: pd.DataFrame, observations: pd.DataFrame) -> pd.DataFrame:
    """Labels only: score uninterrupted, observed same-stint green continuations.

    Emit a scored flag for every forecast so exclusions and coverage are auditable.
    Labels are never passed to a learner as features.
    """
    out = features.copy()
    lookup = {(r.round, r.driver, r.lap): r for r in observations.itertuples()}
    actual = []
    for r in out.itertuples():
        future = [lookup.get((r.round, r.driver, lap))
                  for lap in range(r.lap + 1, r.target_lap + 1)]
        ok = all(q is not None and q.usable and q.segment == r.segment
                 and q.compound == r.compound and q.age == r.age + i + 1
                 for i, q in enumerate(future))
        actual.append(float(future[-1].actual_s) if ok else np.nan)
    out["actual_s"] = actual
    out["target_delta"] = out["actual_s"] - out["current_s"]
    out["scored"] = out["actual_s"].notna()
    return out


def load_replays(root: Path) -> tuple[pd.DataFrame, pd.DataFrame, list[dict]]:
    inputs, observations, races = [], [], []
    for path in sorted((root / "artifacts/demo/replay").glob("R*.json")):
        race = json.loads(path.read_text(encoding="utf-8"))
        x, obs = replay_features(race)
        inputs.append(x)
        observations.append(obs)
        races.append(race)
    if not races:
        raise ValueError("No replay files; run scripts/export_replay.py first")
    obs = pd.concat(observations, ignore_index=True)
    return attach_targets(pd.concat(inputs, ignore_index=True), obs), obs, races


def fit_candidates(train: pd.DataFrame) -> dict:
    train = train.loc[train["scored"]]
    if train["round"].nunique() < 3:
        raise ValueError("Three completed training races are required")
    x, y = train[FEATURES], train["target_delta"]
    # Small trees, regularisation and no random early-stopping split within races.
    boosted = HistGradientBoostingRegressor(loss="absolute_error", max_iter=140,
        max_leaf_nodes=9, min_samples_leaf=60, l2_regularization=20.,
        learning_rate=.06, early_stopping=False, random_state=26)
    ridge = make_pipeline(StandardScaler(), Ridge(alpha=100.))
    return {"boosted": boosted.fit(x, y), "ridge": ridge.fit(x, y)}


def predict_candidates(models: dict, data: pd.DataFrame) -> dict[str, np.ndarray]:
    current = data["current_s"].to_numpy(float)
    predictions = {
        "persistence": current.copy(),
        "rolling_median": current + data["median3_minus_last"].to_numpy(float),
        "recent_trend": current + data["slope_h"].to_numpy(float),
        "state_space": current + data["kalman_minus_last"].to_numpy(float)
                       + data["kalman_h"].to_numpy(float),
    }
    for name, model in models.items():
        predictions[name] = current + model.predict(data[FEATURES])
    # Fixed blend, not fitted on evaluation races; state smooths tree discontinuities.
    predictions["hybrid"] = .75 * predictions["boosted"] + .25 * predictions["state_space"]
    return predictions


def metrics(actual, predicted) -> dict:
    err = np.asarray(predicted, float) - np.asarray(actual, float)
    return dict(n=int(len(err)), rmse_s=float(np.sqrt(np.mean(err**2))),
                mae_s=float(np.mean(abs(err))), bias_s=float(np.mean(err)),
                p90_error_s=float(np.quantile(abs(err), .9)))


def interval_radius(errors, coverage: float = .9) -> float | None:
    """Finite-sample absolute-residual quantile from PREVIOUS events only.

    Laps are dependent and events shift: coverage is empirical, not a guarantee.
    """
    errors = np.abs(np.asarray(errors, float))
    errors = errors[np.isfinite(errors)]
    if len(errors) < 30:
        return None
    rank = min(len(errors), int(np.ceil((len(errors) + 1) * coverage)))
    return float(np.partition(errors, rank-1)[rank-1])
