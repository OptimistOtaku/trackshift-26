"""Timestamp-causal lap features: emit when the individual driver's lap arrives."""
from __future__ import annotations

from itertools import groupby
import numpy as np
import pandas as pd
from pitwall.intelligence import PaceState, HORIZONS, usable, finite
from pitwall.conditions import condition_features


def clock_features(race: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows = [r for r in race['laps_data'] if finite(r.get('completed_s'))]
    seen = set()
    for row in rows:
        key = (row['driver'], row['lap'])
        if key in seen:
            raise ValueError(f'Duplicate observation {key}')
        seen.add(key)
    rows.sort(key=lambda r: (r['completed_s'], r['driver']))
    states, deltas, features, observations = {}, {}, [], []
    count = 0
    for timestamp, simultaneous in groupby(rows, key=lambda r: r['completed_s']):
        batch = list(simultaneous)
        current = []
        for row in batch:
            state = states.setdefault(row['driver'], PaceState())
            old = state.last_row
            if old and row['lap'] <= old['lap']:
                raise ValueError('Lap number regresses in timestamp order')
            delta = None
            if (old and usable(old) and usable(row) and row['lap'] == old['lap']+1
                    and row['compound'] == old['compound'] and row['tyre_age'] == old['tyre_age']+1):
                delta = row['lap_time_s']-old['lap_time_s']
            deltas[row['driver']] = delta
            ok = state.observe(row)
            count += 1
            observations.append(dict(round=int(race['round']), driver=row['driver'],
                lap=int(row['lap']), completed_s=timestamp, segment=state.segment,
                usable=ok, compound=row.get('compound'), age=row.get('tyre_age'),
                actual_s=row.get('lap_time_s')))
            if ok and len(state.history)>=3:
                current.append((row,state))
        active = {driver:s for driver,s in states.items() if usable(s.last_row)
                  and timestamp-s.last_row['completed_s']<=180}
        pace = np.array([s.last_row['lap_time_s'] for s in active.values()])
        changes = [deltas[d] for d in active if deltas[d] is not None]
        level = float(np.median(pace)) if len(pace) else 0.
        spread = float(np.median(abs(pace-level))) if len(pace) else 0.
        change = float(np.median(changes)) if changes else 0.
        for row,state in current:
            for h in HORIZONS:
                if row['lap']+h>race['laps']:
                    continue
                f = state.features(h, race['laps'], change, level, spread)
                f.update(condition_features(row,state.previous_conditions,count))
                features.append(dict(f,round=int(race['round']),driver=row['driver'],
                    lap=int(row['lap']),target_lap=int(row['lap'])+h,issued_s=timestamp,
                    segment=state.segment,compound=row['compound'],current_s=row['lap_time_s']))
    return pd.DataFrame(features),pd.DataFrame(observations)
