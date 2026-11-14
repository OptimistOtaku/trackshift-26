"""Select on R04-R08, then score one frozen challenger on reused R09-R12.

New runs are research iterations, not blind tests. All candidate specifications
are declared before fitting; evaluation outcomes cannot choose the model.
"""
from pathlib import Path
import json, sys, hashlib
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from pitwall.clockmodel import clock_features
from pitwall.stopvalue import stop_table
from pitwall.decision import fit_decision
from pitwall.tyre_response import fit_response
from pitwall.intelligence import metrics
from benchmark_intelligence import write_json

CONFIGS = {'mean':None, 'existing_factorized':'existing'}
for spec in ('age','state','environment'):
    for alpha in (16,64,256):
        for normalized in (False,True):
            CONFIGS[f'{spec}_a{alpha}_'+('normalized' if normalized else 'seconds')] = dict(spec=spec,alpha=alpha,normalized=normalized)
for alpha in (64,256):
    CONFIGS[f'environment_a{alpha}_balanced'] = dict(spec='environment',alpha=alpha,balanced=True)


def predict_candidate(train,test,target,name):
    if name == 'mean': return np.full(len(test),train[target].mean())
    if name == 'existing_factorized':
        return fit_decision(train.assign(step_obs=train[target]),'factorized').predict(test)
    return fit_response(train,target,**CONFIGS[name]).predict(test)


def load_tables():
    labels=ROOT/'artifacts/recovery_labels_2026.csv'
    strict=pd.read_csv(labels)
    races=[json.loads(p.read_text()) for p in sorted((ROOT/'artifacts/demo/replay').glob('R[0-9][0-9].json'))]
    features=[]
    for race in races:
        x,_=clock_features(race)
        features.append(x.loc[x.horizon==1])
    one=pd.concat(features,ignore_index=True)
    legacy=stop_table(pd.read_parquet(ROOT/'data/season_2026.parquet')).rename(columns={'Round':'round','Driver':'driver','PitLap':'lap'})
    legacy=legacy.merge(one,on=['round','driver','lap'],validate='one_to_one')
    return {'deployed_stop_response':(legacy,'step_obs'),
            'strict_raw_response':(strict,'raw_step_s'),
            'strict_relative_response':(strict,'relative_step_s')}


def main():
    out=ROOT/'artifacts/demo/tyre-challenge';out.mkdir(exist_ok=True)
    tables=load_tables();reports={};predictions=[]
    for name,(rows,target) in tables.items():
        data=rows.loc[rows[target].notna()].copy()
        dev=[]
        for rnd in range(4,9):
            train=data.loc[data['round']<rnd];test=data.loc[data['round']==rnd].copy()
            if test.empty:continue
            for candidate in CONFIGS:
                test[candidate]=predict_candidate(train,test,target,candidate)
            dev.append(test)
        development=pd.concat(dev,ignore_index=True)
        # Score candidates on the exact same supported observations as the old model.
        eligible=development.dropna(subset=list(CONFIGS))
        scores={c:float(eligible.assign(error=(eligible[c]-eligible[target])**2).groupby('round').error.mean().mean()) for c in CONFIGS}
        selected=min(scores,key=scores.get)
        selection=dict(selected=selected,config=CONFIGS[selected],development_event_mse=scores,
            development_scored=len(eligible),development_issued=len(development),candidates=len(CONFIGS),
            protocol='Choice uses only R04-R08 earlier-race predictions; no evaluation outcomes enter selection')
        write_json(out/(name+'_selection.json'),selection)
        development.to_csv(out/(name+'_development.csv'),index=False)
        print(name,'FROZEN',selected,'development MSE',round(scores[selected],4),'mean',round(scores['mean'],4),flush=True)
        results=[]
        for rnd in range(9,13):
            train=data.loc[data['round']<rnd];test=data.loc[data['round']==rnd].copy()
            if test.empty:continue
            for candidate in set((selected,'mean','existing_factorized')):
                test[candidate]=predict_candidate(train,test,target,candidate)
            test['selected_s']=test[selected];results.append(test)
        final=pd.concat(results,ignore_index=True).dropna(subset=['selected_s','existing_factorized'])
        m=metrics(final[target],final.selected_s);baseline=metrics(final[target],final['mean']);existing=metrics(final[target],final.existing_factorized)
        rng=np.random.default_rng(26)
        groups=[g for _,g in final.groupby('round')]
        draws=[]
        for _ in range(5000):
            boot=pd.concat([groups[i] for i in rng.integers(0,len(groups),len(groups))])
            draws.append(100*(1-np.sqrt(np.mean((boot.selected_s-boot[target])**2)/np.mean((boot['mean']-boot[target])**2))))
        report=dict(**selection,**m,target=target,baseline_rmse_s=baseline['rmse_s'],existing_rmse_s=existing['rmse_s'],
            event_bootstrap_95_improvement_pct=np.quantile(draws,[.025,.975]).tolist(),
            improvement_vs_mean_pct=100*(1-m['rmse_s']/baseline['rmse_s']),
            improvement_vs_existing_pct=100*(1-m['rmse_s']/existing['rmse_s']),
            per_event=[dict(round=int(r),**metrics(g[target],g.selected_s),baseline_rmse_s=metrics(g[target],g['mean'])['rmse_s']) for r,g in final.groupby('round')])
        reports[name]=report
        final['experiment']=name;final['truth_s']=final[target];predictions.append(final)
        print(name,{k:report[k] for k in ('selected','n','rmse_s','baseline_rmse_s','existing_rmse_s','improvement_vs_mean_pct')},flush=True)
    pd.concat(predictions,ignore_index=True).to_csv(out/'predictions.csv',index=False)
    write_json(out/'report.json',dict(experiments=reports,
        protocol='Bounded new research iteration on reused races. Development selects configuration; only the frozen choice is scored on R09-R12. Targets evaluated separately, never pooled or relabelled as physical wear.',
        source_sha256=hashlib.sha256((ROOT/'artifacts/recovery_labels_2026.csv').read_bytes()).hexdigest()))

if __name__=='__main__':main()
