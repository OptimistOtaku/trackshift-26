"""Train on earlier races, select on R04-R08, evaluate once on R09-R12.

No downloads. Rebuilds the causal replay intelligence and its auditable scoreboard.
Run: python scripts/benchmark_intelligence.py
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys

# Keep small tabular fits from oversubscribing laptop CPUs.
os.environ.setdefault("OMP_NUM_THREADS", "2")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "2")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import numpy as np
import pandas as pd
from pitwall.intelligence import (HORIZONS, fit_candidates, interval_radius,
                                  load_replays, metrics, predict_candidates)

OUT = ROOT / "artifacts/demo/intelligence"
FIRST_TEST = 4
HOLDOUT_START = 9
CANDIDATES = ("persistence", "rolling_median", "recent_trend", "state_space",
              "ridge", "boosted", "hybrid")


def clean_json(obj):
    if isinstance(obj, dict):
        return {k: clean_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [clean_json(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (float, np.floating)):
        return round(float(obj), 6) if np.isfinite(obj) else None
    if isinstance(obj, np.bool_):
        return bool(obj)
    return obj


def write_json(path, obj):
    path.write_text(json.dumps(clean_json(obj), allow_nan=False, separators=(",", ":")),
                    encoding="utf-8")


def select_model(prior: pd.DataFrame) -> str:
    if prior.empty:
        return "hybrid"
    # Equal weight for events and horizons rather than favouring long, clean races.
    scored = prior.loc[prior["scored"]]
    losses = {name: scored.assign(error=(scored[name] - scored.actual_s)**2)
              .groupby(["round", "horizon"]).error.mean().mean() for name in CANDIDATES}
    return min(losses, key=losses.get)


def cluster_bootstrap(frame: pd.DataFrame, baseline: str) -> list[float]:
    """Paired event bootstrap; resample whole races, never correlated individual laps."""
    squared = frame.assign(model_err=(frame.selected_s-frame.actual_s)**2,
                           base_err=(frame[baseline]-frame.actual_s)**2)
    blocks = squared.groupby("round").agg(model=("model_err", "sum"),
        base=("base_err", "sum"), n=("model_err", "size")).to_numpy()
    rng = np.random.default_rng(26)
    sums = blocks[rng.integers(0, len(blocks), size=(2000, len(blocks)))].sum(axis=1)
    gain = 100 * (1 - np.sqrt(sums[:, 0] / sums[:, 1]))
    return np.quantile(gain, [.025, .975]).tolist()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    data, observations, races = load_replays(ROOT)
    print(f"{len(observations)} observed laps; {len(data)} forecast requests", flush=True)
    history = []
    selected_holdout = None
    for race in races:
        rnd = int(race["round"])
        current = data.loc[data["round"] == rnd].copy()
        if rnd < FIRST_TEST:
            write_json(OUT / f"R{rnd:02d}.json", dict(round=rnd, training_through_round=None,
                status="collecting training races", selected_model=None, snapshots=[], evaluation=[]))
            continue
        train = data.loc[data["round"] < rnd]
        models = fit_candidates(train)
        prior = pd.concat(history, ignore_index=True) if history else pd.DataFrame()
        if rnd == HOLDOUT_START:
            selected_holdout = select_model(prior)
        selected = selected_holdout or select_model(prior)
        predictions = predict_candidates(models, current)
        for name, pred in predictions.items():
            current[name] = pred
        current["selected_s"] = current[selected]
        current["model"] = selected
        current["radius_s"] = np.nan
        # Prequential calibration: residuals from earlier, out-of-event predictions only.
        for h in HORIZONS:
            if not prior.empty:
                calibration = prior.loc[prior.horizon == h]
                radius = interval_radius(calibration[selected] - calibration.actual_s)
                if radius is not None:
                    current.loc[current.horizon == h, "radius_s"] = radius
        history.append(current)
        score = current.loc[current.scored]
        print(f"R{rnd:02d} {selected:14s} n={len(score):4d} "
              f"RMSE={metrics(score.actual_s, score.selected_s)['rmse_s']:.3f} "
              f"persistence={metrics(score.actual_s, score.persistence)['rmse_s']:.3f}", flush=True)
        snapshots = []
        for (lap, driver), group in current.groupby(["lap", "driver"], sort=True):
            first = group.iloc[0]
            snapshots.append(dict(lap=int(lap), driver=driver, compound=first.compound,
                tyre_age=float(first.age), observations=int(first.n_recent),
                pace_trend_s_per_lap=float(first.kalman_trend),
                forecasts=[dict(horizon=int(r.horizon), target_lap=int(r.target_lap),
                    pace_s=r.selected_s, lower_s=r.selected_s-r.radius_s,
                    upper_s=r.selected_s+r.radius_s) for r in group.itertuples()]))
        # Separate retrospective scoring records. UI must filter target_lap <= cursor.
        evaluation = [dict(issued_lap=int(r.lap), target_lap=int(r.target_lap),
            driver=r.driver, horizon=int(r.horizon), predicted_s=r.selected_s,
            actual_s=r.actual_s, baseline_s=r.persistence)
            for r in score.itertuples()]
        write_json(OUT / f"R{rnd:02d}.json", dict(round=rnd,
            training_through_round=rnd-1, selected_model=selected,
            status="ready", snapshot_basis="after the field completed this lap",
            interval_nominal_coverage=.9, snapshots=snapshots, evaluation=evaluation))

    all_predictions = pd.concat(history, ignore_index=True)
    all_predictions.to_csv(ROOT / "artifacts/intelligence_predictions_2026.csv", index=False)
    scored = all_predictions.loc[all_predictions.scored]
    development = scored.loc[scored["round"] < HOLDOUT_START]
    holdout = scored.loc[scored["round"] >= HOLDOUT_START]
    rows = []
    for split, group in (("development", development), ("holdout", holdout)):
        for h in (0, *HORIZONS):
            subset = group if h == 0 else group.loc[group.horizon == h]
            for model in (*CANDIDATES, "selected_s"):
                rows.append(dict(split=split, horizon=h, model=model,
                                 **metrics(subset.actual_s, subset[model])))
    pd.DataFrame(rows).to_csv(ROOT / "artifacts/intelligence_benchmark_2026.csv", index=False)
    baseline = min(("persistence", "rolling_median", "recent_trend", "state_space"),
                   key=lambda name: metrics(development.actual_s, development[name])["rmse_s"])
    per_horizon = []
    for h in HORIZONS:
        subset = holdout.loc[holdout.horizon == h]
        calibrated = subset.loc[subset.radius_s.notna()]
        model_metric = metrics(subset.actual_s, subset.selected_s)
        base_metric = metrics(subset.actual_s, subset[baseline])
        per_horizon.append(dict(horizon=h, **model_metric, baseline_rmse_s=base_metric["rmse_s"],
            improvement_pct=100*(1-model_metric["rmse_s"]/base_metric["rmse_s"]),
            interval_coverage=float(((calibrated.selected_s-calibrated.actual_s).abs()
                                      <= calibrated.radius_s).mean()),
            mean_interval_width_s=float(2*calibrated.radius_s.mean())))
    model_metric = metrics(holdout.actual_s, holdout.selected_s)
    base_metric = metrics(holdout.actual_s, holdout[baseline])
    manifest = [{"path": str(p.relative_to(ROOT)).replace("\\", "/"),
                 "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
                for p in sorted((ROOT / "artifacts/demo/replay").glob("R*.json"))]
    report = dict(version=1, task="same-stint green-flag lap-time forecast",
        selection="equal event/horizon MSE on R04-R08; architecture frozen for R09-R12",
        training="expanding earlier races only; coefficients refit before each event",
        selected_model=selected_holdout, baseline=baseline,
        holdout_rounds=sorted(holdout["round"].unique().tolist()),
        **model_metric, baseline_rmse_s=base_metric["rmse_s"],
        improvement_pct=100*(1-model_metric["rmse_s"]/base_metric["rmse_s"]),
        improvement_event_bootstrap_95=cluster_bootstrap(holdout, baseline),
        issued_forecasts=int((all_predictions["round"] >= HOLDOUT_START).sum()),
        scored_forecasts=len(holdout), horizons=per_horizon,
        per_event=[dict(round=int(rnd), **metrics(g.actual_s, g.selected_s),
            baseline_rmse_s=metrics(g.actual_s, g[baseline])["rmse_s"])
            for rnd, g in holdout.groupby("round")],
        limitations=["Only four final evaluation races; interval coverage is empirical.",
            "Forecasts assume no pit stop or neutralisation during the horizon.",
            "Lap-synchronous snapshots are not exact live wall-clock timing.",
            "Pace trend includes fuel, traffic, track and tyre effects; it is not measured wear.",
            "The 2026 files are cached source data; results do not establish superiority to other teams."],
        source_manifest=manifest)
    write_json(OUT / "report.json", report)
    print(json.dumps(clean_json({k:v for k,v in report.items()
        if k not in ("source_manifest", "limitations", "per_event")}), indent=2))


if __name__ == "__main__":
    main()
