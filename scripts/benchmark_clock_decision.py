"""Move the existing stop estimator to driver timestamps without model retuning."""
from pathlib import Path
import json, sys
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from pitwall.clockmodel import clock_features
from pitwall.stopvalue import stop_table
from pitwall.decision import fit_decision, SLICKS
from pitwall.intelligence import interval_radius, metrics
from benchmark_intelligence import write_json

def main():
    folder=ROOT/'artifacts/demo/decision-clock';folder.mkdir(exist_ok=True)
    races=[json.loads(p.read_text()) for p in sorted((ROOT/'artifacts/demo/replay').glob('R*.json'))]
    features=[]
    for race in races:
        x,_=clock_features(race);features.append(x.loc[x.horizon==1])
    one=pd.concat(features,ignore_index=True)
    labels=stop_table(pd.read_parquet(ROOT/'data/season_2026.parquet')).rename(columns={'Round':'round','Driver':'driver','PitLap':'lap'})
    stops=labels.merge(one,on=['round','driver','lap'],validate='one_to_one')
    selected=json.loads((ROOT/'artifacts/demo/intelligence/decision_report.json').read_text())['selected_model']
    history=[]
    for race in races:
        rnd=race['round'];snapshots=[]
        if rnd<4:
            write_json(folder/f'R{rnd:02d}.json',dict(round=rnd,snapshots=[],status='Collecting earlier races'));continue
        train=stops.loc[stops['round']<rnd];test=stops.loc[stops['round']==rnd].copy()
        model=fit_decision(train,selected)
        radius=interval_radius(pd.concat(history).selected_s-pd.concat(history).step_obs) if history else None
        test['selected_s']=model.predict(test);test['baseline']=train.step_obs.mean();test['radius_s']=radius;history.append(test)
        now=one.loc[one['round']==rnd];scenarios={}
        for compound in SLICKS:
            query=now.copy();query['pair']=query.compound+'>'+compound
            for row,value in zip(query.itertuples(),model.predict(query)):
                scenarios.setdefault((row.driver,int(row.lap)),{})[compound]=dict(step_s=float(value),radius_s=radius,
                    supported=bool(np.isfinite(value)),training_stops=model.support.get(row.pair,0),
                    extrapolating=not model.age_range[0]<=row.age<=model.age_range[1])
        for r in now.itertuples():
            snapshots.append(dict(driver=r.driver,lap=int(r.lap),issued_s=r.issued_s,compound=r.compound,tyre_age=r.age,
                inputs=dict(age=r.age,pace_trend_s_per_lap=r.kalman_trend,field_relative_s=r.field_relative,
                    track_temp_c=None if r.weather_missing else r.track_temp_c,traffic_close=None if r.traffic_missing else r.traffic_close),
                stop_scenarios=scenarios[r.driver,int(r.lap)]))
        write_json(folder/f'R{rnd:02d}.json',dict(round=rnd,snapshots=snapshots,training_through_round=rnd-1,
            model=model.to_dict(),basis='Existing stop architecture; per-driver timestamp inputs; earlier races only',
            limitation='Observed pre/post pace recovery includes residual confounding. Compound is a requested scenario; uncertain estimates are not guaranteed tyre gains.'))
        print(f'R{rnd:02d}: {len(snapshots)} clock stop snapshots',flush=True)
    scored=pd.concat(history,ignore_index=True);scored.to_csv(ROOT/'artifacts/clock_decision_predictions_2026.csv',index=False)
    final=scored.loc[scored['round']>=9].dropna(subset=['selected_s'])
    report=dict(selected_model=selected,**metrics(final.step_obs,final.selected_s),baseline_rmse_s=metrics(final.step_obs,final.baseline)['rmse_s'],
        protocol='Previously selected deployed architecture frozen; exact driver timestamp inputs; earlier-race training; reused R09-R12 evaluation',
        limitations=['Historical retrospectively cleaned stop labels, not physical wear.','Weather and traffic are context; the frozen factorized estimator uses pace state, tyre age, compound and race context.','This moves existing stop estimates to the clock; it is not a newly proven strategy advantage.'])
    write_json(folder/'report.json',report);print(json.dumps(report,indent=2))
if __name__=='__main__':main()
