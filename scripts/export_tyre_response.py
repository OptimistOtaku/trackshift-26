"""Promote the development-selected tyre response into the shared clock strategy.

The earlier factorized audit remains reproducible via benchmark_clock_decision.py.
Only pre-stop features enter prediction; empirical intervals use earlier races.
"""
from pathlib import Path
import sys,json
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from pitwall.tyre_response import fit_response, design
from pitwall.clockmodel import clock_features
from pitwall.intelligence import metrics,interval_radius
from pitwall.decision import fit_decision,SLICKS
from challenge_tyre_response import load_tables,CONFIGS
from benchmark_intelligence import write_json


def main():
    folder=ROOT/'artifacts/demo/decision-clock'
    challenge=json.loads((ROOT/'artifacts/demo/tyre-challenge/report.json').read_text())
    evidence=challenge['experiments']['deployed_stop_response']
    selection=evidence['selected'];config=CONFIGS[selection]
    if not isinstance(config,dict) or evidence['rmse_s']>=min(evidence['baseline_rmse_s'],evidence['existing_rmse_s']):
        raise ValueError('Challenger has not earned promotion on the declared comparison')
    stops,_=load_tables()['deployed_stop_response']
    history=[]
    for path in sorted((ROOT/'artifacts/demo/replay').glob('R[0-9][0-9].json')):
        race=json.loads(path.read_text());rnd=race['round']
        if rnd<4:continue
        train=stops.loc[stops['round']<rnd];test=stops.loc[stops['round']==rnd].copy()
        model=fit_response(train,'step_obs',**config)
        radius=interval_radius(pd.concat(history).selected_s-pd.concat(history).step_obs) if history else None
        test['selected_s']=model.predict(test);test['baseline']=train.step_obs.mean()
        test['previous_s']=fit_decision(train,'factorized').predict(test);test['radius_s']=radius
        history.append(test)
        x,_=clock_features(race);now=x.loc[x.horizon==1];scenarios={}
        for compound in SLICKS:
            query=now.copy();query['pair']=query.compound+'>'+compound
            features=design(query,model.spec)
            params=model.to_dict()
            for row,value,f in zip(query.itertuples(),model.predict(query),features.to_dict('records')):
                lo,hi=model.age_support.get(row.pair,(np.nan,np.nan))
                # Match the previous product's global age gate, and expose the
                # narrower transition range as an additional extrapolation warning.
                global_lo,global_hi=float(train.age.min()),float(train.age.max())
                scale=row.pace_scale/90 if model.normalized else 1
                terms={k:float(v*params['coefficients'][k]*scale) for k,v in f.items()}
                attribution=dict(intercept_s=params['intercept']*scale,
                    compound_s=sum(v for k,v in terms.items() if k.startswith(('old_','new_'))),
                    age_s=sum(v for k,v in terms.items() if k.startswith('age')),
                    environment_s=sum(v for k,v in terms.items() if k in ('track_temp_c','track_temp_change_c','weather_missing','traffic_close','traffic_change','traffic_missing') or k.startswith('thermal_')),
                    pace_context_s=sum(v for k,v in terms.items() if k in ('kalman_trend','mean3_minus_last','mean8_minus_last','spread','field_relative','field_delta','progress','pace_scale')))
                scenarios.setdefault((row.driver,int(row.lap)),{})[compound]=dict(step_s=float(value),radius_s=radius,
                    supported=bool(np.isfinite(value)),training_stops=model.support.get(row.pair,0),
                    extrapolating=not global_lo<=row.age<=global_hi,
                    transition_age_extrapolation=not lo<=row.age<=hi,transition_age_support=[lo,hi],
                    attribution=attribution)
        snapshots=[dict(driver=r.driver,lap=int(r.lap),issued_s=r.issued_s,compound=r.compound,tyre_age=r.age,
            inputs=dict(age=r.age,pace_trend_s_per_lap=r.kalman_trend,field_relative_s=r.field_relative,
                track_temp_c=None if r.weather_missing else r.track_temp_c,traffic_close=None if r.traffic_missing else r.traffic_close),
            model_features=design(now.loc[[r.Index]].assign(pair=r.compound+'>'+r.compound),model.spec).iloc[0].to_dict(),
            stop_scenarios=scenarios[r.driver,int(r.lap)]) for r in now.itertuples()]
        write_json(folder/path.name,dict(round=rnd,snapshots=snapshots,training_through_round=rnd-1,
            selected_model=selection,model=model.to_dict(),
            basis='Pace-normalized, strongly regularized tyre-response model. Track temperature and observed traffic are model inputs. Coefficients train on earlier races only; architecture chosen on R04-R08.',
            limitation='Predicts observational clean-lap recovery across a stop, not physical wear. R04-R08 are development replays; R09-R12 are reused evaluation races.'))
        print(f'R{rnd:02d}: {len(snapshots)} improved tyre-response snapshots',flush=True)
    scored=pd.concat(history,ignore_index=True);scored.to_csv(ROOT/'artifacts/clock_decision_predictions_2026.csv',index=False)
    final=scored.loc[scored['round']>=9].dropna(subset=['selected_s','previous_s'])
    report=dict(selected_model=selection,**metrics(final.step_obs,final.selected_s),
        baseline_rmse_s=metrics(final.step_obs,final.baseline)['rmse_s'],previous_rmse_s=metrics(final.step_obs,final.previous_s)['rmse_s'],
        improvement_pct=evidence['improvement_vs_mean_pct'],improvement_vs_previous_pct=evidence['improvement_vs_existing_pct'],
        event_bootstrap_95_improvement_pct=evidence.get('event_bootstrap_95_improvement_pct'),
        interval_coverage=float(((final.selected_s-final.step_obs).abs()<=final.radius_s).mean()),
        protocol='New bounded research iteration: model chosen on R04-R08, earlier-race coefficient fits, one frozen choice evaluated on reused R09-R12.',
        feature_inputs=['tyre age','old/requested compound','recent pace state','race progress','track temperature','observed traffic'],
        per_event=evidence['per_event'],strict_relative_validation=challenge['experiments']['strict_relative_response'],
        limitations=['Retrospectively cleaned historical stop labels; not physical wear or randomized tyre effects.','Four evaluation races reused in prior research; improvement is exploratory, not a new blind test.','Actual fuel, tyre core temperature and pressure are unavailable. Future traffic remains a scenario assumption.','Coefficient contributions explain the model, not causal effects. Transition-specific age support is exposed alongside the broader model age gate.'])
    write_json(folder/'report.json',report)
    print(json.dumps({k:report[k] for k in ('rmse_s','baseline_rmse_s','previous_rmse_s','improvement_pct','interval_coverage')},indent=2))

if __name__=='__main__':main()
