"""Pre-stop pace-step model and transparent short-horizon undercut scenarios.

Unlike the retrospective stop model, this model never consumes post-stop traffic,
new-tyre observed age, or post-stop pace as an input. The requested compound is a
scenario, not a prediction of which tyre the team will actually choose.
"""
from __future__ import annotations

from dataclasses import dataclass
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge

SLICKS = ("SOFT", "MEDIUM", "HARD")
PAIRS = tuple(f"{a}>{b}" for a in SLICKS for b in SLICKS)
DECISION_SPECS = ("mean", "pair", "age", "state", "context", "shrink_context", "factorized", "environment")


def design(stops: pd.DataFrame, spec: str) -> pd.DataFrame:
    x = pd.DataFrame(index=stops.index)
    if spec == "mean":
        x["constant"] = 0.
        return x
    for pair in PAIRS:
        x[f"pair:{pair}"] = (stops.pair == pair).astype(float)
    if spec == "environment":
        x["temperature"] = (stops.track_temp_c-35.)/10.
        x["temperature_missing"] = stops.weather_missing
        x["traffic"] = stops.traffic_close
        x["traffic_missing"] = stops.traffic_missing
        x["temperature_change"] = stops.track_temp_change_c/10.
    if spec in ("age", "state", "context", "shrink_context", "factorized"):
        x["age"] = stops.age / 25.
        x["age2"] = (stops.age / 25.)**2
    if spec in ("state", "context", "shrink_context", "factorized"):
        x["trend"] = stops.kalman_trend
        x["slope"] = stops.slope
        x["pace_displacement"] = stops.last_minus_median
        x["spread"] = stops.spread
        x["progress"] = stops.progress
    if spec in ("context", "shrink_context", "factorized"):
        x["field_relative"] = stops.field_relative
        x["median3"] = stops.median3_minus_last
        x["mean8"] = stops.mean8_minus_last
        x["pace_scale"] = stops.pace_scale / 100.
    if spec == "factorized":
        for compound in SLICKS:
            x[f"old:{compound}"] = stops.pair.str.startswith(compound+">").astype(float)
            x[f"new:{compound}"] = stops.pair.str.endswith(">"+compound).astype(float)
    return x


@dataclass
class DecisionModel:
    model: Ridge
    spec: str
    columns: list[str]
    support: dict[str, int]
    age_range: tuple[float, float]

    def predict(self, rows: pd.DataFrame) -> np.ndarray:
        values = self.model.predict(design(rows, self.spec)[self.columns])
        # An unseen requested transition is unsupported, not the reference compound.
        return np.where(rows.pair.isin(self.support), values, np.nan)

    def to_dict(self) -> dict:
        return dict(spec=self.spec, intercept=float(self.model.intercept_),
                    coefficients=dict(zip(self.columns, self.model.coef_.tolist())),
                    pair_counts=self.support, age_range=list(self.age_range))


def fit_decision(stops: pd.DataFrame, spec: str = "state") -> DecisionModel:
    if spec not in DECISION_SPECS:
        raise ValueError(f"Unknown decision specification: {spec}")
    if stops["round"].nunique() < 3:
        raise ValueError("Need three earlier races")
    x = design(stops, spec)
    # Pair effects shrink toward the intercept; continuous variables have explicit units.
    model = Ridge(alpha=32. if spec == "shrink_context" else 8.).fit(x, stops.step_obs)
    return DecisionModel(model, spec, x.columns.tolist(),
        {k: int(v) for k, v in stops.pair.value_counts().items()},
        (float(stops.age.min()), float(stops.age.max())))


def undercut_scenario(*, step_s: float, step_radius_s: float, gap_s: float,
                     response_laps: int = 3, pace_advantage_s: float = 0.,
                     warmup_loss_s: float = 0., traffic_loss_s: float = 0.,
                     service_delta_s: float = 0., degradation_delta_s: float = 0.) -> list[dict]:
    """Conditional arithmetic, NOT a learned probability of gaining a place.

    Positive pace_advantage favours our car. Positive service_delta means our stop
    is slower. Warm-up and traffic are TOTAL losses over the horizon; warm-up is
    charged on lap one, traffic is distributed. Degradation_delta is additional
    net pace loss per successive lap. The uncertain step is shared across the
    entire horizon, so its interval grows as k, never as sqrt(k).
    """
    numbers = (step_s, step_radius_s, gap_s, pace_advantage_s, warmup_loss_s,
               traffic_loss_s, service_delta_s, degradation_delta_s)
    if not all(np.isfinite(v) for v in numbers):
        raise ValueError("Scenario inputs must be finite")
    if isinstance(response_laps, bool) or int(response_laps) != response_laps or not 1 <= response_laps <= 5:
        raise ValueError("response_laps must be an integer from 1 to 5")
    if min(step_radius_s, warmup_loss_s, traffic_loss_s) < 0:
        raise ValueError("Uncertainty and total losses must be nonnegative")
    rows = []
    for k in range(1, int(response_laps)+1):
        gain = (k * (step_s + pace_advantage_s) - degradation_delta_s*k*(k-1)/2
                - warmup_loss_s - traffic_loss_s*k/response_laps - service_delta_s)
        radius = k * step_radius_s
        margin = gain - gap_s
        rows.append(dict(response_laps=k, time_gained_s=gain, margin_s=margin,
            lower_margin_s=margin-radius, upper_margin_s=margin+radius,
            classification="positive scenario margin" if margin-radius > 0 else
                           "negative scenario margin" if margin+radius < 0 else "uncertain",
            tyre_age_deficit_laps=k))
    return rows
