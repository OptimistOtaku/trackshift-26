"""Event-level data pipeline with an on-disk cache.

Loading position telemetry for one session takes tens of seconds; a season is ~40
sessions. Every model iteration would otherwise pay that cost again, so each event is
reduced once to a cleaned lap table and cached as parquet.

The event is the right unit because the fuel burn rate is a property of the *race*
distance and must be applied to that event's practice sessions - see
`pitwall.data.fuel_burn_rate`. Cleaning a practice session in isolation cannot get this
right, so the pipeline never does.
"""
from __future__ import annotations

import os
import warnings

import fastf1
import numpy as np
import pandas as pd

from .data import (SessionRef, clean_laps, enable_cache, fuel_burn_rate, load_session,
                   race_laps_of)
from .track import build_centreline
from .traffic import attach_traffic, lap_traffic_features

warnings.filterwarnings("ignore")

_HERE = os.path.dirname(os.path.abspath(__file__))
FRAME_DIR = os.path.abspath(os.path.join(_HERE, "..", "..", "data", "frames"))

# Sprint weekends run a single practice session; conventional weekends run three.
PRACTICE_BY_FORMAT = {
    "conventional": ("FP1", "FP2", "FP3"),
    "sprint_qualifying": ("FP1",),
    "sprint_shootout": ("FP1",),
    "sprint": ("FP1", "FP2"),
}


def _slug(s: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in s).strip("_").lower()


def completed_events(year: int, upto: pd.Timestamp | None = None) -> pd.DataFrame:
    """Events whose race has already run."""
    enable_cache()
    sch = fastf1.get_event_schedule(year, include_testing=False)
    cutoff = upto or pd.Timestamp.utcnow().tz_localize(None)
    done = sch.loc[sch["Session5DateUtc"] < cutoff].copy()
    return done[["RoundNumber", "EventName", "EventFormat", "Session5DateUtc"]]


def practice_sessions(event_format: str) -> tuple[str, ...]:
    return PRACTICE_BY_FORMAT.get(event_format, ("FP1", "FP2", "FP3"))


def _prep_session(year: int, gp: str, name: str, burn: float | None):
    s = load_session(SessionRef(year, gp, name), telemetry=True)
    cl = build_centreline(s)
    tf = lap_traffic_features(s, cl)
    laps = attach_traffic(clean_laps(s, burn_kg_per_lap=burn), tf)
    return s, laps, cl


def _add_track_evolution(out: pd.DataFrame) -> pd.DataFrame:
    """Weekend-cumulative rubber, and the regressor built from it.

    Sessions are ordered by their real start time and each lap is credited with every
    lap the field has run at this circuit so far that weekend. Rubber laid on Friday is
    still there on Sunday, so the count has to be cumulative across sessions, not reset
    per session.

    `TrackEvo = log1p(laps)` is the operative regressor, and the log is doing real work.
    Track evolution saturates: the first 200 laps transform a green surface, the next 200
    barely change it. A linear count would advance in step with tyre age inside a run and
    be unidentifiable; a log advances fast early and slowly late, so a run at the start of
    FP1 and a run at the end of FP3 see very different evolution per lap. That difference
    in shape is what separates track evolution from degradation.
    """
    out = out.copy()
    order = (out[["Session", "SessionDate", "SessionTotalLaps"]]
             .drop_duplicates("Session")
             .sort_values("SessionDate"))
    offset, offsets = 0.0, {}
    for _, r in order.iterrows():
        offsets[r["Session"]] = offset
        offset += float(r["SessionTotalLaps"])

    out["WeekendLaps"] = (out["Session"].map(offsets).astype(float)
                          + out["SessionLapsBefore"].astype(float))
    out["TrackEvo"] = np.log1p(out["WeekendLaps"])
    return out


def build_event(year: int, gp: str, event_format: str = "conventional",
                *, force: bool = False) -> pd.DataFrame:
    """Cleaned laps for every session of one event, with traffic attached.

    Cached to parquet. The race is processed first because it fixes the fuel burn rate
    used for that event's practice sessions.
    """
    os.makedirs(FRAME_DIR, exist_ok=True)
    path = os.path.join(FRAME_DIR, f"{year}_{_slug(gp)}.parquet")
    if os.path.exists(path) and not force:
        return pd.read_parquet(path)

    s_race, race, cl = _prep_session(year, gp, "R", None)
    burn = fuel_burn_rate(year, race_laps_of(s_race))

    parts = [race]
    for name in practice_sessions(event_format):
        try:
            parts.append(_prep_session(year, gp, name, burn)[1])
        except Exception as exc:  # a session may be cancelled or have no position data
            print(f"    {gp} {name}: skipped ({type(exc).__name__}: {exc})")

    out = pd.concat([p for p in parts if not p.empty], ignore_index=True)
    out = _add_track_evolution(out)
    out["Round"] = 0  # filled by build_season
    out["TrackLengthM"] = float(cl.length)
    out.to_parquet(path, index=False)
    return out


def build_season(year: int, *, force: bool = False,
                 rounds: list[int] | None = None) -> pd.DataFrame:
    """Build (or load) every completed event of a season."""
    ev = completed_events(year)
    if rounds:
        ev = ev.loc[ev["RoundNumber"].isin(rounds)]

    frames = []
    for _, r in ev.iterrows():
        gp, rnd = r["EventName"], int(r["RoundNumber"])
        print(f"[R{rnd:02d}] {gp}")
        try:
            df = build_event(year, gp, r["EventFormat"], force=force)
        except Exception as exc:
            print(f"    FAILED: {type(exc).__name__}: {exc}")
            continue
        df["Round"] = rnd
        frames.append(df)
        print(f"    {len(df):5d} laps  {df['RunId'].nunique():3d} runs  "
              f"sessions={sorted(df['Session'].unique())}")

    if not frames:
        return pd.DataFrame()
    season = pd.concat(frames, ignore_index=True)
    # RunId is only unique within a session; make it globally unique so that clustering
    # and run dummies do not merge two different cars' stints across events.
    season["RunId"] = (season["Round"].astype(str) + "|"
                       + season["Session"].astype(str) + "|" + season["RunId"])
    return season
