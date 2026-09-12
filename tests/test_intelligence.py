from pathlib import Path
import json
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from pitwall.intelligence import (PaceState, replay_features, attach_targets,
    interval_radius, fit_candidates, predict_candidates)
from pitwall.decision import fit_decision, undercut_scenario
from pitwall.engineer import build_facts, commentary, validate_selection


def sample_race():
    return dict(round=1, laps=30, laps_data=[dict(lap=lap, driver=driver,
        lap_time_s=80+lap*.04+(driver=="BBB")*.5, compound="MEDIUM", tyre_age=lap,
        track_status="1", in_lap=False, out_lap=False, clean=True, deleted=False)
        for lap in range(1,31) for driver in ("AAA","BBB")])


class CausalityTests(unittest.TestCase):
    def test_future_suffix_and_retrospective_cleaning_do_not_change_features(self):
        full = sample_race()
        before, _ = replay_features(full)
        poisoned = json.loads(json.dumps(full))
        for row in poisoned["laps_data"]:
            row["clean"] = False
            row["deleted"] = True
            if row["lap"] > 15:
                row.update(lap_time_s=500., compound="SOFT", tyre_age=1, track_status="4")
        after, _ = replay_features(poisoned)
        pd.testing.assert_frame_equal(before.loc[before.lap<=15].reset_index(drop=True),
                                      after.loc[after.lap<=15].reset_index(drop=True))
        prefix = dict(full, laps_data=[r for r in full["laps_data"] if r["lap"]<=15])
        truncated, _ = replay_features(prefix)
        pd.testing.assert_frame_equal(before.loc[before.lap<=15].reset_index(drop=True), truncated)

    def test_neutralisation_and_pit_reset_remove_stale_trend(self):
        race = sample_race()
        for row in race["laps_data"]:
            if row["lap"] == 10:
                row["track_status"] = "4"
            if row["lap"] == 20:
                row["out_lap"] = True
            if row["lap"] >= 20:
                row["tyre_age"] = row["lap"]-19
        x, observations = replay_features(race)
        targets = attach_targets(x, observations)
        self.assertFalse(x.lap.isin([10,11,12,20,21,22]).any())
        cross = targets.loc[(targets.lap==9) & (targets.horizon==3)]
        self.assertFalse(cross.scored.any())
        self.assertTrue(targets.loc[(targets.lap==13)&(targets.horizon==1)].scored.all())

    def test_out_of_order_and_duplicate_observations_fail(self):
        state = PaceState()
        row = sample_race()["laps_data"][4]
        state.observe(row)
        with self.assertRaises(ValueError):
            state.observe(row)
        race = sample_race()
        race["laps_data"].append(race["laps_data"][0])
        with self.assertRaises(ValueError):
            replay_features(race)

    def test_model_ignores_target_columns_at_prediction_time(self):
        tables = []
        for rnd in range(1,4):
            race = sample_race()
            race["round"] = rnd
            x, obs = replay_features(race)
            tables.append(attach_targets(x,obs))
        data = pd.concat(tables,ignore_index=True)
        models = fit_candidates(data)
        expected = predict_candidates(models,data)
        poisoned = data.assign(actual_s=1e6,target_delta=-1e6,scored=False)
        actual = predict_candidates(models,poisoned)
        for name in expected:
            np.testing.assert_array_equal(expected[name],actual[name])

    def test_intervals_use_finite_sample_quantile_and_require_calibration(self):
        self.assertIsNone(interval_radius([.2]*10))
        self.assertEqual(interval_radius(np.arange(1,101)),91.)


class StrategyTests(unittest.TestCase):
    def test_cost_conservation_and_shared_uncertainty(self):
        rows = undercut_scenario(step_s=1.5,step_radius_s=.5,gap_s=1.,response_laps=3,
            pace_advantage_s=.2,warmup_loss_s=.7,traffic_loss_s=.3,service_delta_s=.2)
        final = rows[-1]
        self.assertAlmostEqual(final["time_gained_s"],3*1.7-.7-.3-.2)
        self.assertAlmostEqual(final["margin_s"]-final["lower_margin_s"],1.5)
        self.assertEqual(final["tyre_age_deficit_laps"],3)

    def test_invalid_horizons_and_nonfinite_inputs_are_rejected(self):
        for h in (0,6,1.5,True):
            with self.assertRaises(ValueError):
                undercut_scenario(step_s=1,step_radius_s=.5,gap_s=1,response_laps=h)
        with self.assertRaises(ValueError):
            undercut_scenario(step_s=np.nan,step_radius_s=.5,gap_s=1)

    def test_unseen_compound_is_not_treated_as_reference_pair(self):
        train = pd.DataFrame(dict(round=[1,1,2,2,3,3],pair=["MEDIUM>HARD"]*6,
            age=[10,20]*3,step_obs=[1.,2.]*3))
        model = fit_decision(train,"pair")
        self.assertTrue(np.isnan(model.predict(train.assign(pair="SOFT>SOFT"))).all())


class EngineerTests(unittest.TestCase):
    def test_fail_closed_and_no_arbitrary_llm_language(self):
        facts = [dict(id="forecast",text="Forecast: 81.23 seconds.")]
        for bad in ({"fact_ids":["pit_now"]},{"fact_ids":["forecast"],"text":"Box now"},
                    {"fact_ids":["forecast","forecast"]}):
            with self.assertRaises(ValueError):
                validate_selection(bad,facts)
        with patch.dict("os.environ",{"PITWALL_OLLAMA_MODEL":"test"}), patch(
                "pitwall.engineer.urlopen",side_effect=OSError("offline")):
            result = commentary(facts)
        self.assertEqual(result["source"],"template")
        self.assertEqual(result["text"],facts[0]["text"])

    def test_future_outcomes_never_enter_commentary(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for folder in ("replay","intelligence"):
                (root / "artifacts/demo" / folder).mkdir(parents=True)
            (root/"artifacts/demo/replay/R01.json").write_text(json.dumps(sample_race()))
            state = dict(lap=10,driver="AAA",compound="MEDIUM",tyre_age=10,
                pace_trend_s_per_lap=.03, forecasts=[dict(horizon=3,target_lap=13,
                pace_s=81.,lower_s=80.,upper_s=82.)])
            payload = dict(snapshots=[state],training_through_round=0,evaluation=[dict(
                driver="AAA",target_lap=11,predicted_s=999.,actual_s=-999.)])
            path = root/"artifacts/demo/intelligence/R01.json"
            path.write_text(json.dumps(payload))
            facts = build_facts(root,1,10,"AAA")
            self.assertNotIn("evidence",[f["id"] for f in facts])
            self.assertNotIn("999",json.dumps(facts))


class ArtifactTests(unittest.TestCase):
    def test_exported_models_train_before_the_replayed_race(self):
        for path in (ROOT/"artifacts/demo/intelligence").glob("R[0-9][0-9].json"):
            data = json.loads(path.read_text())
            if data["status"] != "ready":
                self.assertEqual(data["snapshots"],[])
                continue
            self.assertLess(data["training_through_round"],data["round"])
            self.assertLess(data["decision_model"]["training_through_round"],data["round"])
            for snapshot in data["snapshots"]:
                for forecast in snapshot["forecasts"]:
                    self.assertEqual(forecast["target_lap"],snapshot["lap"]+forecast["horizon"])
                    self.assertNotIn("actual_s",forecast)

    def test_scoreboard_matches_saved_predictions(self):
        report=json.loads((ROOT/"artifacts/demo/intelligence/report.json").read_text())
        data=pd.read_csv(ROOT/"artifacts/intelligence_predictions_2026.csv")
        test=data.loc[(data["round"]>=9)&data.scored]
        rmse=np.sqrt(np.mean((test.actual_s-test.selected_s)**2))
        self.assertEqual(len(test),report["n"])
        self.assertAlmostEqual(rmse,report["rmse_s"],places=6)
        self.assertEqual(test.model.unique().tolist(),[report["selected_model"]])


if __name__ == "__main__":
    unittest.main()
