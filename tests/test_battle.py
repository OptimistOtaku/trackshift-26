from pathlib import Path
import copy
import json
import sys
import unittest
import shutil
import subprocess

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"src"))
from pitwall.battle import attack_budget, battle_requests, robust_compound_plan, BATTLE_FEATURES


class BattleTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"), "Node is needed for the browser arithmetic parity check")
    def test_browser_and_python_attack_costs_match(self):
        for h in (3,5):
            step=dict(step_s=1.7,radius_s=.4)
            battle=dict(predicted_loss_s=1.2,radius_s=.8,horizon=h)
            costs=dict(gap=1.5,warmup=.7,service=-.2,traffic=.6,decay=.1)
            script="const {attackBudget}=require('./demo_fallback/battle.js');const x=JSON.parse(process.argv[1]);process.stdout.write(JSON.stringify(attackBudget(...x)));"
            actual=json.loads(subprocess.check_output([shutil.which("node"),"-e",script,
                json.dumps([step,battle,costs])],cwd=ROOT,text=True))
            expected=attack_budget(step_s=1.7,step_radius_s=.4,gap_s=1.5,
                relative_loss_s=1.2,relative_radius_s=.8,horizon=h,
                warmup_s=.7,service_s=-.2,traffic_s=.6,degradation_s=.1)
            for key in ("margin_s","lower_margin_s","upper_margin_s","required_step_s"):
                self.assertAlmostEqual(actual[key],expected[key])

    def test_attack_accounts_for_rival_pace_and_all_costs(self):
        result = attack_budget(step_s=2., step_radius_s=.2, gap_s=1., relative_loss_s=1.5,
            relative_radius_s=.5, horizon=3, warmup_s=.7, service_s=.2, traffic_s=.3, degradation_s=.1)
        self.assertAlmostEqual(result["margin_s"], 2.)
        self.assertAlmostEqual(result["lower_margin_s"], .9)
        self.assertAlmostEqual(result["required_step_s"], 4./3)
        slower = attack_budget(step_s=2., step_radius_s=.2, gap_s=1., relative_loss_s=2.5,
            relative_radius_s=.5, horizon=3, warmup_s=.7, service_s=.2, traffic_s=.3, degradation_s=.1)
        self.assertAlmostEqual(result["margin_s"]-slower["margin_s"], 1.)

    def test_bad_scenario_inputs_fail(self):
        args = dict(step_s=1., step_radius_s=.2, gap_s=1., relative_loss_s=.1,
                    relative_radius_s=.5, horizon=3)
        for field, value in (("gap_s", -1), ("horizon", True), ("horizon", 4),
                             ("step_s", np.nan), ("relative_radius_s", -1)):
            with self.assertRaises(ValueError):
                attack_budget(**dict(args, **{field:value}))

    def test_optimizer_abstains_on_unsupported_or_uncalibrated_cases(self):
        scenario = dict(supported=True, extrapolating=False, radius_s=.3, step_s=2., training_stops=20)
        battle = dict(horizon=3, predicted_loss_s=1., radius_s=.5)
        self.assertEqual(robust_compound_plan({"HARD":dict(scenario, extrapolating=True)},[battle],gap_s=1),[])
        self.assertEqual(robust_compound_plan({"HARD":scenario},[dict(battle,radius_s=None)],gap_s=1),[])
        plan = robust_compound_plan({"HARD":scenario,"SOFT":dict(scenario,step_s=3.)},[battle],gap_s=1)
        self.assertEqual(plan[0]["compound"],"SOFT")
        self.assertGreater(plan[0]["worst_margin_s"],plan[1]["worst_margin_s"])

    def test_future_positions_and_labels_do_not_select_rivals(self):
        races = [dict(round=4,laps_data=[dict(driver=d,lap=l,position=p,lap_time_s=80+p*.1)
                    for l in range(1,10) for d,p in (("AAA",1),("BBB",2),("CCC",3))])]
        values = []
        for d,p in (("AAA",1),("BBB",2),("CCC",3)):
            for h in (1,3,5):
                values.append(dict(round=4,driver=d,lap=4,horizon=h,age=4,kalman_trend=.1,
                    spread=.1,progress=.4,field_relative=p*.1,soft=0,hard=1,current_s=80+p*.1,
                    persistence=80+p*.1,rolling_median=80+p*.1,state_space=80+p*.1,
                    hybrid=80+p*.1,selected_s=80+p*.1,scored=True))
        predictions = pd.DataFrame(values)
        before = battle_requests(predictions,races)
        poisoned = copy.deepcopy(races)
        for r in poisoned[0]["laps_data"]:
            if r["lap"]>4:
                r["position"] = 4-r["position"]
                r["lap_time_s"] += 50*r["position"]
        after = battle_requests(predictions,poisoned)
        pd.testing.assert_frame_equal(before[BATTLE_FEATURES+["driver","rival"]],
                                      after[BATTLE_FEATURES+["driver","rival"]])
        self.assertFalse(np.allclose(before.actual_loss_s,after.actual_loss_s))
        self.assertAlmostEqual(before.iloc[0].actual_loss_s, .3)


class BattleArtifactTests(unittest.TestCase):
    def test_exported_battles_have_no_future_outcomes(self):
        for path in (ROOT/"artifacts/demo/intelligence").glob("R[0-9][0-9].json"):
            data=json.loads(path.read_text())
            if data["status"]!="ready":
                continue
            self.assertLess(data["battle_model"]["training_through_round"],data["round"])
            for snapshot in data["snapshots"]:
                for battle in snapshot.get("battles",[]):
                    self.assertEqual(battle["target_lap"],snapshot["lap"]+battle["horizon"])
                    self.assertNotIn("actual_s",battle)
                    self.assertNotIn("actual_loss_s",battle)

    def test_report_recomputes_from_predictions(self):
        path = ROOT/"artifacts/demo/intelligence/battle_report.json"
        self.assertTrue(path.exists(),"Run benchmark_battle.py first")
        report = json.loads(path.read_text())
        data = pd.read_csv(ROOT/"artifacts/battle_predictions_2026.csv")
        final = data.loc[(data["round"]>=9)&data.scored]
        self.assertEqual(len(final),report["n"])
        self.assertAlmostEqual(np.sqrt(np.mean((final.selected_s-final.actual_loss_s)**2)), report["rmse_s"],places=6)
        self.assertEqual(final.model.unique().tolist(),[report["selected_model"]])


if __name__ == "__main__":
    unittest.main()
