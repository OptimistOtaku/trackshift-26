"""Export timestamped cached race positions and car channels, without model labels.

One sample per second, selected backwards from the original feed. Frontend
interpolation is delayed by one second so neither endpoint comes from its future.
"""
from pathlib import Path
import argparse
import json
import sys
import numpy as np
import pandas as pd
import fastf1
from scipy.spatial import cKDTree

ROOT = Path(__file__).resolve().parents[1]


def export(replay):
    session = fastf1.get_session(2026, replay['event'], 'R')
    session.load(laps=True, telemetry=True, weather=False, messages=False)
    laps = session.laps
    start = float(laps.LapStartTime.dropna().dt.total_seconds().min())
    end = float(laps.Time.dropna().dt.total_seconds().max())
    grid = np.arange(np.ceil(start), np.floor(end) + 1)
    circuit = replay.get('circuit')
    xy = np.asarray(circuit['xy'], float) if circuit else None
    tree = cKDTree(xy) if circuit else None
    # Use the geometry's own arc length rather than rank or timing-table offsets.
    segments = np.linalg.norm(np.diff(np.vstack([xy, xy[0]]), axis=0), axis=1) if circuit else None
    arcs = np.r_[0., np.cumsum(segments)[:-1]] / segments.sum() if circuit else None
    drivers = {}
    for number, d in laps.groupby('DriverNumber'):
        name = str(d.Driver.iloc[0])
        pos = session.pos_data.get(str(number))
        car = session.car_data.get(str(number))
        if pos is None or pos.empty:
            continue
        pos = pos.sort_values('SessionTime').drop_duplicates('SessionTime', keep='last')
        times = pos.SessionTime.dt.total_seconds().to_numpy()
        indices = np.searchsorted(times, grid, side='right') - 1
        keep = (indices >= 0) & (grid - times[np.maximum(indices, 0)] <= 1.5)
        ts, ix = grid[keep], indices[keep]
        samples = pos.iloc[ix]
        coords = samples[['X', 'Y']].to_numpy(float)
        valid = np.isfinite(coords).all(axis=1)
        if tree:
            distances, nearest = tree.query(np.where(np.isfinite(coords), coords, 0))
            arc = arcs[nearest]
            ontrack = valid & (distances / 10 <= 35) & samples.Status.eq('OnTrack').to_numpy()
        else:
            arc = np.full(len(ts), np.nan)
            ontrack = np.zeros(len(ts), dtype=bool)
        channels = np.full((len(ts), 4), np.nan)
        if car is not None and not car.empty:
            car = car.sort_values('SessionTime').drop_duplicates('SessionTime', keep='last')
            ct = car.SessionTime.dt.total_seconds().to_numpy()
            ci = np.searchsorted(ct, ts, side='right') - 1
            ok = (ci >= 0) & (ts - ct[np.maximum(ci, 0)] <= 1.5)
            channels[ok] = car.iloc[ci[ok]][['Speed','nGear','Throttle','Brake']].to_numpy(float)
        # Pit status is known after entry, until the observed exit. No future pace.
        inpit = np.zeros(len(ts), dtype=bool)
        events = [(v.total_seconds(), 1) for v in d.PitInTime.dropna()]
        events += [(v.total_seconds(), 0) for v in d.PitOutTime.dropna()]
        events.sort()
        if events:
            et, ev = np.array(events).T
            ei = np.searchsorted(et, ts, side='right') - 1
            inpit = (ei >= 0) & (ev[np.maximum(0, ei)] == 1)
        ontrack &= ~inpit
        rows = []
        for k in range(len(ts)):
            if not valid[k]:
                continue
            ch = [int(v) if np.isfinite(v) else None for v in channels[k]]
            rows.append([int(ts[k]), int(coords[k,0]), int(coords[k,1]),
                         round(float(arc[k]),5) if np.isfinite(arc[k]) else None,
                         *ch, int(ontrack[k]), round(float(ts[k]-times[ix[k]]),3)])
        drivers[name] = rows
    return dict(version=1, round=replay['round'], start_s=start, end_s=end,
                sample_period_s=1, columns=['t','x','y','arc','speed_kph','gear','throttle_pct','brake','on_track','source_age_s'],
                source='Cached FastF1 race position and car telemetry; latest source sample at or before each timestamp',
                xy_unit='decimetres', drivers=drivers)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--rounds', nargs='*', type=int)
    args = parser.parse_args()
    fastf1.set_log_level('ERROR')
    fastf1.Cache.enable_cache(str(ROOT/'data/cache'))
    fastf1.Cache.offline_mode(True)
    dest = ROOT/'artifacts/demo/motion'
    dest.mkdir(exist_ok=True)
    paths = sorted((ROOT/'artifacts/demo/replay').glob('R*.json'))
    for path in paths:
        replay = json.loads(path.read_text())
        if args.rounds and replay['round'] not in args.rounds:
            continue
        payload = export(replay)
        out = dest/path.name
        out.write_text(json.dumps(payload, separators=(',', ':'), allow_nan=False), encoding='utf-8')
        print(f"R{replay['round']:02d}: {len(payload['drivers'])} drivers, {out.stat().st_size/1e6:.1f} MB", flush=True)


if __name__ == '__main__':
    main()
