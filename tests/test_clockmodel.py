import copy
import hashlib
import json
import sys
import unittest
from pathlib import Path
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from pitwall.clockmodel import clock_features

def race():
    return dict(round=1,laps=12,laps_data=[dict(driver=d,lap=l,completed_s=l*80+offset,
        lap_time_s=80+.04*l+offset/10,compound='MEDIUM',tyre_age=l,track_status='1',
        in_lap=False,out_lap=False) for d,offset in [('AAA',0),('BBB',25)] for l in range(1,13)])

class ClockTests(unittest.TestCase):
    def test_later_same_lap_opponent_cannot_change_earlier_forecast(self):
        a=race();b=copy.deepcopy(a)
        for row in b['laps_data']:
            if row['completed_s']>640:row['lap_time_s']=999
        xa,_=clock_features(a);xb,_=clock_features(b)
        pd.testing.assert_frame_equal(xa[xa.issued_s<=640].reset_index(drop=True),xb[xb.issued_s<=640].reset_index(drop=True))
    def test_timestamp_prefix_reproduces_full_run(self):
        a=race();prefix=dict(a,laps_data=[r for r in a['laps_data'] if r['completed_s']<=640])
        x,_=clock_features(a);p,_=clock_features(prefix)
        pd.testing.assert_frame_equal(x[x.issued_s<=640].reset_index(drop=True),p)
    def test_missing_timestamp_is_not_inferred_from_future(self):
        a=race();a['laps_data'][5]['completed_s']=None
        x,o=clock_features(a)
        self.assertFalse(((o.driver=='AAA')&(o.lap==6)).any())
    def test_duplicate_rows_fail(self):
        a=race();a['laps_data'].append(a['laps_data'][0])
        with self.assertRaises(ValueError):clock_features(a)

class ClockArtifactTests(unittest.TestCase):
    def test_report_matches_saved_predictions_and_sources(self):
        report=json.loads((ROOT/'artifacts/demo/clock/report.json').read_text())
        data=pd.read_csv(ROOT/'artifacts/clock_predictions_2026.csv')
        final=data.loc[(data['round']>=9)&data.scored]
        self.assertEqual(len(final),report['scored'])
        self.assertAlmostEqual(((final.selected_s-final.actual_s)**2).mean()**.5,report['rmse_s'],places=6)
        self.assertTrue((final.target_s>final.issued_s).all())
        for source in report['source_manifest']:
            self.assertEqual(hashlib.sha256((ROOT/source['path']).read_bytes()).hexdigest(),source['sha256'])
