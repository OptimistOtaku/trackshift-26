# Demo data contract

Everything the UI needs is static JSON in `artifacts/demo/`. No server, no Python at runtime.
Fetch a file, read the numbers, draw. Written by `scripts/export_demo.py`.

The contract is frozen: field names and shapes below will not change before the presentation.
If a number needs to move, the value changes and the shape does not.

```
artifacts/demo/
  index.json            what exists, and the headline numbers
  model.json            fitted coefficients — lets the UI compute live, client-side
  races/R01.json  …  R12.json
```

---

## `index.json`

```jsonc
{
  "season": 2026,
  "generated": "2026-09-09",
  "headline": {
    "stops": 288,
    "events": 12,
    "rmse_s": 0.9496,          // out-of-sample, leave-one-event-out
    "baseline_rmse_s": 1.0776, // season-mean baseline
    "improvement_pct": 11.9,
    "calib_slope": 0.8166,     // 1.0 = magnitudes right
    "events_won": 7,
    "events_scored": 11
  },
  "pit_loss": { "season_median_s": 21.75, "min_s": 20.07, "max_s": 23.67 },
  "races": [
    { "round": 1, "event": "Australian Grand Prix", "laps": 58,
      "file": "races/R01.json", "pit_loss_s": 21.70, "track_temp_c": 41.2 }
  ]
}
```

## `model.json`

Coefficients for the deployed spec (compound pair + track temp + traffic). The UI can predict
a step for any scenario without a round trip:

```
step = intercept
     + pair[<pair>]                 (0.0 for the reference pair)
     + tt_coef  * (track_temp_c - tt_mean)
     + traf_coef * d_close
```

```jsonc
{
  "spec": ["pair", "tt", "traf"],
  "intercept": 1.05,
  "tt_mean": 43.7,
  "tt_coef": 0.041,
  "traf_coef": 0.50,
  "pairs": { "HARD>HARD": 0.0, "MEDIUM>HARD": 0.62, "SOFT>MEDIUM": 0.88 },
  "degradation": {
    "b1": 0.0704, "b2": -0.00164, "peak_age": 21.5, "max_age_seen": 50,
    "note": "phi(a) = b1*a + b2*a^2, HELD FLAT past peak_age. Never let it decline — a declining phi claims tyres get faster as they wear, which is the sign error this project exists to point at."
  },
  "fresh_age": 3.0
}
```

`phi` in JS, including the saturation, which is not optional:

```js
const phi = (a, d) => { const x = Math.min(Math.max(a, 0), d.peak_age);
                        return d.b1 * x + d.b2 * x * x; };
```

## `races/R08.json`

One file per race. `laps` drives the replay scrubber; `stops` are the real decisions.

```jsonc
{
  "round": 8, "event": "Austrian Grand Prix", "laps": 71,
  "pit_loss_s": 21.69, "track_temp_c": 51.1,
  "drivers": ["VER", "NOR", "..."],
  "laps_data": [
    { "lap": 12, "driver": "VER", "lap_time_s": 70.42, "compound": "MEDIUM",
      "tyre_age": 11, "position": 1, "fuel_kg": 55.2, "frac_close": 0.0 }
  ],
  "stops": [
    { "driver": "VER", "pit_lap": 36, "pair": "MEDIUM>HARD",
      "age_old": 35, "step_obs_s": 1.41, "step_pred_s": 1.67 }
  ]
}
```

`step_obs_s` is measured, `step_pred_s` is the model out of sample. Plotting them against each
other IS the validation figure — no extra computation needed.

---

## The two demo surfaces

### 1. Race replay scrubber

Scrub a lap; show each car's tyre age, compound, and the pace the model says a stop would buy
right now. Everything comes from `laps_data` plus `model.json`.

### 2. Undercut calculator — **this is the hero feature**

Inputs: my compound pair, my tyre age, rival's tyre age, gap in seconds, track temp.
Output: do I clear them, and how long they must stay out.

```js
// pit loss CANCELS — both cars serve the same pit lane. This is why undercuts work.
const dL = step0 - phi(ageMine, deg) + phi(deg.fresh_age ?? 3, deg);
let gained = 0, rows = [];
for (let k = 1; k <= 8; k++) {
  gained += dL + phi(ageTheirs + k, deg) - phi(k, deg);
  rows.push({ respondAfter: k, gained, gapAfter: gap - gained, ahead: gap - gained < 0 });
}
```

At Austria, lap 25, 1.5 s behind a rival on an equally old tyre: **+1.80 s on the first lap, so
they are caught even if they respond immediately.** That matches real F1 undercut values
(~1.5–2.5 s) and it is the number to put on screen large.

Show `tyre_deficit_laps` too — the cost of the undercut is emerging that many laps older than
the car you just passed. It is what makes the tool honest rather than a hype machine.

### What NOT to build

**No pit-window recommendation.** We tested it (`scripts/check_window_placebo.py`): it covers
66.9% of real stops but a width-matched mid-race window covers 66.2%, so it adds nothing over
"pit halfway through." It stays in the codebase as a diagnostic and in the deck as a negative
result. Don't put a "recommended lap" in the UI — we can't defend it, and being asked to defend
it is worse than not having it.

**No safety-car probability input that looks fitted.** If SC appears, it is a slider the user
sets, labelled as an assumption. Twelve races at twelve circuits is one observation per
circuit; we cannot estimate it.
