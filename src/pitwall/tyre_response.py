"""Pre-stop tyre-response challengers; feature lists exclude post-stop outcomes."""
from dataclasses import dataclass
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

SLICKS = ('SOFT', 'MEDIUM', 'HARD')
PACE = ('kalman_trend', 'mean3_minus_last', 'mean8_minus_last', 'spread',
        'field_relative', 'field_delta', 'progress')
ENVIRONMENT = ('track_temp_c', 'track_temp_change_c', 'weather_missing',
               'traffic_close', 'traffic_change', 'traffic_missing')


def design(rows, spec):
    x = pd.DataFrame(index=rows.index)
    old, new = rows.pair.str.split('>').str[0], rows.pair.str.split('>').str[1]
    for compound in SLICKS:
        x['old_'+compound] = (old == compound).astype(float)
        x['new_'+compound] = (new == compound).astype(float)
        # A bounded age basis shares statistical strength across sparse transitions.
        x['age_'+compound] = (old == compound)*(-np.expm1(-rows.age/20))
    x['age'] = rows.age/25
    x['age2'] = (rows.age/25)**2
    if spec != 'age':
        for col in PACE:
            x[col] = rows[col]
        x['pace_scale'] = rows.pace_scale/90
    if spec == 'environment':
        for col in ENVIRONMENT:
            x[col] = rows[col]
        for c in SLICKS:
            x['thermal_'+c] = (old == c)*rows.age/25*(rows.track_temp_c-35)/10
    return x.astype(float).replace([np.inf, -np.inf], np.nan).fillna(0)


@dataclass
class ResponseModel:
    pipeline: object
    spec: str
    normalized: bool
    support: dict
    age_support: dict

    def predict(self, rows):
        values = self.pipeline.predict(design(rows, self.spec))
        if self.normalized:
            values *= rows.pace_scale.to_numpy()/90
        return np.where(rows.pair.isin(self.support), values, np.nan)

    def to_dict(self):
        scaler, ridge = self.pipeline.steps[0][1], self.pipeline.steps[1][1]
        coefficients = ridge.coef_/scaler.scale_
        intercept = ridge.intercept_-np.dot(coefficients,scaler.mean_)
        return dict(spec=self.spec,normalized=self.normalized,intercept=float(intercept),
            coefficients=dict(zip(scaler.feature_names_in_,coefficients.tolist())),
            pair_counts=self.support,age_support={k:list(v) for k,v in self.age_support.items()},
            normalized_reference_pace_s=90,
            inputs='Requested compound, recorded tyre age, pace state, race progress, track temperature and observed traffic; no post-stop input')


def fit_response(rows, target, spec, alpha=64, normalized=False, balanced=False):
    if rows['round'].nunique() < 3:
        raise ValueError('Three earlier races are required')
    y = rows[target].to_numpy(float)
    if normalized:
        y = y*90/rows.pace_scale.to_numpy()
    pipeline = make_pipeline(StandardScaler(), Ridge(alpha=alpha))
    weights = np.ones(len(rows))
    if balanced:
        weights = rows['round'].map(1/rows['round'].value_counts()).to_numpy()
        weights *= len(rows)/weights.sum()
    pipeline.fit(design(rows, spec), y, ridge__sample_weight=weights)
    support = {k:int(v) for k,v in rows.pair.value_counts().items()}
    age_support = {k:(float(g.age.min()),float(g.age.max())) for k,g in rows.groupby('pair')}
    return ResponseModel(pipeline,spec,normalized,support,age_support)
