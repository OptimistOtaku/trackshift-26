import json
import sys
import unittest
from pathlib import Path
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
sys.path.insert(0,str(ROOT/'scripts'))
from pitwall.tyre_response import fit_response,design
from challenge_tyre_response import load_tables,CONFIGS


class TyreResponseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data,_=load_tables()['deployed_stop_response']
        cls.train=cls.data.loc[cls.data['round']<11]
        cls.query=cls.data.loc[cls.data['round']==11].iloc[:4].copy()
        cls.model=fit_response(cls.train,'step_obs','environment',256,True)

    def test_post_stop_outcomes_cannot_enter_prediction(self):
        changed=self.query.copy()
        for col in ('step_obs','t_new','age_new','fuel_new','close_new','d_fuel','d_close'):
            changed[col]=99999
        np.testing.assert_array_equal(self.model.predict(self.query),self.model.predict(changed))

    def test_exported_linear_arithmetic_reproduces_pipeline(self):
        payload=self.model.to_dict()
        x=design(self.query,self.model.spec)
        result=payload['intercept']+x.to_numpy()@np.array([payload['coefficients'][c] for c in x.columns])
        result*=self.query.pace_scale.to_numpy()/90
        np.testing.assert_allclose(result,self.model.predict(self.query),atol=1e-10)
        changed=self.query.copy();changed['track_temp_c']+=5;changed['traffic_close']+=.2
        self.assertGreater(np.max(abs(self.model.predict(changed)-self.model.predict(self.query))),1e-5)

    def test_saved_race_model_uses_only_earlier_race_fit(self):
        saved=json.loads((ROOT/'artifacts/demo/decision-clock/R11.json').read_text())
        self.assertEqual(saved['training_through_round'],10)
        np.testing.assert_allclose(list(saved['model']['coefficients'].values()),list(self.model.to_dict()['coefficients'].values()),atol=5.1e-7)
        for snapshot in saved['snapshots']:
            for scenario in snapshot['stop_scenarios'].values():
                if scenario['supported']:
                    self.assertAlmostEqual(sum(scenario['attribution'].values()),scenario['step_s'],places=5)

    def test_development_selection_and_final_metrics_recompute(self):
        report=json.loads((ROOT/'artifacts/demo/tyre-challenge/report.json').read_text())
        predictions=pd.read_csv(ROOT/'artifacts/demo/tyre-challenge/predictions.csv')
        for name,result in report['experiments'].items():
            dev=pd.read_csv(ROOT/f'artifacts/demo/tyre-challenge/{name}_development.csv').dropna(subset=list(CONFIGS))
            self.assertLessEqual(dev['round'].max(),8)
            scores={c:dev.assign(e=(dev[c]-dev[result['target']])**2).groupby('round').e.mean().mean() for c in CONFIGS}
            self.assertEqual(min(scores,key=scores.get),result['selected'])
            final=predictions.loc[predictions.experiment==name]
            self.assertEqual(len(final),result['n'])
            self.assertAlmostEqual(np.sqrt(np.mean((final.selected_s-final.truth_s)**2)),result['rmse_s'],places=5)
            self.assertAlmostEqual(np.sqrt(np.mean((final['mean']-final.truth_s)**2)),result['baseline_rmse_s'],places=5)

    def test_new_model_refuses_unseen_transition(self):
        changed=self.query.copy();changed['pair']='WET>HARD'
        self.assertTrue(np.isnan(self.model.predict(changed)).all())


if __name__=='__main__':unittest.main()
