"""Opponent-relative forecasts and robust attack budgets.

Observed evidence is future relative running time under continued green running.
Attack budgets are conditional scenarios, never counterfactual race-win labels.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor

WEIGHTS = {3: {1: 1.5, 3: 1.5}, 5: {1: 1.5, 3: 2., 5: 1.5}}
BATTLE_FEATURES = ["horizon", "current_delta", "forecast_loss", "age", "rival_age",
    "trend", "rival_trend", "spread", "rival_spread", "progress", "position",
    "relative_field", "rival_relative_field", "soft", "rival_soft", "hard", "rival_hard"]
BATTLE_CANDIDATES = ("constant_gap", "persistence", "rolling_median", "state_space",
    "hybrid", "pace_model", "relative_model", "relative_blend")


def battle_requests(predictions: pd.DataFrame, races: list[dict]) -> pd.DataFrame:
    """Choose adjacent rivals using CURRENT order, before attaching labels.

    Integration linearly interpolates the pace forecasts at laps 2 and 4. Actual
    totals sum every observed future lap, including slow laps. No future positions
    or response laps select a rival or enter a feature.
    """
    pred = {(int(r.round), r.driver, int(r.lap), int(r.horizon)): r
            for r in predictions.itertuples()}
    rows = []
    for race in races:
        rnd = int(race["round"])
        raw = {(r["driver"], int(r["lap"])): r for r in race["laps_data"]}
        laps = sorted({int(r["lap"]) for r in race["laps_data"]})
        for lap in laps:
            order = sorted([r for r in race["laps_data"] if r["lap"] == lap and r.get("position")],
                           key=lambda r: r["position"])
            for ahead, behind in zip(order, order[1:]):
                if behind["position"] != ahead["position"]+1:
                    continue
                a, b = behind["driver"], ahead["driver"]
                for h, weights in WEIGHTS.items():
                    ap = {k: pred.get((rnd, a, lap, k)) for k in weights}
                    bp = {k: pred.get((rnd, b, lap, k)) for k in weights}
                    if any(v is None for v in [*ap.values(), *bp.values()]):
                        continue
                    x, y = ap[1], bp[1]
                    r = dict(round=rnd, lap=lap, target_lap=lap+h, driver=a, rival=b,
                        horizon=h, position=behind["position"], age=x.age, rival_age=y.age,
                        trend=x.kalman_trend, rival_trend=y.kalman_trend,
                        spread=x.spread, rival_spread=y.spread, progress=x.progress,
                        relative_field=x.field_relative, rival_relative_field=y.field_relative,
                        soft=x.soft, rival_soft=y.soft, hard=x.hard, rival_hard=y.hard,
                        current_delta=x.current_s-y.current_s, constant_gap=0.)
                    for name in ("persistence", "rolling_median", "state_space", "hybrid", "selected_s"):
                        r["pace_model" if name == "selected_s" else name] = sum(
                            w*(getattr(ap[k], name)-getattr(bp[k], name)) for k, w in weights.items())
                    r["forecast_loss"] = r["pace_model"]
                    # Target construction is intentionally below the complete feature block.
                    r["scored"] = bool(ap[h].scored and bp[h].scored)
                    r["actual_loss_s"] = sum(raw[a, lap+k]["lap_time_s"]-raw[b, lap+k]["lap_time_s"]
                        for k in range(1, h+1)) if r["scored"] else np.nan
                    rows.append(r)
    return pd.DataFrame(rows)


def fit_relative(train: pd.DataFrame):
    train = train.loc[train.scored]
    if train["round"].nunique() < 3:
        return None
    model = HistGradientBoostingRegressor(max_iter=140, max_leaf_nodes=7,
        min_samples_leaf=60, l2_regularization=30., learning_rate=.04,
        early_stopping=False, random_state=26)
    return model.fit(train[BATTLE_FEATURES],
                     (train.actual_loss_s-train.pace_model).clip(-8, 8))


def attack_budget(*, step_s: float, step_radius_s: float, gap_s: float,
                  relative_loss_s: float, relative_radius_s: float,
                  horizon: int, warmup_s: float = .7, service_s: float = 0.,
                  traffic_s: float = 0., degradation_s: float = 0.) -> dict:
    """Price an undercut after BOTH cars stop; assumes rival responds at horizon.

    Positive relative loss means we are slower. Both shared errors accumulate
    conservatively; adding empirical radii is a stress range, not joint coverage.
    Positive traffic budget is the additional delay the central scenario tolerates.
    """
    values = (step_s, step_radius_s, gap_s, relative_loss_s, relative_radius_s,
              warmup_s, service_s, traffic_s, degradation_s)
    if not all(np.isfinite(v) for v in values):
        raise ValueError("Attack inputs must be finite")
    if type(horizon) is not int or horizon not in WEIGHTS:
        raise ValueError("Attack horizon must be 3 or 5 laps")
    if min(step_radius_s, relative_radius_s, gap_s, warmup_s, traffic_s) < 0:
        raise ValueError("Gaps, uncertainty, warm-up and traffic must be nonnegative")
    gain = horizon*step_s-relative_loss_s-warmup_s-service_s-degradation_s*horizon*(horizon-1)/2
    margin = gain-gap_s-traffic_s
    radius = horizon*step_radius_s+relative_radius_s
    return dict(margin_s=margin, lower_margin_s=margin-radius, upper_margin_s=margin+radius,
        additional_traffic_budget_s=margin, conservative_traffic_budget_s=margin-radius,
        required_step_s=(gap_s+relative_loss_s+warmup_s+service_s+traffic_s
                         +degradation_s*horizon*(horizon-1)/2)/horizon,
        verdict="positive across stress range" if margin-radius > 0 else
                "negative across stress range" if margin+radius < 0 else "uncertain",
        assumption="Both cars stop; rival responds after the selected horizon; no neutralisation.")


def robust_compound_plan(scenarios: dict, battles: list[dict], *, gap_s: float,
                         warmup_s: float = .7, service_s: float = 0., traffic_s: float = 0.,
                         degradation_s: float = 0.) -> list[dict]:
    """Rank supported compounds by their worst margin over 3/5-lap responses.

    Inventory and sporting legality remain user inputs; unsupported or extrapolated
    transitions are excluded, as are cases without calibrated earlier-race errors.
    """
    plans = []
    for compound, step in scenarios.items():
        if (not step.get("supported") or step.get("extrapolating")
                or step.get("radius_s") is None or step.get("training_stops", 0) < 5):
            continue
        cases = []
        for b in battles:
            if b.get("radius_s") is None:
                continue
            budget = attack_budget(step_s=step["step_s"], step_radius_s=step["radius_s"],
                gap_s=gap_s, relative_loss_s=b["predicted_loss_s"], relative_radius_s=b["radius_s"],
                horizon=int(b["horizon"]), warmup_s=warmup_s, service_s=service_s,
                traffic_s=traffic_s, degradation_s=degradation_s)
            cases.append(dict(horizon=b["horizon"], **budget))
        if cases:
            plans.append(dict(compound=compound, cases=cases,
                worst_margin_s=min(c["lower_margin_s"] for c in cases),
                central_margin_s=min(c["margin_s"] for c in cases)))
    return sorted(plans, key=lambda p: p["worst_margin_s"], reverse=True)
