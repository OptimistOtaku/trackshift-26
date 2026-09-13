"""Emit EVERY lap of every 2026 race as JSON, for the replay scrubber. Unfiltered.

WHY THIS IS A SEPARATE SCRIPT FROM export_demo.py
-------------------------------------------------
`scripts/export_demo.py` writes `artifacts/demo/races/R*.json` out of
`data/season_2026.parquet`. That parquet is the MODEL FITTING table: `pitwall.data.clean_laps`
throws away any lap that is not green-flag, plus in-laps, out-laps, deleted laps, wet-tyre laps
and laps that fall outside a within-run pace band. Those exclusions are correct for fitting a
degradation curve - a lap run behind a safety car tells you nothing about how fast a tyre is -
and they are wrong for a replay, which is a picture of the race rather than an estimator.

The replay inherited the estimator's filter and it shows. 57 laps across the season had zero
rows, so scrubbing onto them rendered an empty table: Monaco 60-71 (the whole safety-car and
red-flag sequence that decided the race), Austria 24-25, Miami 5-11, Japan 22-27, and lap 1 of
five different races. Those are not dirty laps. They are the laps a judge will scrub to first.
British GP was worse than blank: the filtered file's `laps` field reported 47 laps for a 52-lap
race, because the last five laps had no surviving rows at all, so the scrubber's track simply
ended early.

So the fix is not a looser filter in `data.py` - the fit needs that filter - it is a second
export with no filter at all. This script goes back to FastF1 and dumps `session.laps` whole,
tagging each lap with the flags that explain why the fit dropped it (`green`, `in_lap`,
`out_lap`, `deleted`, `clean`) plus the raw `track_status` code so the UI can put "SAFETY CAR"
on screen instead of nothing. `lap_time_s` is null where FastF1 has no lap time, which is real
and must be rendered as a gap rather than dropped.

Output goes to `artifacts/demo/replay/`, a NEW directory. `races/` is left exactly as it is:
it carries `stops` (the measured pit-stop steps) and the fuel/traffic columns the validation
figure needs, and it is the file the frozen contract in `docs/DEMO_CONTRACT.md` describes. The
two directories answer two different questions and neither replaces the other. See
`docs/REPLAY_DATA.md`.

Round numbering is taken from the FastF1 schedule (`pipeline.completed_events`), the same
source `build_season` used, and is cross-checked against the event names already in
`artifacts/demo/races/`. R06 means Monaco in both directories or this script complains.

NO STRATEGY OUTPUT. This file carries observations only - no recommended pit lap, no undercut
verdict, no stop value. The pit-window recommendation was tested
(`scripts/check_window_placebo.py`), found to be indistinguishable from "pit halfway through",
and cut on purpose. Do not add it back here by the side door.

Runs entirely from the on-disk FastF1 cache in `data/cache` with network access disabled, so it
cannot hang on stage. Pass --allow-network only when refreshing the cache.

Run: python scripts/export_replay.py
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(_HERE, ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, _HERE)

import fastf1                                                        # noqa: E402

from pitwall import data as D                                        # noqa: E402
from pitwall.data import SessionRef, _green_flag                     # noqa: E402
from pitwall.pipeline import _slug, completed_events                 # noqa: E402

# Reused, not reimplemented: one definition of how floats reach the UI. It also maps every
# non-finite float to JSON null, which is exactly what we need for a missing lap time.
from export_demo import _round_floats                                # noqa: E402

YEAR = 2026
FRAME_DIR = os.path.join(ROOT, "data", "frames")
OUT = os.path.join(ROOT, "artifacts", "demo", "replay")
RACES = os.path.join(ROOT, "artifacts", "demo", "races")

# Field names match `races/R*.json` laps_data so the frontend swap is a URL change, then the
# flags. Deliberately NOT carried over: fuel_kg and frac_close. Both are model inputs computed
# by the fitting path, they are undefined for the laps this file exists to add, and a replay
# does not need them.
LAP_COLS = ["lap", "driver", "lap_time_s", "compound", "tyre_age", "position",
            "green", "in_lap", "out_lap", "deleted", "clean", "track_status"]

# FastF1 concatenates every status code seen during a lap, so '412' is "green, then SC, then
# yellow". Shipped per file so the UI does not have to hardcode a legend it might get wrong.
TRACK_STATUS_CODES = {
    "1": "green", "2": "yellow", "3": "unknown", "4": "safety car",
    "5": "red flag", "6": "VSC deployed", "7": "VSC ending",
}


def _int_or_none(v) -> int | None:
    """Whole-lap quantities as JSON integers.

    Lap number, tyre age and position are counts. The filtered export leaks them as floats
    (`"lap": 2.0`) because it round-trips through a float column, and DEMO_BRIEF is explicit
    that floats coming out of JSON where the UI expects integers cost an afternoon. Fixed here
    rather than propagated.
    """
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if not np.isfinite(f) else int(round(f))


def _str_or_none(v) -> str | None:
    if v is None or (isinstance(v, float) and not np.isfinite(v)) or v is pd.NA:
        return None
    s = str(v)
    return None if s in ("", "nan", "None", "<NA>") else s


def clean_keys(session) -> tuple[set[tuple[str, int]], str]:
    """(driver, lap) pairs that survive the fit filter, by running the fit filter.

    `clean` has to mean "this exact lap is in the model's training table", so it is computed by
    calling `data.clean_laps` rather than by re-deriving its mask here. Re-deriving would drift:
    `clean_laps` drops laps on the `keep` mask AND on a within-run pace band AND on a minimum
    run length, and a hand-copied version of that would quietly disagree with the model.
    """
    try:
        cl = D.clean_laps(session)
    except Exception as exc:
        print(f"    WARNING: clean_laps failed ({type(exc).__name__}: {exc}); "
              f"falling back to the keep mask only")
        return set(), "keep-mask fallback"
    if cl.empty:
        return set(), "clean_laps (empty)"
    return (set(zip(cl["Driver"].astype(str), cl["LapNumber"].astype(int))),
            "clean_laps")


def _fallback_clean(laps: pd.DataFrame) -> pd.Series:
    """The `keep` mask from data.clean_laps, for the case where clean_laps itself blew up.

    Coarser than the real thing - it does not apply the within-run pace band or the minimum
    run length - so it over-reports `clean`. Only reachable on a session that failed to clean.
    """
    keep = (laps["LapTimeS"].notna() & laps["Green"]
            & ~laps["IsInLap"] & ~laps["IsOutLap"]
            & laps["Compound"].notna() & laps["TyreLife"].notna() & laps["Stint"].notna()
            & laps["Compound"].isin(D.SLICKS))
    if "Deleted" in laps.columns:
        keep &= laps["Deleted"].fillna(False).eq(False)
    return keep


def replay_json(session, rnd: int, event: str) -> dict:
    """Every lap FastF1 has for one race, with the fit-exclusion flags attached."""
    laps = session.laps.copy()
    laps["LapTimeS"] = laps["LapTime"].dt.total_seconds()
    laps["Green"] = laps["TrackStatus"].apply(_green_flag)
    laps["IsInLap"] = laps["PitInTime"].notna()
    laps["IsOutLap"] = laps["PitOutTime"].notna()
    if "Deleted" in laps.columns:
        laps["IsDeleted"] = laps["Deleted"].fillna(False).astype(bool)
    else:
        laps["IsDeleted"] = False

    keys, clean_src = clean_keys(session)
    fallback = _fallback_clean(laps) if clean_src == "keep-mask fallback" else None

    # A lap with no lap number or no driver cannot be placed on a scrubber, so it is dropped -
    # and counted, because silently losing rows is how this bug happened in the first place.
    usable = laps["LapNumber"].notna() & laps["Driver"].notna()
    n_unplaceable = int((~usable).sum())
    laps = laps.loc[usable]

    rows = []
    for i, r in laps.iterrows():
        drv, lap = str(r["Driver"]), int(r["LapNumber"])
        is_clean = bool(fallback.loc[i]) if fallback is not None else ((drv, lap) in keys)
        rows.append({
            "lap": lap,
            "driver": drv,
            "lap_time_s": float(r["LapTimeS"]),          # NaN -> null via _round_floats
            "compound": _str_or_none(r.get("Compound")),
            "tyre_age": _int_or_none(r.get("TyreLife")),
            "position": _int_or_none(r.get("Position")),
            "green": bool(r["Green"]),
            "in_lap": bool(r["IsInLap"]),
            "out_lap": bool(r["IsOutLap"]),
            "deleted": bool(r["IsDeleted"]),
            "clean": is_clean,
            "track_status": _str_or_none(r.get("TrackStatus")),
        })
    rows.sort(key=lambda d: (d["lap"], d["driver"]))

    # Scheduled distance, not "the highest lap number we happen to have a row for". That
    # distinction is the British GP bug: 52 laps were run, the filtered file said 47.
    scheduled = _int_or_none(getattr(session, "total_laps", None)) or 0
    n_laps = max(scheduled, max((d["lap"] for d in rows), default=0))
    have = {d["lap"] for d in rows}
    blank = [l for l in range(1, n_laps + 1) if l not in have]
    n_clean = sum(1 for d in rows if d["clean"])

    return {
        "round": int(rnd),
        "event": str(event),
        "laps": int(n_laps),
        "scheduled_laps": int(scheduled) or None,
        "unfiltered": True,
        "drivers": sorted({d["driver"] for d in rows}),
        "rows": len(rows),
        "clean_rows": int(n_clean),
        "non_clean_rows": int(len(rows) - n_clean),
        "blank_laps": blank,
        "unplaceable_rows": n_unplaceable,
        "clean_source": clean_src,
        "track_status_codes": TRACK_STATUS_CODES,
        "note": ("Every lap FastF1 recorded, including safety-car, VSC, red-flag, in- and "
                 "out-laps. lap_time_s is null where no lap time was recorded; render the gap, "
                 "do not drop the row. clean=false means the lap was excluded from model "
                 "fitting, not that it is wrong."),
        "laps_data": rows,
    }


def target_rounds(year: int) -> list[tuple[int, str]]:
    """(round, event name) for exactly the events that are already exported.

    `completed_events` alone is not safe to use as the round list any more: it returns every
    event whose race has run as of today, and the season has moved on since
    `data/season_2026.parquet` was built. Intersecting it with the per-event frames on disk
    pins the set to the twelve events the rest of the artifacts describe.
    """
    ev = completed_events(year)
    out = []
    for _, r in ev.sort_values("RoundNumber").iterrows():
        frame = os.path.join(FRAME_DIR, f"{year}_{_slug(r['EventName'])}.parquet")
        if os.path.exists(frame):
            out.append((int(r["RoundNumber"]), str(r["EventName"])))
    return out


def check_round_numbering(rounds: list[tuple[int, str]]) -> None:
    """R06 must mean Monaco here and in races/. Warn loudly if it does not."""
    for rnd, event in rounds:
        path = os.path.join(RACES, f"R{rnd:02d}.json")
        if not os.path.exists(path):
            print(f"    note: no races/R{rnd:02d}.json to cross-check against")
            continue
        try:
            with open(path, encoding="utf-8") as f:
                existing = json.load(f).get("event")
        except Exception as exc:
            print(f"    note: could not read races/R{rnd:02d}.json ({type(exc).__name__})")
            continue
        if existing != event:
            print(f"    *** ROUND MISMATCH R{rnd:02d}: races/ says {existing!r}, "
                  f"schedule says {event!r}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--rounds", type=int, nargs="*", default=None,
                    help="subset of rounds to export (default: every exported event)")
    ap.add_argument("--allow-network", action="store_true",
                    help="let FastF1 hit the network; off by default so a missing cache entry "
                         "fails fast instead of stalling")
    args = ap.parse_args()

    fastf1.set_log_level("ERROR")
    cache = D.enable_cache()
    if not args.allow_network:
        fastf1.Cache.offline_mode(True)
    print(f"cache {cache}  offline={not args.allow_network}")

    rounds = target_rounds(YEAR)
    if args.rounds:
        rounds = [(r, e) for r, e in rounds if r in set(args.rounds)]
    if not rounds:
        print("no rounds to export")
        return
    check_round_numbering(rounds)

    os.makedirs(OUT, exist_ok=True)
    written, skipped, totals = [], [], {"rows": 0, "non_clean": 0, "blank": 0}
    for rnd, event in rounds:
        try:
            s = D.load_session(SessionRef(YEAR, event, "R"), telemetry=False)
        except Exception as exc:
            print(f"[R{rnd:02d}] {event[:24]:24s} SKIPPED: {type(exc).__name__}: {exc}")
            skipped.append((rnd, event, f"{type(exc).__name__}: {exc}"))
            continue

        rj = replay_json(s, rnd, event)
        name = f"R{rnd:02d}.json"
        with open(os.path.join(OUT, name), "w", encoding="utf-8") as f:
            json.dump(_round_floats(rj), f, separators=(",", ":"))

        written.append(rj)
        totals["rows"] += rj["rows"]
        totals["non_clean"] += rj["non_clean_rows"]
        totals["blank"] += len(rj["blank_laps"])
        extra = ""
        if rj["blank_laps"]:
            extra = f"  STILL BLANK: {rj['blank_laps']}"
        if rj["unplaceable_rows"]:
            extra += f"  dropped {rj['unplaceable_rows']} unplaceable"
        print(f"[R{rnd:02d}] {rj['event'][:24]:24s} laps=1-{rj['laps']:<3d} "
              f"rows={rj['rows']:5d}  non_clean={rj['non_clean_rows']:5d} "
              f"({100.0 * rj['non_clean_rows'] / max(rj['rows'], 1):4.1f}%)  "
              f"blank={len(rj['blank_laps'])}{extra}")

    size = sum(os.path.getsize(os.path.join(OUT, f)) for f in os.listdir(OUT))
    print(f"\nwrote {len(written)} files to {os.path.relpath(OUT, ROOT)}  "
          f"({size / 1e6:.2f} MB, {totals['rows']} rows, "
          f"{totals['non_clean']} non-clean, {totals['blank']} blank laps remaining)")
    for rnd, event, why in skipped:
        print(f"SKIPPED R{rnd:02d} {event}: {why}")


if __name__ == "__main__":
    main()
