# PITWALL

Tyre degradation intelligence for Formula 1 — separating what a tyre actually costs you from
the fuel, traffic and track evolution that hide it.

Built for **TrackShift 2026** (problem statement: *Tyre Degradation Intelligence*), on the
2026 season: **14,310 laps, 12 events, 1,068 runs** pulled from FastF1.

---

## The short version

The conventional approach — fit `lap_time ~ tyre_age` on practice long runs, having removed
the confounders — **works in sample and fails out of sample**. We built it, showed it was
defensible, and then showed it does not transfer to a race.

So the deployed model predicts the quantity a race engineer actually needs instead: **the
seconds per lap a driver gains by fitting a new tyre.**

| | |
|---|---|
| Fuel sensitivity, estimated not assumed | **+0.0294 s/kg** (se 0.0039) — literature says 0.030–0.035 |
| What a fresh tyre is worth | **+1.26 s/lap** (sd 1.03), measured over 288 real pit stops |
| Deployed model vs season mean | **+11.1% RMSE**, leave-one-event-out, no free constants |
| Calibration slope | **0.79** (1.0 = magnitudes correct) |
| Per-event record | wins **7 of 11** events |

## The four questions, in the order we asked them

Reproduce all of this with one command: `python scripts/stop_value.py`

**1. Can the practice confounders be removed?** Yes — and it fixes a *sign error*. The naive
fit reports HARD tyres getting **faster** as they age (−0.15 s per 10 laps) because fuel burn
is perfectly collinear with tyre age inside a single run. Correcting fuel, traffic and track
evolution flips every compound to a physically sensible positive number.

```
spec        SOFT     MEDIUM    HARD
naive     +0.0518   -0.0459  -0.1535   <- claims tyres get faster
+rubber   +0.1096   +0.0738  +0.0631
```

**2. What does the race say about tyre age?** The pit stop is the one moment where tyre age
resets and fuel does not, so the step in pace across a stop measures the tyre effect with fuel
almost entirely cancelled. That gives us ground truth that owes nothing to the practice model.

The answer is **non-monotonic**, and this is the finding we very nearly got wrong. A linear
test finds nothing (p = 0.58). Entered with curvature, the age terms are **jointly significant
(p = 0.005)** and the value of a stop **peaks around tyre age 21–25, then declines**. A linear
test averages an inverted U to zero and reports a confident null. Degradation accumulates for
roughly twenty laps — and then stops.

**3. Does the practice-fitted curve predict that?** **No.** It gets the average roughly right
(+1.52 predicted vs +1.26 observed) and the stop-by-stop variation entirely wrong:
**calibration slope +0.006**. The curve is not merely imprecise — its variation is
uncorrelated with truth. A saturating form `A(1−exp(−a/τ))` does not rescue it either: τ is
unidentified (SSR falls 0.1% between τ=3 and τ=44 laps).

**4. What does predict it?** Compound pair, track temperature (a hotter track makes fresh
rubber worth more), and **measured** traffic. Tyre age is deliberately *not* a regressor: it
is significant in sample (R² 0.350 → 0.382) but costs out-of-sample performance
(11.1% → 10.3%, calibration 0.79 → 0.73). We report the effect and omit it from the model.

## What makes the numbers trustworthy

- **Fuel is identified where it is identifiable.** λ comes from race data, where fuel falls
  monotonically while tyre age saw-tooths at every stop. Practice runs then absorb their
  unknown starting fuel in a run intercept, with λ imported and subtracted.
- **Track evolution is measured, and identified because the log saturates.** Within-run
  evolution slope varies ~11× between FP1 and FP3 while tyre age is always 1.0/lap. A linear
  rubber count would be collinear and unidentified; `log1p(WeekendLaps)` is not.
- **Traffic comes from position telemetry**, not a guess: KD-tree snap to the racing-line
  centreline → forward gap → time-in-dirty-air fractions. Falsification check: the measure
  rises monotonically from P1–3 to P16–20, as it must.
- **~1,100 run fixed effects** are absorbed analytically via Frisch–Waugh–Lovell demeaning —
  identical coefficients, ~200× faster than explicit dummies.
- **Cluster-robust SEs** (by run for lap fits, by event for stop fits), and
  **leave-one-event-out** validation in which *no method is granted a free constant* — the
  model has to get the level right, not just the shape.

## Honest limits

The pooled gain is weighted by stop count and carried by the larger events; by event count it
is 7 of 11. Track temperature enters as an event mean, so it partly proxies for circuit
identity, and 12 events cannot cleanly separate the two. Past tyre age 30 there are only 24
stops, and drivers running a tyre that long were nursing it — selection plausibly explains
part of the decline. The scripts print all three caveats rather than smoothing them over.

## Layout

```
src/pitwall/
  data.py         FastF1 loading, run segmentation, lap cleaning
  track.py        racing-line centreline, arc-length projection
  traffic.py      forward-gap / dirty-air measurement from position telemetry
  degradation.py  the two-stage fuel + degradation model (Q1)
  stopvalue.py    the deployed model: what a fresh tyre is worth (Q4)
  validate.py     pit-step extraction and out-of-sample scoring
  plots.py        every figure
scripts/
  build_season.py   build the cached season parquet (slow, downloads telemetry)
  stop_value.py     the full evidence chain, start to finish
  make_charts.py    all 8 figures
  spike_*.py        the exploratory work, kept for provenance
docs/METHOD.md      identification notes
artifacts/          figures and result tables (committed)
```

## Running it

```bash
pip install -r requirements.txt
python scripts/build_season.py    # slow: downloads a season of telemetry into data/cache
python scripts/stop_value.py      # the evidence chain
python scripts/make_charts.py     # figures into artifacts/
```

`build_season.py` writes a ~2.7 GB FastF1 cache under `data/`, which is gitignored — it is
large, reproducible, and not source. Everything after it runs off `data/season_2026.parquet`.

## Beyond motorsport

The transferable method is *recovering a wear signal from confounded operating conditions,
then validating it against a natural experiment rather than in sample*. The intended target is
Indian commercial-vehicle fleet tyre management, where wear is confounded by axle load, road
roughness, ambient temperature and driver behaviour — structurally the same problem. The
methodological warning transfers too: an in-sample wear curve that looks excellent can carry
almost no out-of-sample information, and only a natural experiment will tell you.
