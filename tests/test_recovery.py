import copy, hashlib, json, sys, unittest, subprocess
from pathlib import Path
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from pitwall.recovery import stop_labels, adaptation, add_stint_anchors
from pitwall.clockmodel import clock_features

def race():
    rows=[]
    for d,offset in [('AAA',0),('BBB',.1),('CCC',-.1),('DDD',.2),('EEE',-.2)]:
        for l in range(1,25):
            changed=d=='AAA' and l>=13
            rows.append(dict(driver=d,lap=l,completed_s=l*90+offset,lap_time_s=90-.04*l+offset-(1.5 if changed else 0),
                compound='MEDIUM',tyre_age=l-12 if changed else l,track_status='1',in_lap=d=='AAA' and l==12,out_lap=d=='AAA' and l==13))
    return dict(round=1,laps=24,laps_data=rows)

class RecoveryTests(unittest.TestCase):
    def test_control_removes_common_fuel_and_recovers_injected_reset(self):
        labels=stop_labels(race()); self.assertEqual(len(labels),1)
        row=labels.iloc[0]
        self.assertAlmostEqual(row.relative_step_s,1.5)
        self.assertAlmostEqual(row.placebo_relative_s,0)
        self.assertAlmostEqual(row.pretrend_corrected_s,1.5)
        self.assertGreater(row.label_s,row.issued_s)
        self.assertTrue(np.isnan(row.pre_traffic))

    def test_neutralised_or_missing_window_abstains(self):
        r=race()
        next(q for q in r['laps_data'] if q['driver']=='AAA' and q['lap']==15)['track_status']='4'
        self.assertTrue(stop_labels(r).empty)
        r=race(); r['laps_data']=[q for q in r['laps_data'] if not(q['driver']=='AAA' and q['lap']==10)]
        self.assertTrue(stop_labels(r).empty)

    def test_insufficient_controls_does_not_fabricate_adjusted_label(self):
        r=race(); r['laps_data']=[q for q in r['laps_data'] if q['driver'] in ('AAA','BBB')]
        row=stop_labels(r).iloc[0]
        self.assertTrue(np.isnan(row.relative_step_s)); self.assertTrue(np.isfinite(row.raw_step_s))

    def test_control_selection_waits_for_all_candidate_sources(self):
        r=race()
        last=next(q for q in r['laps_data'] if q['driver']=='EEE' and q['lap']==16)
        last['completed_s']=9999; last['in_lap']=True
        label=stop_labels(r).iloc[0]
        self.assertEqual(label.label_s,9999)
        self.assertNotIn('EEE',label.controls)

    def test_online_adaptation_cannot_see_unresolved_result(self):
        x=pd.DataFrame(dict(label_s=[50,100,150],y=[1,999,999],pred=[0,0,0]))
        self.assertEqual(adaptation(x,100,'y','pred',5),(1/6,1))
        x.loc[1:,'y']=-999
        self.assertEqual(adaptation(x,100,'y','pred',5),(1/6,1))

    def test_anchor_prefix_invariance(self):
        x,_=clock_features(race()); x=x.loc[x.horizon==1]
        full=add_stint_anchors(x)
        prefix=add_stint_anchors(x.loc[x.issued_s<1000])
        pd.testing.assert_frame_equal(full.loc[full.issued_s<1000].reset_index(drop=True),prefix)

class RecoveryArtifacts(unittest.TestCase):
    def test_browser_recovery_contracts(self):
        subprocess.run(['node','--test','tests/test_recovery_ui.js'],cwd=ROOT,check=True,capture_output=True,text=True)

    def test_same_compound_evidence_recomputes(self):
        evidence=json.loads((ROOT/'artifacts/demo/recovery/evidence.json').read_text())
        data=pd.read_csv(ROOT/'artifacts/recovery_observations_2026.csv')
        same=data.loc[data.pair.str.split('>').str[0]==data.pair.str.split('>').str[1]].dropna(subset=['relative_step_s'])
        self.assertEqual(len(same),evidence['same_compound']['n'])
        self.assertAlmostEqual(same.relative_step_s.mean(),evidence['same_compound']['mean_s'],places=5)
        paired=same.dropna(subset=['placebo_relative_s'])
        self.assertAlmostEqual((paired.relative_step_s-paired.placebo_relative_s).mean(),evidence['paired_same_compound']['difference']['mean_s'],places=5)

    def test_report_recomputes_and_selection_uses_development_only(self):
        report=json.loads((ROOT/'artifacts/demo/recovery/report.json').read_text())
        lock=json.loads((ROOT/'artifacts/demo/recovery/selection.json').read_text())
        x=pd.read_csv(ROOT/'artifacts/recovery_predictions_2026.csv')
        for target,metrics in report['targets'].items():
            data=x.loc[x.target_name==target]; final=data.loc[data['round']>=9]
            self.assertAlmostEqual(np.sqrt(np.mean((final.selected_s-final[target])**2)),metrics['rmse_s'],places=5)
            dev=data.loc[data['round']<9]
            scores={c:float(dev.assign(e=(dev[c]-dev[target])**2).groupby('round').e.mean().mean()) for c in lock[target]['development_event_mse']}
            self.assertEqual(min(scores,key=scores.get),lock[target]['selected'])
        for source in report['source_manifest']:
            self.assertEqual(hashlib.sha256((ROOT/source['path']).read_bytes()).hexdigest(),source['sha256'])
