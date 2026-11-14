"""Environmental causality, source units and missing-sensor regression tests."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import copy
import hashlib
import json
import sys
import unittest

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from pitwall.conditions import condition_features, weather_at
from pitwall.intelligence import replay_features
from pitwall.track import Centreline
from pitwall.traffic import lap_traffic_features
from test_intelligence import sample_race


class ConditionsTests(unittest.TestCase):
    def test_report_source_hashes_match_the_sensor_rebuild(self):
        report = json.loads((ROOT / 'artifacts/demo/intelligence/report.json').read_text())
        for source in report['source_manifest']:
            self.assertEqual(hashlib.sha256((ROOT / source['path']).read_bytes()).hexdigest(),
                             source['sha256'])
        forecasts = pd.read_csv(ROOT / 'artifacts/intelligence_predictions_2026.csv')
        # Report covers all feature requests, including R01-R03 training races;
        # exported predictions cover R04 onward, so verify sensor flags themselves.
        self.assertTrue(forecasts.traffic_missing.isin([0, 1]).all())
        self.assertTrue(forecasts.weather_missing.isin([0, 1]).all())

    def test_weather_is_backward_only_and_stale_samples_are_missing(self):
        weather = pd.DataFrame(dict(Time=pd.to_timedelta([120, 60, 240], unit='s'),
            TrackTemp=[40., 35., 99.], AirTemp=[25., 24., 80.], Rainfall=[False, False, True]))
        self.assertEqual(weather_at(weather, 150)['track_temp_c'], 40.)
        self.assertEqual(weather_at(weather, 150)['weather_age_s'], 30.)
        self.assertIsNone(weather_at(weather, 30)['track_temp_c'])
        self.assertIsNone(weather_at(weather, 421)['track_temp_c'])
        self.assertIsNone(weather_at(weather, np.nan)['track_temp_c'])
        weather.loc[0, 'TrackTemp'] = np.inf
        self.assertIsNone(weather_at(weather, 150)['track_temp_c'])

    def test_missing_traffic_cannot_become_a_clean_air_observation(self):
        missing = condition_features(dict(traffic_observed=False, frac_close=.9), None, 25)
        clean = condition_features(dict(traffic_observed=True, frac_close=0.), None, 25)
        self.assertEqual(missing['traffic_missing'], 1)
        self.assertEqual(clean['traffic_missing'], 0)
        bad = condition_features(dict(track_temp_c=np.nan, frac_close=np.inf,
            traffic_observed=True), dict(track_temp_c=np.inf, frac_close=np.nan), 30)
        self.assertTrue(all(np.isfinite(v) for v in bad.values()))
        self.assertEqual(bad['weather_missing'], 1)
        self.assertEqual(bad['traffic_missing'], 1)

    def test_future_environment_does_not_change_earlier_forecasts(self):
        race = sample_race()
        for row in race['laps_data']:
            row.update(track_temp_c=40., air_temp_c=25., rainfall=False,
                traffic_observed=True, frac_close=.2, frac_near=.6, gap_med_s=2.)
        before, _ = replay_features(race)
        altered = copy.deepcopy(race)
        for row in altered['laps_data']:
            if row['lap'] > 15:
                row.update(track_temp_c=90., air_temp_c=80., rainfall=True,
                    traffic_observed=False, frac_close=.99)
        after, _ = replay_features(altered)
        pd.testing.assert_frame_equal(before[before.lap <= 15], after[after.lap <= 15])

    def test_source_decimetres_are_converted_for_metric_offline_gate(self):
        xy = np.array([[0., 0.], [100., 0.], [200., 0.]])
        cl = Centreline(xy, np.array([0., 10., 20.]), 30., cKDTree(xy))
        distance, off = cl.arc_length(np.array([100., 200.]), np.array([150., 250.]))
        np.testing.assert_allclose(distance, [10., 20.])
        np.testing.assert_allclose(off, [15., 25.])

    def test_sparse_position_samples_do_not_represent_a_whole_lap(self):
        grid = pd.DataFrame([dict(t=t, car=car, s=s) for t in np.arange(0, 5, .5)
                             for car, s in [('1', 10.), ('2', 20.)]])
        session = SimpleNamespace(pos_data={}, results=pd.DataFrame(dict(
            DriverNumber=['1', '2'], Abbreviation=['AAA', 'BBB'])),
            laps=pd.DataFrame([dict(Driver='AAA', DriverNumber='1', LapNumber=2.,
                LapStartTime=pd.Timedelta(0), Time=pd.Timedelta(seconds=90),
                LapTime=pd.Timedelta(seconds=90))]))
        with patch('pitwall.traffic._resample_positions', return_value=grid):
            traffic = lap_traffic_features(session, SimpleNamespace(length=1000.), causal=True)
        self.assertTrue(traffic.empty)


if __name__ == '__main__':
    unittest.main()
