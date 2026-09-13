"""Observable tyre-change recovery, with matched stay-out controls.

Recovery is pace, not physical rubber loss. Controls also age, so the adjusted
label is relative to continued running, not an isolated causal tyre effect.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import Ridge, HuberRegressor
from sklearn.ensemble import ExtraTreesRegressor, RandomForestRegressor
from .intelligence import usable, finite

SPECS = ('mean', 'ridge_age', 'ridge_state', 'ridge_environment', 'huber', 'forest', 'extra')
ANCHOR_SPECS = ('ridge_anchor', 'forest_anchor', 'extra_anchor')
ADAPTATIONS = (0, 5, 15)
TARGETS = ('raw_step_s', 'relative_step_s')


def add_stint_anchors(features):
    """Personal early-stint reference, formed only from already-issued rows."""
    features=features.sort_values(['issued_s','driver']).copy()
    history={}; values=[]
    for row in features.itertuples():
        key=(row.driver,row.segment)
        prior=history.setdefault(key,[])
        prior.append(row)
        anchor=prior[:3]; recent=prior[-3:]
        values.append(dict(stint_pace_loss=np.mean([p.pace_scale for p in recent])-np.mean([p.pace_scale for p in anchor]),
            stint_relative_loss=np.mean([p.field_relative for p in recent])-np.mean([p.field_relative for p in anchor]),
            anchor_age=float(np.mean([p.age for p in anchor])),
            anchor_span=row.age-float(np.mean([p.age for p in anchor])),
            anchor_traffic_change=np.mean([p.traffic_close for p in recent])-np.mean([p.traffic_close for p in anchor]),
            anchor_traffic_missing=max(p.traffic_missing for p in anchor+recent)))
    return pd.concat([features.reset_index(drop=True),pd.DataFrame(values)],axis=1)


def continuous(rows):
    return bool(rows) and all(r is not None and usable(r) and finite(r.get('completed_s')) for r in rows) and all(
        b['lap'] == a['lap']+1 and b['compound'] == a['compound'] and b['tyre_age'] == a['tyre_age']+1
        for a, b in zip(rows, rows[1:]))


def stop_labels(race):
    """Strict windows; no cherry-picked fast post-stop laps or future features.

    Three consecutive laps before the in-lap and three after the out-lap.
    All six must be usable; the intervening pit laps must remain green.
    Up to five non-stopping controls chosen using PRE-window pace and trend.
    """
    lookup = {(r['driver'], r['lap']): r for r in race['laps_data']}
    drivers = sorted({d for d, _ in lookup})
    labels = []
    for pit in race['laps_data']:
        if not pit.get('in_lap') or pit.get('track_status') != '1': continue
        d, p = pit['driver'], pit['lap']
        out = lookup.get((d, p+1))
        if not out or not out.get('out_lap') or out.get('track_status') != '1': continue
        pre = [lookup.get((d, k)) for k in range(p-3, p)]
        post = [lookup.get((d, k)) for k in range(p+2, p+5)]
        if not continuous(pre) or not continuous(post): continue
        if post[0]['tyre_age'] >= pre[-1]['tyre_age']: continue
        before = np.mean([r['lap_time_s'] for r in pre])
        after = np.mean([r['lap_time_s'] for r in post])
        controls = []
        for other in drivers:
            if other == d: continue
            whole = [lookup.get((other, k)) for k in range(p-3, p+5)]
            if not continuous(whole): continue
            a, b = whole[:3], whole[-3:]
            # Matching uses no post-window outcome.
            distance = abs(np.mean([r['lap_time_s'] for r in a])-before)
            distance += abs((a[-1]['lap_time_s']-a[0]['lap_time_s'])-(pre[-1]['lap_time_s']-pre[0]['lap_time_s']))
            controls.append((distance, other, np.mean([r['lap_time_s'] for r in a])-np.mean([r['lap_time_s'] for r in b]), whole[-1]['completed_s']))
        controls = sorted(controls)[:5]
        common = float(np.median([c[2] for c in controls])) if len(controls)>=3 else np.nan
        # Eligibility itself examines all candidate control windows. Wait for
        # their source observations too, not merely the selected five outcomes.
        selection_s=max(r['completed_s'] for r in race['laps_data']
            if p-3<=r['lap']<=p+4 and finite(r.get('completed_s')))
        # Negative control: the same spacing entirely BEFORE the actual stop.
        # Match anew using only that placebo's pre-window, not the actual stop.
        placebo=np.nan; placebo_controls=[]
        history=[lookup.get((d,k)) for k in range(p-8,p)]
        if continuous(history):
            ha,hb=history[:3],history[-3:]
            hm=float(np.mean([r['lap_time_s'] for r in ha]))
            for other in drivers:
                if other==d: continue
                control=[lookup.get((other,k)) for k in range(p-8,p)]
                if not continuous(control): continue
                ca,cb=control[:3],control[-3:]
                distance=abs(np.mean([r['lap_time_s'] for r in ca])-hm)
                distance+=abs((ca[-1]['lap_time_s']-ca[0]['lap_time_s'])-(ha[-1]['lap_time_s']-ha[0]['lap_time_s']))
                placebo_controls.append((distance,other,np.mean([r['lap_time_s'] for r in ca])-np.mean([r['lap_time_s'] for r in cb])))
            placebo_controls=sorted(placebo_controls)[:5]
            if len(placebo_controls)>=3:
                placebo=hm-float(np.mean([r['lap_time_s'] for r in hb]))-float(np.median([c[2] for c in placebo_controls]))
        def traffic(rows):
            vals = [r['frac_close'] for r in rows if r.get('traffic_observed') and finite(r.get('frac_close'))]
            return float(np.mean(vals)) if len(vals)==len(rows) else np.nan
        labels.append(dict(round=race['round'], driver=d, lap=p-1, issued_s=pre[-1]['completed_s'],
            label_s=selection_s, control_selection_s=selection_s,
            pair=pre[-1]['compound']+'>'+post[0]['compound'], new_compound=post[0]['compound'],
            old_age=pre[-1]['tyre_age'],new_age=post[0]['tyre_age'],
            raw_step_s=float(before-after), control_step_s=common, relative_step_s=float(before-after-common),
            controls=','.join(c[1] for c in controls), control_n=len(controls),
            placebo_relative_s=placebo, pretrend_corrected_s=float(before-after-common-placebo),
            control_mad_s=float(np.median(abs(np.array([c[2] for c in controls])-common))) if len(controls)>=3 else np.nan,
            pre_traffic=traffic(pre), post_traffic=traffic(post), pre_mean_s=float(before), post_mean_s=float(after)))
    return pd.DataFrame(labels)


def design(rows, spec):
    x = pd.DataFrame(index=rows.index)
    for c in ('SOFT', 'MEDIUM', 'HARD'):
        x['old_'+c] = (rows.compound==c).astype(float)
        x['new_'+c] = (rows.new_compound==c).astype(float)
    x['age'] = rows.age/25
    # Fixed knots, no data-dependent choice from evaluation.
    for knot in (10, 20, 30): x['age_above_'+str(knot)] = np.maximum(rows.age-knot, 0)/25
    if spec not in ('mean', 'ridge_age'):
        for c in ('progress','slope','kalman_trend','last_minus_median','spread','mean3_minus_last','mean8_minus_last','field_delta','field_relative','field_spread'):
            x[c] = rows[c]
        x['pace_scale'] = rows.pace_scale/100
    if spec in ('ridge_environment','huber','forest','extra',*ANCHOR_SPECS):
        for c in ('traffic_close','traffic_missing','traffic_change','weather_missing','thermal_age','traffic_age'):
            x[c] = rows[c]
        x['track_temp_c'] = (rows.track_temp_c-35)/10
        x['track_temp_change_c'] = rows.track_temp_change_c/10
    if spec in ANCHOR_SPECS:
        for c in ('stint_pace_loss','stint_relative_loss','anchor_age','anchor_span','anchor_traffic_change','anchor_traffic_missing'):
            x[c]=rows[c]
    return x


def fit_model(rows, spec, target):
    y = rows[target].to_numpy()
    if spec == 'mean': return float(np.mean(y))
    if spec.startswith('ridge'): model = make_pipeline(StandardScaler(), Ridge(alpha=40))
    elif spec == 'huber': model = make_pipeline(StandardScaler(), HuberRegressor(alpha=5, max_iter=1000))
    elif spec.startswith('forest'): model = RandomForestRegressor(n_estimators=160, min_samples_leaf=12, max_depth=5, max_features=.8, random_state=26, n_jobs=2)
    else: model = ExtraTreesRegressor(n_estimators=160, min_samples_leaf=10, max_depth=5, max_features=.8, random_state=26, n_jobs=2)
    return model.fit(design(rows,spec), y)


def predict(model, rows, spec):
    return np.full(len(rows),model) if spec=='mean' else model.predict(design(rows,spec))


def adaptation(history, now, target, prediction_col, strength):
    """Only labels fully resolved before this timestamp can update this race."""
    if not strength: return 0., 0
    known = history.loc[(history.label_s < now) & history[target].notna()]
    residual = (known[target]-known[prediction_col]).to_numpy()
    # Bound one incident's influence, while retaining untrimmed evaluation.
    return float(np.clip(residual, -3, 3).sum()/(len(residual)+strength)), len(residual)
