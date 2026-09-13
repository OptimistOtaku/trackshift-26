"""Reproduce the opponent-relative evidence and deploy causal battle snapshots.

Run after benchmark_intelligence.py and benchmark_decision.py. No downloads.
"""
from pathlib import Path
import json
import os
import sys

os.environ.setdefault("OMP_NUM_THREADS", "2")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"src"))
sys.path.insert(0, str(ROOT/"scripts"))
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score
from pitwall.battle import BATTLE_CANDIDATES, BATTLE_FEATURES, battle_requests, fit_relative
from pitwall.intelligence import metrics, interval_radius
from benchmark_intelligence import write_json, cluster_bootstrap


def balanced_mse(data, name):
    return data.assign(error=(data[name]-data.actual_loss_s)**2).groupby(["round", "horizon"]).error.mean().mean()


def alert_metrics(data, column, threshold=2.):
    actual, pred = data.actual_loss_s.to_numpy(), data[column].to_numpy()
    truth, alert = actual > threshold, pred > threshold
    tp = int((truth & alert).sum())
    return dict(threshold_s=threshold, alerts=int(alert.sum()), actual_erosions=int(truth.sum()),
        precision=float(tp/alert.sum()) if alert.any() else None,
        recall=float(tp/truth.sum()) if truth.any() else None,
        auc=float(roc_auc_score(truth, pred)) if len(set(truth)) == 2 else None,
        # Distance from the threshold on wrong-side decisions. This is a forecast
        # diagnostic in seconds, not time saved by a hypothetical intervention.
        threshold_regret_s=float(np.mean(np.where(truth != alert, abs(actual-threshold), 0))))


def regret_bootstrap(data, baseline, threshold=2.):
    actual = data.actual_loss_s
    blocks = pd.DataFrame({"round":data["round"],
        "model":np.where((data.selected_s>threshold)!=(actual>threshold),abs(actual-threshold),0),
        "base":np.where((data[baseline]>threshold)!=(actual>threshold),abs(actual-threshold),0)}).groupby("round").sum().to_numpy()
    rng = np.random.default_rng(26)
    sums = blocks[rng.integers(0,len(blocks),size=(2000,len(blocks)))].sum(axis=1)
    return np.quantile(100*(1-sums[:,0]/sums[:,1]),[.025,.975]).tolist()


def main():
    predictions = pd.read_csv(ROOT/"artifacts/intelligence_predictions_2026.csv")
    races = [json.loads(p.read_text(encoding="utf-8")) for p in sorted((ROOT/"artifacts/demo/replay").glob("R*.json"))]
    data = battle_requests(predictions, races)
    history, frozen = [], None
    for rnd, current in data.groupby("round"):
        current = current.copy()
        prior = pd.concat(history, ignore_index=True) if history else pd.DataFrame()
        model = fit_relative(data.loc[data["round"] < rnd])
        current["relative_model"] = current.pace_model + (model.predict(current[BATTLE_FEATURES]) if model else 0.)
        current["relative_blend"] = .5*current.relative_model+.5*current.pace_model
        valid = prior.loc[(prior["round"] >= 7) & prior.scored] if not prior.empty else prior
        selected = min(BATTLE_CANDIDATES, key=lambda name: balanced_mse(valid, name)) if not valid.empty else "pace_model"
        if rnd == 9:
            frozen = selected
        selected = frozen or selected
        current["selected_s"] = current[selected]
        current["model"] = selected
        current["radius_s"] = np.nan
        if not prior.empty:
            for h in (3, 5):
                cal = prior.loc[(prior.horizon == h) & prior.scored]
                if selected in ("relative_model", "relative_blend"):
                    cal = cal.loc[cal["round"] >= 7]
                radius = interval_radius(cal[selected]-cal.actual_loss_s)
                if radius is not None:
                    current.loc[current.horizon == h, "radius_s"] = radius
        history.append(current)
        file = ROOT/f"artifacts/demo/intelligence/R{rnd:02d}.json"
        payload = json.loads(file.read_text(encoding="utf-8"))
        snapshots, defence = {}, {}
        for r in current.itertuples():
            snapshots.setdefault((r.lap, r.driver), []).append(dict(rival=r.rival, horizon=r.horizon,
                target_lap=r.target_lap, predicted_loss_s=r.selected_s, radius_s=r.radius_s,
                lower_s=r.selected_s-r.radius_s, upper_s=r.selected_s+r.radius_s,
                baseline_loss_s=r.persistence, rival_age=r.rival_age))
            defence.setdefault((r.lap, r.rival), []).append(dict(rival=r.driver, horizon=r.horizon,
                target_lap=r.target_lap, predicted_closing_s=-r.selected_s, radius_s=r.radius_s,
                lower_s=-r.selected_s-r.radius_s, upper_s=-r.selected_s+r.radius_s))
        for snap in payload["snapshots"]:
            snap["battles"] = snapshots.get((snap["lap"], snap["driver"]), [])
            snap["defence"] = defence.get((snap["lap"], snap["driver"]), [])
        payload["battle_model"] = dict(name=selected, training_through_round=int(rnd)-1,
            target="Relative running-time loss to the current car ahead; both continue under green flags")
        payload["battle_evaluation"] = [dict(issued_lap=int(r.lap), target_lap=int(r.target_lap),
            driver=r.driver, rival=r.rival, horizon=int(r.horizon), predicted_s=r.selected_s,
            actual_s=r.actual_loss_s, baseline_s=r.persistence) for r in current.loc[current.scored].itertuples()]
        write_json(file, payload)
        score = current.loc[current.scored]
        print(f"R{rnd:02d} {selected:16s} {len(score)} battles; RMSE {metrics(score.actual_loss_s,score.selected_s)['rmse_s']:.3f}", flush=True)

    result = pd.concat(history, ignore_index=True)
    result.to_csv(ROOT/"artifacts/battle_predictions_2026.csv", index=False)
    dev = result.loc[result["round"].between(7,8) & result.scored]
    final = result.loc[(result["round"]>=9) & result.scored].copy()
    baseline = min(("constant_gap", "persistence", "rolling_median", "state_space"), key=lambda name: balanced_mse(dev,name))
    gain = lambda d: 100*(1-metrics(d.actual_loss_s,d.selected_s)["rmse_s"]/metrics(d.actual_loss_s,d[baseline])["rmse_s"])
    report = dict(version=1, task="3/5-lap relative running-time forecast against current adjacent rival",
        selected_model=frozen, baseline=baseline, evaluation_rounds=[9,10,11,12],
        selection="Equal event/horizon MSE on R07-R08; relative learner trains on earlier out-of-event forecasts from R04 onward",
        **metrics(final.actual_loss_s, final.selected_s), baseline_rmse_s=metrics(final.actual_loss_s,final[baseline])["rmse_s"],
        improvement_pct=gain(final),
        improvement_event_bootstrap_95=cluster_bootstrap(final.assign(actual_s=final.actual_loss_s), baseline),
        issued=int((result["round"]>=9).sum()), scored=len(final),
        candidate_development_mse={n:balanced_mse(dev,n) for n in BATTLE_CANDIDATES},
        candidates={n:metrics(final.actual_loss_s,final[n]) for n in BATTLE_CANDIDATES},
        horizons=[dict(horizon=h, **metrics(d.actual_loss_s,d.selected_s), improvement_pct=gain(d),
            coverage=float(((d.selected_s-d.actual_loss_s).abs()<=d.radius_s).mean()),
            mean_interval_width_s=float(2*d.radius_s.mean())) for h,d in final.groupby("horizon")],
        per_event=[dict(round=int(r), **metrics(d.actual_loss_s,d.selected_s), improvement_pct=gain(d)) for r,d in final.groupby("round")],
        alerts={n:alert_metrics(final,n) for n in ("selected_s",baseline)},
        threshold_regret_improvement_event_bootstrap_95=regret_bootstrap(final,baseline),
        nonoverlapping_audit={"rule":"horizon=5, issued lap divisible by 5; adjacent cars can still be correlated",
            **metrics(final.loc[(final.horizon==5)&(final.lap%5==0)].actual_loss_s,
                      final.loc[(final.horizon==5)&(final.lap%5==0)].selected_s),
            "improvement_pct":gain(final.loc[(final.horizon==5)&(final.lap%5==0)])},
        alert_sensitivity=[dict(threshold_s=t, model=alert_metrics(final,"selected_s",t),
            baseline=alert_metrics(final,baseline,t)) for t in (1.,2.,3.)],
        limitations=["Relative time is not track position or observed race time saved.",
            "Only continued same-stint green running is scored; pit and neutralisation interruptions are disclosed.",
            "Adjacent position at the same lap count does not establish physical proximity for lapped cars; enter the real gap before an attack scenario.",
            "Only two development races for the relative learner and four reused evaluation races; new blind races are still required.",
            "Attack budgets assume both cars stop and use user-supplied warm-up, traffic, service and degradation costs."])
    write_json(ROOT/"artifacts/demo/intelligence/battle_report.json", report)
    print(json.dumps({k:v for k,v in report.items() if k not in ("candidates", "limitations", "alert_sensitivity")}, indent=2))


if __name__ == "__main__":
    main()
