"""Earlier-race-only decision model; no post-stop traffic feature.

Writes model parameters and per-driver candidate tyre steps into the causal replay.
Run AFTER benchmark_intelligence.py. Retrospective stop labels retain their known
selection limitations; the chronological comparison is separate from lap forecasting.
"""
from pathlib import Path
import sys
import json
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
from pitwall.decision import fit_decision, SLICKS
from pitwall.intelligence import load_replays, metrics, interval_radius
from pitwall.stopvalue import stop_table
from benchmark_intelligence import write_json


def main():
    features, _, races = load_replays(ROOT)
    one = features.loc[features.horizon == 1]
    season = pd.read_parquet(ROOT / "data/season_2026.parquet")
    stops = stop_table(season).rename(columns={"Round":"round", "Driver":"driver", "PitLap":"lap"})
    stops = stops.merge(one, on=["round", "driver", "lap"], how="inner", validate="one_to_one")
    results = []
    frozen = None
    for race in races:
        rnd = int(race["round"])
        if rnd < 4:
            continue
        train, test = stops.loc[stops["round"] < rnd], stops.loc[stops["round"] == rnd].copy()
        prior = pd.concat(results, ignore_index=True) if results else pd.DataFrame()
        def select():
            if prior.empty:
                return "pair"
            return min(("pair", "age", "state"), key=lambda name:
                prior.assign(error=(prior[f"pred_{name}"]-prior.step_obs)**2).groupby("round").error.mean().mean())
        if rnd == 9:
            frozen = select()
        selected = frozen or select()
        models = {spec: fit_decision(train, spec) for spec in ("pair", "age", "state")}
        for spec, model in models.items():
            test[f"pred_{spec}"] = model.predict(test)
        test["baseline"] = float(train.step_obs.mean())
        test["selected_s"] = test[f"pred_{selected}"]
        radius = interval_radius(prior[f"pred_{selected}"]-prior.step_obs) if not prior.empty else None
        test["radius_s"] = np.nan if radius is None else radius
        results.append(test)
        file = ROOT / f"artifacts/demo/intelligence/R{rnd:02d}.json"
        payload = json.loads(file.read_text(encoding="utf-8"))
        payload["decision_model"] = dict(models[selected].to_dict(), radius_s=radius,
            training_through_round=rnd-1, target="observed pace step across a stop",
            limitation="Post-stop traffic is unknown; interval is empirical. Not a causal treatment effect.")
        now = one.loc[one["round"] == rnd]
        candidates = {}
        for compound in SLICKS:
            scenario = now.copy()
            scenario["pair"] = scenario.compound + ">" + compound
            pred = models[selected].predict(scenario)
            for row, value in zip(scenario.itertuples(), pred):
                candidates.setdefault((int(row.lap), row.driver), {})[compound] = dict(
                    step_s=float(value), radius_s=radius,
                    supported=bool(np.isfinite(value)),
                    training_stops=models[selected].support.get(row.pair, 0),
                    extrapolating=not models[selected].age_range[0] <= row.age <= models[selected].age_range[1])
        for snapshot in payload["snapshots"]:
            snapshot["stop_scenarios"] = candidates.get((snapshot["lap"], snapshot["driver"]), {})
        write_json(file, payload)
        print(f"R{rnd:02d} {selected} {len(test)} stops", flush=True)
    scored = pd.concat(results, ignore_index=True)
    columns = ["round", "driver", "lap", "pair", "step_obs", "baseline", "pred_pair", "pred_age", "pred_state", "selected_s", "radius_s"]
    scored[columns].to_csv(ROOT / "artifacts/decision_predictions_2026.csv", index=False)
    final = scored.loc[scored["round"] >= 9].dropna(subset=["selected_s"])
    report = dict(selected_model=frozen, n_training_labels=len(stops),
        evaluation="R09-R12; architecture selected on R04-R08; earlier races only",
        **metrics(final.step_obs, final.selected_s),
        baseline_rmse_s=metrics(final.step_obs, final.baseline)["rmse_s"],
        candidates={name: metrics(final.step_obs, final[f"pred_{name}"]) for name in ("pair", "age", "state")},
        limitation="Conditional on the requested compound; labels use retrospectively filtered pre/post laps.")
    write_json(ROOT / "artifacts/demo/intelligence/decision_report.json", report)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
