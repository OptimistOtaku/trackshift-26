# Replay data — every lap, unfiltered

`artifacts/demo/replay/R01.json … R12.json`, written by `scripts/export_replay.py`.

This is a **second, additive** set of files. Nothing in `docs/DEMO_CONTRACT.md` changes:
`artifacts/demo/races/*.json`, `index.json` and `model.json` keep their shapes and their
numbers. If you are drawing the undercut calculator or the validation scatter, you still want
`races/`. If you are drawing the race replay scrubber, you want `replay/`.

---

## Why this exists (the bug)

`data/season_2026.parquet` is the **model fitting table**. `pitwall.data.clean_laps` builds it,
and it drops any lap that is not representative of green-flag pace:

- not green flag (safety car, VSC, yellow, red)
- in-laps and out-laps
- deleted laps
- non-slick tyres
- laps missing a lap time, compound, tyre life or stint
- laps outside a ±7% pace band around their own run's 20th-percentile lap time
- laps in runs shorter than 4 laps

Every one of those exclusions is correct **for fitting a degradation curve**. A lap run at
120 s behind a safety car tells you nothing about how fast a MEDIUM tyre is at 20 laps old, and
leaving it in would poison the slope this project exists to measure. `clean_laps` should not
change.

The replay scrubber was built on the same table, and that is where it went wrong. A replay is
not an estimator. It is a picture of what happened. Filtering it does not remove noise, it
removes **the race**:

```
R01 Australia    blank: 1, 12, 13          R06 Monaco       blank: 1, 60-71
R02 China        blank: 1, 10-13, 18, 33   R08 Austria      blank: 24, 25
R03 Japan        blank: 22-27              R09 Britain      blank: 1, 2  (+ laps 48-52 missing entirely)
R04 Miami        blank: 5-11               R10 Belgium      blank: 1-4, 8, 18, 20
R05 Canada       blank: 1, 13, 30          R12 Netherlands  blank: 1-5, 54, 55
```

57 laps with zero rows. Scrub onto one and the table renders empty. Those laps are not the
boring ones — Monaco 60-71 is the safety-car and red-flag sequence that decided the race, and
lap 1 is missing from five races because a standing start makes the first lap ~20 s slower than
the run's reference pace and the ±7% band throws it out.

British GP was worse than blank. `races/R09.json` reports `"laps": 47` for a **52-lap** race,
because that field is the highest lap number that survived filtering. The last five laps did
not exist as far as the UI was concerned, so the scrubber's track just ended early.

The fix is not a looser filter in `data.py`. The fit needs that filter. The fix is a separate
export that does not filter at all, and which carries the flags saying *why* the fit would have
dropped each lap — so the UI can grey a lap out, or label it "SAFETY CAR", instead of showing
nothing.

## Source

Straight from FastF1's `session.laps` for each race, not from the parquet. The parquet is
already stripped by the time anything reads it, so going back to the raw session is the only
way to recover the missing laps.

Runs entirely from the 2.7 GB on-disk cache in `data/cache` with `Cache.offline_mode(True)` —
no network at all. Twelve races load in about 1.5 s each. `--allow-network` exists for
refreshing the cache and should not be needed.

Round numbering comes from `pipeline.completed_events`, the same schedule call `build_season`
used, intersected with the per-event frames in `data/frames/`. That pins the set to exactly the
twelve events the rest of the artifacts describe — `completed_events` on its own would now also
return round 13, which nothing else in the repo covers. The script cross-checks each event name
against `races/R*.json` and prints `ROUND MISMATCH` if R06 ever stops meaning Monaco in both.

---

## Shape

```jsonc
{
  "round": 6,
  "event": "Monaco Grand Prix",
  "laps": 78,                    // scheduled race distance, NOT "highest lap we have data for"
  "scheduled_laps": 78,
  "unfiltered": true,
  "drivers": ["ALB", "ALO", "..."],
  "rows": 1452,
  "clean_rows": 1149,            // how many would survive the fit filter
  "non_clean_rows": 303,
  "blank_laps": [],              // lap numbers with STILL no rows — render a caption, not an empty table
  "unplaceable_rows": 0,         // rows dropped for having no lap number or no driver
  "clean_source": "clean_laps",
  "track_status_codes": { "1": "green", "4": "safety car", "...": "..." },
  "note": "…",
  "laps_data": [
    { "lap": 63, "driver": "ANT", "lap_time_s": 120.412, "compound": "SOFT",
      "tyre_age": 6, "position": 1,
      "green": false, "in_lap": false, "out_lap": false, "deleted": false,
      "clean": false, "track_status": "4" }
  ]
}
```

`lap`, `driver`, `lap_time_s`, `compound`, `tyre_age`, `position` are the **same field names**
as `races/*.json` `laps_data`, so pointing the scrubber at the new URL is most of the work.

Two deliberate differences from `races/`:

- **`fuel_kg` and `frac_close` are not here.** Both are model inputs computed by the fitting
  path. They are undefined for exactly the laps this file exists to add, and a replay does not
  need them. They are still in `races/`.
- **`lap`, `tyre_age` and `position` are JSON integers**, not floats. `races/` emits `"lap": 2.0`
  because it round-trips through a float column. These are counts. `DEMO_BRIEF.md` is already
  explicit that floats arriving where the UI expects integers cost an afternoon, so they are
  fixed at the source rather than passed on.

### Flags

| field | meaning |
|---|---|
| `green` | `TrackStatus` is `1` and nothing else, for the whole lap. Anything else means yellow, SC, VSC or red was showing at some point. |
| `in_lap` | `PitInTime` is set — the car pitted at the end of this lap. |
| `out_lap` | `PitOutTime` is set — the car left the pit lane during this lap. |
| `deleted` | The stewards deleted the lap time (track limits). |
| `clean` | This exact lap is in the model's training table. |
| `track_status` | The raw FastF1 code string, unparsed. |

`track_status` is a **concatenation** of every code seen during the lap, not a single code, so
`"412"` means green, then safety car, then yellow — in the order they appeared. Test with
"contains", never with equality. `"1"` alone is a fully green lap. Codes: `1` green, `2` yellow,
`4` safety car, `5` red flag, `6` VSC deployed, `7` VSC ending. The map ships in each file as
`track_status_codes` so the UI does not have to hardcode a legend it might get wrong.

`clean` is computed by **calling `data.clean_laps` and checking membership**, not by
re-deriving its mask. That matters: `clean_laps` filters on the keep mask *and* the within-run
pace band *and* a minimum run length, and a hand-copied version of that logic would quietly
drift away from the model. Verified: for all twelve races the set of `clean: true` rows equals
the `laps_data` of `races/R*.json` exactly, row for row on `(lap, driver)`. That is what makes
`clean` a claim about the model rather than a guess.

### Nulls are real data

`lap_time_s` is `null` where FastF1 recorded no lap time — 228 rows across the season, mostly
red-flag and retirement laps. **Render the gap; do not drop the row.** The row still carries
position, compound and tyre age, which is exactly what a replay needs to show a car sitting in
the pit lane under a red flag. Dropping null-lap-time rows is a smaller version of the original
bug.

Every other field can be null too, and the UI has to cope with each: `compound` 25 rows,
`tyre_age` 46 rows, `position` 22 rows. `lap` and `driver` are the only two guaranteed
non-null — a row missing either cannot be placed on a scrubber at all, so the script drops it
and reports the count in `unplaceable_rows` rather than losing it silently. That count is 0 for
all twelve races.

`blank_laps` is currently empty for all twelve races. It is exported anyway so that if a future
session does have a hole, the UI can render "no timing data for this lap" instead of an
ambiguous empty table.

### Not here, on purpose

No recommended pit lap, no pit window, no undercut verdict, no stop value. The window
recommendation was tested in `scripts/check_window_placebo.py`: it covers 68.4% of real stops
against 65.8% for a width-matched mid-race window, a margin too small to lean on, and per event
that mid-race constant tracks the chosen lap better than the window centre does — so it adds
nothing over "pit halfway through" and was cut. This file is observations only. Strategy numbers come from `model.json`,
computed client-side.

---

## Worked example: Monaco, lap 63

In `races/R06.json` lap 63 does not exist. Zero rows. The scrubber goes blank at the exact
moment the race is decided.

In `replay/R06.json` it is 17 rows, of which the leader's is:

```json
{ "lap": 63, "driver": "ANT", "lap_time_s": 120.412, "compound": "SOFT", "tyre_age": 6,
  "position": 1, "green": false, "in_lap": false, "out_lap": false, "deleted": false,
  "clean": false, "track_status": "4" }
```

Read it as: Antonelli leads on a 6-lap-old SOFT, lapping at 2:00.4 — some 44 s off green-flag
pace — because `track_status` is `4` and the safety car is out. `clean: false` says the model
never saw this lap, `green: false` says why. The UI should show the field, grey the times, and
put "SAFETY CAR" across the lap. All of that is in the row.

Five laps later, lap 68, `track_status` is `"451"` — safety car, then red flag, then green —
and 9 of the 16 cars have `lap_time_s: null` because the race was stopped mid-lap. `in_lap` and
`out_lap` are both true for cars that came in and went back out around the stoppage. Again:
render it, do not drop it.

Compare with a lap the model does use, Monaco lap 30:

```json
{ "lap": 30, "driver": "ALB", "lap_time_s": 79.052, "compound": "MEDIUM", "tyre_age": 30,
  "position": 10, "green": true, "in_lap": false, "out_lap": false, "deleted": false,
  "clean": true, "track_status": "1" }
```

And one that looks clean but is not — Australia, lap 1:

```json
{ "lap": 1, "driver": "ALB", "lap_time_s": 99.376, "compound": "MEDIUM", "tyre_age": 1,
  "position": 12, "green": true, "in_lap": false, "out_lap": false, "deleted": false,
  "clean": false, "track_status": "1" }
```

Green, not a pit lap, not deleted — and still excluded, because a standing start puts lap 1
about 20 s outside the run's pace band. This is the case the boolean flags alone do not
explain, and it is why `clean` is computed by running the real filter instead of being inferred
from `green && !in_lap && !out_lap && !deleted`. A UI that infers it will disagree with the
model on lap 1 of every race.

---

## Per-race counts

| file | event | laps | rows | non-clean | blank |
|---|---|---:|---:|---:|---:|
| R01 | Australian Grand Prix | 58 | 1006 | 181 (18.0%) | 0 |
| R02 | Chinese Grand Prix | 56 | 920 | 183 (19.9%) | 0 |
| R03 | Japanese Grand Prix | 53 | 1107 | 181 (16.4%) | 0 |
| R04 | Miami Grand Prix | 57 | 1040 | 261 (25.1%) | 0 |
| R05 | Canadian Grand Prix | 68 | 1211 | 286 (23.6%) | 0 |
| R06 | Monaco Grand Prix | 78 | 1452 | 303 (20.9%) | 0 |
| R07 | Barcelona Grand Prix | 66 | 1236 | 231 (18.7%) | 0 |
| R08 | Austrian Grand Prix | 71 | 1339 | 180 (13.4%) | 0 |
| R09 | British Grand Prix | 52 | 1113 | 298 (26.8%) | 0 |
| R10 | Belgian Grand Prix | 44 | 872 | 188 (21.6%) | 0 |
| R11 | Hungarian Grand Prix | 70 | 1431 | 199 (13.9%) | 0 |
| R12 | Dutch Grand Prix | 72 | 1368 | 285 (20.8%) | 0 |

14,095 rows, 2.60 MB written compact. `races/` is 1.55 MB for the 11,319 clean rows; the extra
1 MB is the 2,776 laps the replay was missing plus six flags per row. One in five race laps in
2026 was not a clean green-flag lap, which is the real answer to "how much was the replay
hiding".

R09 is the row to look at: 52 laps here against `races/R09.json`'s 47.

## Regenerating

```
python scripts/export_replay.py                 # all twelve, offline, ~25 s
python scripts/export_replay.py --rounds 6 8    # just Monaco and Austria
```

The script skips and reports any session that will not load from cache rather than aborting the
run, so a single bad cache entry cannot cost you the other eleven files.
