"""Frozen development selection, strict stop windows and timestamp-safe adaptation."""
from pathlib import Path
import sys, json, hashlib
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from pitwall.clockmodel import clock_features
from pitwall.recovery import *
from pitwall.intelligence import metrics, interval_radius
from benchmark_intelligence import write_json


def main():
    out=ROOT/'artifacts/demo/recovery'; out.mkdir(exist_ok=True)
    races=[json.loads(p.read_text()) for p in sorted((ROOT/'artifacts/demo/replay').glob('R*.json'))]
    tables=[]; inputs={}
    for race in races:
        x,_=clock_features(race); x=add_stint_anchors(x.loc[x.horizon==1].copy()); inputs[race['round']]=x
        labels=stop_labels(race)
        merged=labels.merge(x.drop(columns='issued_s'),on=['round','driver','lap'],validate='one_to_one') if len(labels) else pd.DataFrame()
        tables.append(merged)
        print(f"R{race['round']:02d}: {len(merged)} strict-window stops",flush=True)
    data=pd.concat(tables,ignore_index=True)
    data.to_csv(ROOT/'artifacts/recovery_labels_2026.csv',index=False)
    all_results=[]; locks={}; reports={}; model_cache={}
    specs=(*SPECS,*ANCHOR_SPECS)
    candidates=[f'{spec}@{a}' for spec in specs for a in ADAPTATIONS]
    for target in TARGETS:
        history=[]
        for rnd in range(4,13):
            train=data.loc[(data['round']<rnd)&data[target].notna()]
            test=data.loc[(data['round']==rnd)&data[target].notna()].copy()
            if rnd==9:
                dev=pd.concat(history,ignore_index=True)
                scores={c:float(dev.assign(e=(dev[c]-dev[target])**2).groupby('round').e.mean().mean()) for c in candidates}
                locks[target]=dict(selected=min(scores,key=scores.get),development_event_mse=scores)
                write_json(out/'selection.json',locks)
                print(target,'FROZEN',locks[target]['selected'],flush=True)
            for spec in specs:
                model=fit_model(train,spec,target); model_cache[target,rnd,spec]=model
                test[f'{spec}@0']=predict(model,test,spec) if len(test) else []
                for strength in (5,15):
                    test[f'{spec}@{strength}']=[p+adaptation(test,r.issued_s,target,f'{spec}@0',strength)[0] for r,p in zip(test.itertuples(),test[f'{spec}@0'])]
            history.append(test)
        scored=pd.concat(history,ignore_index=True); selected=locks[target]['selected']
        scored['selected_s']=scored[selected]; scored['target_name']=target
        all_results.append(scored)
        final=scored.loc[scored['round']>=9]
        m=metrics(final[target],final.selected_s); b=metrics(final[target],final['mean@0']); strong=metrics(final[target],final['mean@5'])
        dev=scored.loc[scored['round']<9]; radius=interval_radius(dev.selected_s-dev[target])
        reports[target]=dict(selected=selected,**m,baseline_rmse_s=b['rmse_s'],adaptive_mean_rmse_s=strong['rmse_s'],
            improvement_pct=100*(1-m['rmse_s']/b['rmse_s']),improvement_vs_adaptive_pct=100*(1-m['rmse_s']/strong['rmse_s']),
            radius_s=radius,coverage=float(((final.selected_s-final[target]).abs()<=radius).mean()),
            candidates={c:metrics(final[target],final[c]) for c in candidates},
            per_event=[dict(round=int(r),**metrics(g[target],g.selected_s),baseline_rmse_s=metrics(g[target],g['mean@5'])['rmse_s']) for r,g in final.groupby('round')])
        print(target,json.dumps({k:v for k,v in reports[target].items() if k not in ('candidates','per_event')}),flush=True)
    pd.concat(all_results,ignore_index=True).to_csv(ROOT/'artifacts/recovery_predictions_2026.csv',index=False)
    report=dict(protocol='R04–R08 development, choice frozen before R09–R12 reused evaluation; previous races train the base; only timestamp-resolved stops adapt the event',
        research_iteration='Two-stage exploratory study: initial 21 candidates archived in initial_report.json; personal stint anchors added in the second development selection. Evaluation races are reused, including between research iterations.',
        targets=reports,labels=len(data),matched_labels=int(data.relative_step_s.notna().sum()),
        method='Three consecutive green laps before the in-lap versus three after the out-lap. Up to five continuous stay-out controls matched on pre-stop pace and trend; minimum three for relative recovery.',
        limitations=['Observational pace recovery, not physical wear or a randomized causal tyre effect.','Controls also age; relative recovery is versus continued running, with residual driver, fuel and traffic confounding.','Post-stop traffic is label context only, never a predictor. Tyre temperature and pressure are unavailable.','Evaluation races were used in earlier product research; this is a new protocol on reused data, not a blind test.','Strict windows exclude interrupted stops; estimates do not include pit loss or the out-lap.'],
        source_manifest=[dict(path=str(p.relative_to(ROOT)).replace('\\','/'),sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in sorted((ROOT/'artifacts/demo/replay').glob('R*.json'))])
    write_json(out/'report.json',report)


if __name__=='__main__': main()
