"""Publish measured tyre-reset evidence and causal personal stint references."""
from pathlib import Path
import sys, json
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from pitwall.recovery import stop_labels, add_stint_anchors
from pitwall.clockmodel import clock_features
from benchmark_intelligence import write_json


def summary(data, column):
    data=data.dropna(subset=[column]); groups=[g[column].to_numpy() for _,g in data.groupby('round')]
    if not groups:return dict(n=0,events=0,mean_s=None,event_bootstrap_95_s=None)
    rng=np.random.default_rng(26)
    draws=[float(np.mean(np.concatenate([groups[i] for i in rng.integers(0,len(groups),len(groups))]))) for _ in range(3000)]
    return dict(n=len(data),events=len(groups),mean_s=float(data[column].mean()),median_s=float(data[column].median()),
        event_bootstrap_95_s=np.quantile(draws,[.025,.975]).tolist())


def main():
    folder=ROOT/'artifacts/demo/recovery'; folder.mkdir(exist_ok=True)
    tables=[]
    for path in sorted((ROOT/'artifacts/demo/replay').glob('R*.json')):
        race=json.loads(path.read_text()); labels=stop_labels(race); tables.append(labels)
        x,_=clock_features(race); x=add_stint_anchors(x.loc[x.horizon==1])
        snapshots=[dict(driver=r.driver,lap=int(r.lap),issued_s=r.issued_s,compound=r.compound,age=r.age,
            reference_age=r.anchor_age,reference_span=r.anchor_span,raw_drift_s=r.stint_pace_loss,
            relative_drift_s=r.stint_relative_loss,traffic_change=r.anchor_traffic_change,traffic_missing=bool(r.anchor_traffic_missing),
            track_temp_c=None if r.weather_missing else r.track_temp_c)
            for r in x.itertuples()]
        write_json(folder/path.name,dict(round=race['round'],snapshots=snapshots,stops=labels.to_dict('records'),
            basis='Personal mean of first three available forecast observations in the stint versus last three; field-relative pace drift. Only timestamps at/before issue. Not isolated wear.'))
    data=pd.concat(tables,ignore_index=True)
    data.to_csv(ROOT/'artifacts/recovery_observations_2026.csv',index=False)
    same=data.loc[data.pair.str.split('>').str[0]==data.pair.str.split('>').str[1]]
    # Paired diagnostics share the exact same stops, avoiding selection mismatch.
    paired=same.dropna(subset=['relative_step_s','placebo_relative_s'])
    evidence=dict(all_stops=summary(data,'relative_step_s'),same_compound=summary(same,'relative_step_s'),
        paired_same_compound=dict(actual=summary(paired,'relative_step_s'),placebo=summary(paired,'placebo_relative_s'),
            difference=summary(paired,'pretrend_corrected_s')),
        raw_labels=len(data),matched_labels=int(data.relative_step_s.notna().sum()),
        interpretation='Measured pace recovery after tyre-age resets. Same-compound subset avoids compound switching; matched stay-out controls remove some shared pace movement. The pre-stop placebo tests whether a similar recovery appears without a tyre change.',
        limitations='Retrospective selected green windows; nonrandom stops and residual driver, fuel, tyre-temperature and traffic confounding remain. Bootstrap describes these events, not independent wear validation. A placebo is a diagnostic, not proof of parallel trends.')
    write_json(folder/'evidence.json',evidence)
    print(json.dumps(evidence,indent=2))


if __name__=='__main__':main()
