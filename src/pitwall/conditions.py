"""Point-in-time environmental inputs. Missing telemetry is never clean air."""
from __future__ import annotations

import numpy as np
import pandas as pd

CONDITION_FEATURES = ["track_temp_c", "air_temp_c", "track_temp_change_c",
    "weather_missing", "rainfall", "humidity_pct", "wind_speed_ms",
    "traffic_close", "traffic_near", "traffic_gap_s", "traffic_missing",
    "traffic_change", "thermal_age", "traffic_age", "field_laps_log"]


def weather_at(weather: pd.DataFrame, completed_s: float, max_age_s: float = 180.) -> dict:
    """Last sensor sample at/before completion, with a staleness limit."""
    empty = dict(track_temp_c=None, air_temp_c=None, humidity_pct=None,
                 wind_speed_ms=None, rainfall=None, weather_age_s=None)
    if weather.empty or not np.isfinite(completed_s):
        return empty
    times = weather.Time.dt.total_seconds().to_numpy()
    valid = np.flatnonzero(np.isfinite(times) & (times <= completed_s))
    if not len(valid):
        return empty
    idx = valid[np.argmax(times[valid])]
    age = float(completed_s-times[idx])
    if age > max_age_s:
        return empty
    row = weather.iloc[idx]
    result = dict(empty, weather_age_s=age)
    for target, source in (("track_temp_c", "TrackTemp"), ("air_temp_c", "AirTemp"),
                           ("humidity_pct", "Humidity"), ("wind_speed_ms", "WindSpeed")):
        value = row.get(source)
        result[target] = float(value) if pd.notna(value) and np.isfinite(value) else None
    result["rainfall"] = bool(row.Rainfall) if pd.notna(row.get("Rainfall")) else None
    return result


def condition_features(row: dict, previous: dict | None, field_laps: int) -> dict:
    def valid(v):
        return isinstance(v, (float, int, np.number)) and np.isfinite(v)

    def value(key, fallback=0.):
        v = row.get(key)
        return float(v) if valid(v) else fallback
    previous = previous or {}
    temperature = value("track_temp_c", 35.)
    traffic = bool(row.get("traffic_observed")) and valid(row.get("frac_close"))
    close = value("frac_close") if traffic else 0.
    old_temp = previous.get("track_temp_c")
    old_close = previous.get("frac_close")
    age = value("tyre_age")
    return dict(track_temp_c=temperature, air_temp_c=value("air_temp_c", 25.),
        track_temp_change_c=temperature-old_temp if valid(old_temp) and valid(row.get("track_temp_c")) else 0.,
        weather_missing=int(not valid(row.get("track_temp_c"))), rainfall=int(row.get("rainfall") is True),
        humidity_pct=value("humidity_pct", 50.), wind_speed_ms=value("wind_speed_ms"),
        traffic_close=close, traffic_near=value("frac_near") if traffic else 0.,
        traffic_gap_s=min(value("gap_med_s", 20.), 20.) if traffic else 20.,
        traffic_missing=int(not traffic),
        traffic_change=close-old_close if traffic and previous.get("traffic_observed") and valid(old_close) else 0.,
        thermal_age=(temperature-35.)*age/25., traffic_age=close*age/25.,
        field_laps_log=float(np.log1p(field_laps)))
