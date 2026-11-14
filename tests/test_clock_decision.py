import json, subprocess, unittest
from pathlib import Path
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]

class ClockDecisionTests(unittest.TestCase):
    def test_saved_report_recomputes(self):
        data=pd.read_csv(ROOT/'artifacts/clock_decision_predictions_2026.csv')
        report=json.loads((ROOT/'artifacts/demo/decision-clock/report.json').read_text())
        final=data.loc[data['round']>=9].dropna(subset=['selected_s'])
        self.assertEqual(len(final),report['n'])
        self.assertAlmostEqual(((final.selected_s-final.step_obs)**2).mean()**.5,report['rmse_s'],places=5)
        for path in (ROOT/'artifacts/demo/decision-clock').glob('R[0-9][0-9].json'):
            payload=json.loads(path.read_text())
            if payload['snapshots']:self.assertLess(payload['training_through_round'],payload['round'])

    def test_live_browser_contracts(self):
        subprocess.run(['node','--test','tests/test_live_console.js'],cwd=ROOT,check=True)
