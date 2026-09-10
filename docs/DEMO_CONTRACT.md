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

---

## `model.json` -> `degradation_curves` (added, nothing above changed)

Purely additive. Every field documented above is still there, still spelled the same, still
means the same thing. This block is new, and it carries the opening argument of the project.

**What it is.** Fit `lap_time ~ tyre_age` on practice long runs the ordinary way - a run
intercept, nothing else - and two of the three compounds come back claiming tyres get FASTER
as they wear. Inside a run the car burns one lap of fuel for every lap the tyre ages, so fuel
mass and tyre age are collinear and the age slope quietly absorbs the fuel effect, which has
the opposite sign. The fix is to estimate the fuel sensitivity somewhere else: on race laps,
where stints begin at different points in the race, so the same tyre age is seen at many fuel
loads and fuel is separable from age. Subtract it, measure the rubber going down, and the sign
flips.

Slopes are s/lap at tyre age 10 (`slope_ref_age`). Positive means the tyre is losing pace,
which is the direction physics allows:

| compound | naive | deconfounded | |
|---|---|---|---|
| SOFT | +0.0518 | +0.1096 | right sign already, understated 2.1x |
| MEDIUM | -0.0459 | +0.0738 | **sign flip** |
| HARD | -0.1535 | +0.0631 | **sign flip** |

`lambda_fuel_s_per_kg` is +0.0294 (se 0.0039), against a literature range of 0.030-0.035 s/kg.
That agreement is the check that this is a real physical quantity and not a fitting artefact,
and it is worth a line of copy on screen.

### Shape

```jsonc
"degradation_curves": {
  "slope_ref_age": 10.0,
  "lambda_fuel_s_per_kg": 0.029425,   // estimated on race laps, applied to practice laps
  "lambda_se_s_per_kg": 0.00394,
  "lambda_events": 12,
  "practice": {
    "n_laps": 2991, "n_runs": 469,
    "naive_spec": "no fuel correction, no traffic term, no track evolution",
    "deconfounded_spec": "fuel corrected with lambda, traffic measured, rubber measured",
    "compounds": {
      "HARD": {
        "age_lo": 2.0, "age_hi": 30.0,   // the tyre ages practice actually ran
        "anchor_age": 2.0,               // both curves are pinned to delta_s = 0 here
        "sign_flip": true,
        "naive": {
          "b1": -0.380873, "b2": 0.011368,
          "slope_s_per_lap": -0.153516,       // s/lap at age 10 - NEGATIVE, the wrong one
          "total_s_over_support": -0.478853,  // age 2 -> 30 across the whole curve
          "curve": [ { "age": 2, "delta_s": 0.0 },
                     { "age": 3, "delta_s": -0.324034 },
                     /* ... */
                     { "age": 17, "delta_s": -2.47326 },
                     /* ... */
                     { "age": 30, "delta_s": -0.478853 } ]
        },
        "deconfounded": {
          "b1": 0.005766, "b2": 0.002868,
          "slope_s_per_lap": 0.063123,
          "total_s_over_support": 2.731018,
          "curve": [ { "age": 2, "delta_s": 0.0 },
                     { "age": 3, "delta_s": 0.020105 },
                     /* ... */
                     { "age": 30, "delta_s": 2.731018 } ]
        }
      },
      "MEDIUM": { /* same fields */ },
      "SOFT":   { /* same fields */ }
    }
  },
  "race": { /* below */ },
  "note": "...", "lambda_note": "...", "not_a_predictor": "..."
}
```

`curve` is already sampled at every whole lap from `age_lo` to `age_hi`, and `age` is a JSON
**integer**, not a float like `laps_data.tyre_age`. Both curves for a compound share the same
ages, so they plot straight onto one axis with no interpolation and no arithmetic:

```js
const H = model.degradation_curves.practice.compounds.HARD;
// x: H.naive.curve[i].age   y: H.naive.curve[i].delta_s
// x: H.deconfounded.curve[i].age   y: H.deconfounded.curve[i].delta_s
```

**Worked example, HARD.** Both lines leave `age = 2` at exactly `delta_s = 0`. By age 17 the
naive line has fallen to **-2.473 s/lap** - it is claiming a HARD tyre seventeen laps old is
two and a half seconds a lap quicker than a nearly new one - and it is still at -0.479 at age
30. The deconfounded line climbs the whole way, +0.321 by age 10 and **+2.731** by age 30. Two
lines, one axis, opposite directions: that is the picture.

**Why both curves start at zero.** Practice identifies the SHAPE of a degradation curve and not
its level. Every run has its own intercept and every run is a single compound, so nothing in
the data says whether a SOFT is intrinsically quicker than a MEDIUM. Both curves are therefore
pinned to zero at `anchor_age` (the youngest tyre age the fit saw), and `delta_s` reads
"seconds per lap slower than a tyre of that age, same compound". Pinning both to the same
anchor is what makes the gap between the lines entirely the confounding, and not a choice about
where the axis starts.

### `degradation_curves.race`

```jsonc
"race": {
  "b1": 0.070371, "b2": -0.00164,
  "peak_age": 21.458624, "max_age_seen": 50.0, "n_stops": 288,
  "curve": [ { "age": 0,  "delta_s": 0.0 },
             { "age": 1,  "delta_s": 0.068731 },
             /* ... */
             { "age": 20, "delta_s": 0.751543 },
             { "age": 21, "delta_s": 0.754686 },
             { "age": 22, "delta_s": 0.755031 },   // clamped at peak_age from here on
             /* ... */
             { "age": 50, "delta_s": 0.755031 } ]
}
```

`b1`, `b2` and `peak_age` are the same numbers as `degradation` at the top of `model.json` -
this is that same `phi`, sampled at every whole lap from 0 to the oldest tyre a measured stop
came off. It agrees with the `phi` snippet above to within 0.15 ms, which is the rounding of
`b1` and `b2`, so the gauge and the curve are one object and cannot drift apart on screen.

**The tail is flat and must be drawn flat.** Every point from age 22 to age 50 is exactly
`0.755031`. That is the saturation clamp, not a bug and not a plotting artefact: the fitted
quadratic has `b2 < 0` and would bend downwards past its peak, which would claim tyres get
faster as they wear. If your chart library smooths it into a decline, fix the chart library.

### What to do with these curves

Draw them. That is the whole permitted use.

The deconfounded practice curve is defensible in sample and **does not transfer to a race** -
calibration slope +0.006 against the measured pit-stop step, which is why `stopvalue.py` exists
at all. So do not compute an undercut, a stop value or a lap time from
`degradation_curves.practice`. Anything that computes uses `degradation` / `degradation_curves.race`,
exactly as it did before this block was added. The block also carries a `not_a_predictor`
string saying so, in case this page and the file ever get separated.
