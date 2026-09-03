"""Session loading and lap cleaning for PITWALL.

The job of this module is to turn raw FastF1 timing into a table of *representative*
laps with the bookkeeping the degradation model needs: run index, tyre age, fuel
mass, session progress and track temperature.

Practice sessions are messy in a specific way: a single FastF1 "stint" contains push
laps, cool-down laps and aborted laps interleaved. Treating a stint as a run would
put 129s cool-down laps next to 83s push laps and destroy the degradation slope, so
we segment stints into runs and apply a within-run relative pace filter.
"""
from __future__ import annotations

import os
import warnings
from dataclasses import dataclass

import fastf1
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", category=FutureWarning)

_HERE = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.abspath(os.path.join(_HERE, "..", "..", "data", "cache"))

# 2026 power-unit regs run a ~50/50 ICE/electric split, so race fuel is far below the
# 100kg of the previous generation. This is a modelling prior, not a measurement, and
# the run-level intercept absorbs the level error - only the per-lap *burn rate*
# matters for the slope, and that scales out of the fuel coefficient.
RACE_FUEL_KG_2026 = 70.0
RACE_FUEL_KG_LEGACY = 100.0

# Practice runs carry an unknown fuel load. We only need a *relative* scale here; the
# run intercept absorbs the absolute level.
PRACTICE_NOMINAL_FUEL_KG = 50.0

# Fallback race distance, used only when a caller cleans a practice session without
# telling us the real race lap count. F1 race distances run 44-78 laps. The pipeline
# always passes the true value; this exists so single-session spikes still run.
NOMINAL_RACE_LAPS = 60.0

COMPOUNDS = ("SOFT", "MEDIUM", "HARD", "INTERMEDIATE", "WET")
SLICKS = ("SOFT", "MEDIUM", "HARD")


def enable_cache(path: str | None = None) -> str:
    path = path or CACHE_DIR
    os.makedirs(path, exist_ok=True)
    fastf1.Cache.enable_cache(path)
    return path


@dataclass
class SessionRef:
    year: int
    gp: str
    session: str  # 'FP1' | 'FP2' | 'FP3' | 'Q' | 'R' | 'S'

    def __str__(self) -> str:
        return f"{self.year} {self.gp} {self.session}"


def race_fuel_kg(year: int) -> float:
    return RACE_FUEL_KG_2026 if year >= 2026 else RACE_FUEL_KG_LEGACY


def fuel_burn_rate(year: int, race_laps: float) -> float:
    """Fuel burnt per lap, in kg, over a race distance.

    `race_laps` must be the *race* lap count. Deriving it from a practice session's own
    lap count is wrong and not harmlessly so: a 33-lap FP2 implies 2.1 kg/lap instead of
    1.0, which inflates the entire practice fuel correction by the same factor.

    Note the invariance that makes this robust. The assumed regulation load `f0` cancels
    out of the quantity that actually matters: double `f0` and `FuelKg` doubles, so the
    fitted `lambda` halves, while `burn` doubles - leaving the per-lap fuel effect
    `lambda * burn` unchanged. The correction therefore does not depend on knowing the
    true 2026 fuel allowance, only on the fact that the load declines linearly.
    """
    return race_fuel_kg(year) / max(float(race_laps), 1.0)


def race_laps_of(session) -> float:
    """Scheduled race distance in laps, read off a race session."""
    n = getattr(session, "total_laps", None)
    if n:
        return float(n)
    return max(float(session.laps["LapNumber"].max()), 1.0)


def load_session(ref: SessionRef, telemetry: bool = False):
    """Load one session. `telemetry=True` also pulls position data (needed for traffic)."""
    enable_cache()
    s = fastf1.get_session(ref.year, ref.gp, ref.session)
    s.load(laps=True, telemetry=telemetry, weather=True, messages=False)
    return s


# --------------------------------------------------------------------------- #
# lap cleaning
# --------------------------------------------------------------------------- #

def _green_flag(track_status: object) -> bool:
    """TrackStatus is a concatenation of status codes seen during the lap.

    '1' is green. Anything else (2=yellow, 4=SC, 5=red, 6/7=VSC) invalidates the lap
    for pace analysis.
    """
    if track_status is None or (isinstance(track_status, float) and np.isnan(track_status)):
        return False
    return set(str(track_status)) == {"1"}


def _segment_runs(laps_all: pd.DataFrame) -> pd.DataFrame:
    """Assign a run index to every lap, on the *unfiltered* lap list.

    A run begins whenever the car leaves the pit lane. That is the physically correct
    boundary: each time a car goes out it carries a fresh, unknown fuel load, so each
    run needs its own intercept.

    This must run before any lap filtering. If we segmented on gaps in LapNumber after
    dropping yellow-flag laps, a single race stint would shatter into fragments and
    each fragment would get its own intercept - which would silently absorb the
    degradation we are trying to measure.
    """
    laps_all = laps_all.sort_values(["Driver", "LapNumber"]).copy()
    laps_all["RunIdx"] = (
        laps_all.groupby(["Driver", "Stint"], sort=False)["IsOutLap"]
        .cumsum()
        .astype(int)
    )
    laps_all["RunStartLap"] = (
        laps_all.groupby(["Driver", "Stint", "RunIdx"], sort=False)["LapNumber"]
        .transform("min")
    )
    return laps_all


def clean_laps(
    session,
    *,
    relative_pace_cutoff: float = 1.07,
    min_run_laps: int = 4,
    slicks_only: bool = True,
    burn_kg_per_lap: float | None = None,
) -> pd.DataFrame:
    """Return representative green-flag laps with model bookkeeping attached.

    `relative_pace_cutoff` is applied *within a run*, against that run's 20th-percentile
    lap time, which is robust to a run that is entirely on high fuel.

    `burn_kg_per_lap` sets the practice fuel-burn rate and should be derived from the
    race distance - see `fuel_burn_rate`. It is ignored for race sessions, where the
    burn rate follows from the race's own lap count.
    """
    laps = session.laps.copy()
    if laps.empty:
        return pd.DataFrame()

    is_race = session.name in ("Race", "Sprint")

    laps["LapTimeS"] = laps["LapTime"].dt.total_seconds()
    laps["Green"] = laps["TrackStatus"].apply(_green_flag)
    laps["IsInLap"] = laps["PitInTime"].notna()
    laps["IsOutLap"] = laps["PitOutTime"].notna()

    # Segment runs on the FULL lap list, before any filtering (see _segment_runs).
    laps = _segment_runs(laps)

    keep = (
        laps["LapTimeS"].notna()
        & laps["Green"]
        & ~laps["IsInLap"]
        & ~laps["IsOutLap"]
        & laps["Compound"].notna()
        & laps["TyreLife"].notna()
        & laps["Stint"].notna()
    )
    if "Deleted" in laps.columns:
        keep &= laps["Deleted"].fillna(False).eq(False)
    if slicks_only:
        keep &= laps["Compound"].isin(SLICKS)

    laps = laps.loc[keep].copy()
    if laps.empty:
        return pd.DataFrame()

    laps["RunId"] = (
        laps["Driver"].astype(str)
        + "|S" + laps["Stint"].astype(int).astype(str)
        + "|R" + laps["RunIdx"].astype(str)
    )

    # Laps actually completed since leaving the pits. Uses original lap numbers so
    # that dropped laps still count towards fuel burnt.
    laps["LapsIntoRun"] = (laps["LapNumber"] - laps["RunStartLap"]).astype(float)

    # --- within-run relative pace filter ----------------------------------- #
    # Removes cool-down and aborted laps. The 20th percentile is the reference rather
    # than the minimum so that a run entirely on high fuel is not penalised. The band
    # is deliberately wide (7%): real degradation is ~1-2s on an ~85s lap, so this
    # catches mistakes and heavy traffic without truncating the slow end of a stint,
    # which would bias the degradation slope downwards.
    ref = laps.groupby("RunId")["LapTimeS"].transform(lambda x: np.percentile(x, 20))
    laps["RunPaceRef"] = ref
    laps = laps.loc[laps["LapTimeS"] <= ref * relative_pace_cutoff].copy()

    # --- run-relative bookkeeping ------------------------------------------ #
    laps = laps.sort_values(["RunId", "LapNumber"])
    laps["LapInRun"] = laps.groupby("RunId").cumcount()
    run_len = laps.groupby("RunId")["LapInRun"].transform("size")
    laps = laps.loc[run_len >= min_run_laps].copy()
    if laps.empty:
        return pd.DataFrame()

    laps["TyreAge"] = laps["TyreLife"].astype(float)
    laps["FreshTyre"] = laps["FreshTyre"].astype(bool)

    # --- fuel mass --------------------------------------------------------- #
    year = int(session.event["EventDate"].year)
    if is_race:
        race_laps = race_laps_of(session)
        f0 = race_fuel_kg(year)
        burn = fuel_burn_rate(year, race_laps)
        # Fuel on board at the start of each lap, declining linearly to ~0 at the flag.
        # Across a whole race this is monotone while tyre age saw-tooths at every pit
        # stop, which is exactly why the fuel coefficient is identified here.
        laps["FuelKg"] = f0 - burn * (laps["LapNumber"] - 1.0)
    else:
        # Practice loads are unknown. Only the within-run burn slope is identified; the
        # run intercept absorbs the absolute level. The burn rate must come from the
        # race distance - a practice session's own lap count is not the race distance
        # and using it would scale the whole fuel correction by the wrong factor.
        burn = burn_kg_per_lap
        if burn is None:
            burn = fuel_burn_rate(year, NOMINAL_RACE_LAPS)
        laps["FuelKg"] = PRACTICE_NOMINAL_FUEL_KG - float(burn) * laps["LapsIntoRun"]
    laps["FuelBurnKgPerLap"] = float(burn)

    # --- session progress + weather ---------------------------------------- #
    t = laps["LapStartTime"].dt.total_seconds()
    laps["SessionProgress"] = (t - t.min()) / max(t.max() - t.min(), 1.0)

    # --- rubber laid down -------------------------------------------------- #
    # Track evolution is not a mystery force: it is rubber on the asphalt, and the
    # amount of rubber is the number of laps the field has run. Counted on the
    # UNFILTERED lap list, because a cool-down lap we discard for pace still lays
    # rubber. The pipeline turns this into a weekend-cumulative count.
    all_t = (session.laps["LapStartTime"].dt.total_seconds()
             .dropna().sort_values().to_numpy())
    laps["SessionLapsBefore"] = np.searchsorted(all_t, t.to_numpy(), side="left").astype(float)
    laps["SessionTotalLaps"] = float(len(all_t))
    laps["SessionDate"] = pd.Timestamp(session.date)
    laps["LapStartS"] = t.astype(float)

    laps["TrackTemp"] = np.nan
    laps["AirTemp"] = np.nan
    try:
        w = session.weather_data.copy()
        if not w.empty:
            w["ts"] = w["Time"].dt.total_seconds()
            for col in ("TrackTemp", "AirTemp"):
                laps[col] = np.interp(t, w["ts"], w[col].astype(float))
    except Exception:
        pass

    laps["Session"] = session.name
    laps["Event"] = session.event["EventName"]
    laps["Year"] = year
    laps["IsRace"] = is_race

    cols = [
        "Year", "Event", "Session", "IsRace", "Driver", "Team", "RunId",
        "LapNumber", "LapInRun", "LapsIntoRun", "Stint", "Compound", "TyreAge",
        "FreshTyre", "LapTimeS", "FuelKg", "FuelBurnKgPerLap", "SessionProgress",
        "SessionLapsBefore", "SessionTotalLaps", "SessionDate", "LapStartS",
        "TrackTemp", "AirTemp", "RunPaceRef", "Position",
    ]
    cols = [c for c in cols if c in laps.columns]
    return laps[cols].reset_index(drop=True)


def summarise(laps: pd.DataFrame) -> pd.DataFrame:
    """One row per run - useful for eyeballing what survived cleaning."""
    if laps.empty:
        return pd.DataFrame()
    g = laps.groupby(["Session", "Driver", "RunId", "Compound"], sort=False)
    out = g.agg(
        laps_kept=("LapTimeS", "size"),
        age_start=("TyreAge", "min"),
        age_end=("TyreAge", "max"),
        fresh=("FreshTyre", "first"),
        best=("LapTimeS", "min"),
        median=("LapTimeS", "median"),
        raw_slope_s_per_lap=("LapTimeS", lambda x: np.polyfit(np.arange(len(x)), x, 1)[0]
                             if len(x) > 2 else np.nan),
    ).reset_index()
    return out.sort_values(["Session", "Driver", "RunId"])
