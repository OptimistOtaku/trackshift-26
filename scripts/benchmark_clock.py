"""Audit the already chosen pace architecture under exact observation timestamps.

Does not retune architecture on reused evaluation. Writes a separate clock model
and evidence so historical lap-synchronous results remain reproducible.
"""
from pathlib import Path
import hashlib
import json
import os
import sys
os.environ.setdefault('OMP_NUM_THREADS','2')
os.environ.setdefault('OPENBLAS_NUM_THREADS','2')
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
import numpy as np
import pandas as pd
from pitwall.clockmodel import clock_features
from pitwall.intelligence import attach_targets,fit_candidates,predict_candidates,interval_radius,metrics
from benchmark_intelligence import write_json,cluster_bootstrap


def main():
    out=ROOT/'artifacts/demo/clock'
    out.mkdir(exist_ok=True)
    races=[json.loads(p.read_text()) for p in sorted((ROOT/'artifacts/demo/replay').glob('R*.json'))]
    parts=[]
    for race in races:
        x,obs=clock_features(race)
        data=attach_targets(x,obs)
        completions={(r.driver,r.lap):r.completed_s for r in obs.itertuples()}
        data['target_s']=[completions.get((r.driver,r.target_lap),np.nan) for r in data.itertuples()]
        data['scored'] &= data.target_s>data.issued_s
        parts.append(data)
    all_data=pd.concat(parts,ignore_index=True)
    selected=json.loads((ROOT/'artifacts/demo/intelligence/report.json').read_text())['selected_model']
    history=[]
    for race in races:
        rnd=race['round']
        if rnd<4:
            write_json(out/f'R{rnd:02d}.json',dict(round=rnd,snapshots=[],evaluation=[],status='Collecting earlier races'))
            continue
        current=all_data.loc[all_data['round']==rnd].copy()
        models=fit_candidates(all_data.loc[all_data['round']<rnd])
        predictions=predict_candidates(models,current)
        current['selected_s']=predictions[selected]
        current['persistence']=predictions['persistence']
        current['radius_s']=np.nan
        prior=pd.concat(history,ignore_index=True) if history else pd.DataFrame()
        for h in (1,3,5):
            if not prior.empty:
                cal=prior.loc[(prior.horizon==h)&prior.scored]
                radius=interval_radius(cal.selected_s-cal.actual_s)
                if radius is not None:current.loc[current.horizon==h,'radius_s']=radius
        history.append(current)
        snapshots=[]
        for (driver,lap),group in current.groupby(['driver','lap']):
            first=group.iloc[0]
            snapshots.append(dict(driver=driver,lap=int(lap),issued_s=first.issued_s,
                compound=first.compound,tyre_age=first.age,pace_trend_s_per_lap=first.kalman_trend,
                forecasts=[dict(horizon=int(r.horizon),target_lap=int(r.target_lap),pace_s=r.selected_s,
                    lower_s=r.selected_s-r.radius_s,upper_s=r.selected_s+r.radius_s) for r in group.itertuples()]))
        score=current.loc[current.scored]
        evaluation=[dict(driver=r.driver,issued_lap=int(r.lap),issued_s=r.issued_s,
            target_lap=int(r.target_lap),target_s=r.target_s,horizon=int(r.horizon),
            predicted_s=r.selected_s,actual_s=r.actual_s,baseline_s=r.persistence)
            for r in score.itertuples()]
        write_json(out/f'R{rnd:02d}.json',dict(round=rnd,status='ready',model=selected,
            training_through_round=rnd-1,basis='Each driver lap completion; only already received field observations',
            snapshots=sorted(snapshots,key=lambda s:s['issued_s']),evaluation=evaluation))
        print(f"R{rnd:02d}: {len(score)} scored; RMSE {metrics(score.actual_s,score.selected_s)['rmse_s']:.3f}",flush=True)
    result=pd.concat(history,ignore_index=True)
    result.to_csv(ROOT/'artifacts/clock_predictions_2026.csv',index=False)
    final=result.loc[(result['round']>=9)&result.scored]
    model=metrics(final.actual_s,final.selected_s);base=metrics(final.actual_s,final.persistence)
    report=dict(version=1,model=selected,architecture='Previously selected architecture fixed before timestamp audit; no candidate search on this evaluation',
        protocol='Per-driver completion timestamps; earlier-race fitting and interval calibration',
        evaluation='R09–R12 reused races, stricter timing protocol, not a new blind dataset',
        **model,baseline_rmse_s=base['rmse_s'],improvement_pct=100*(1-model['rmse_s']/base['rmse_s']),
        improvement_event_bootstrap_95=cluster_bootstrap(final,'persistence'),
        issued=int((result['round']>=9).sum()),scored=len(final),
        interval_coverage=float(((final.selected_s-final.actual_s).abs()<=final.radius_s).mean()),
        timing_violations=int((final.target_s<=final.issued_s).sum()),
        per_event=[dict(round=int(r),**metrics(g.actual_s,g.selected_s),baseline_rmse_s=metrics(g.actual_s,g.persistence)['rmse_s']) for r,g in final.groupby('round')],
        source_manifest=[dict(path=str(p.relative_to(ROOT)).replace('\\','/'),sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in sorted((ROOT/'artifacts/demo/replay').glob('R*.json'))],
        limitations=['Recorded timestamp replay, not an external live feed or a measured inference-latency trial.',
            'Pace includes tyre, fuel, traffic and track effects; physical wear remains unmeasured.',
            'Stop/rejoin and learned rival scenario models still use their labelled lap-synchronous protocol.',
            'Same-stint green continuations only; interruptions abstain.'])
    write_json(out/'report.json',report)
    print(json.dumps({k:v for k,v in report.items() if k not in ['source_manifest','limitations','per_event']},indent=2),flush=True)


if __name__=='__main__':main()
