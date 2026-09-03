# PITWALL — method notes

> **Status.** This file documents the *identification* half of the project, which stands. It
> was written before we knew whether the practice-fitted curve transferred to a race. It does
> not — calibration slope +0.006 — so the deployed model predicts the value of a pit stop
> directly from race history instead. See `README.md` for what shipped and
> `src/pitwall/stopvalue.py` for why. The identification argument below is unchanged by that
> result; the validation section has been corrected to say what actually happened.

## The identification problem (this is the whole project)

The problem statement asks us to isolate *true* tyre wear from "confounding practice
variables like fuel weight, traffic, and track evolution."

Most teams will fit `lap_time ~ tyre_age` and call the slope "degradation." That is
wrong, and provably so. Observed lap time decomposes as:

    T[d,r,l] = α[d] + β[r] + λ·M_fuel + φ_c(age) + τ(track_evo) + ρ·traffic + ε

- `α[d]`  driver/car baseline
- `β[r]`  run-level intercept (absorbs unknown starting fuel of that run)
- `λ`     fuel sensitivity, s/kg  (more fuel = slower)
- `φ_c`   tyre degradation curve for compound c  ← **the quantity we want**
- `τ`     track evolution (rubbering-in, temperature)
- `ρ`     traffic penalty

### Why the naive fit fails

Within a single run, fuel mass falls linearly with lap index while tyre age rises
linearly with lap index. They are **perfectly collinear**. Fuel makes the car faster
as the run goes on; tyres make it slower. The naive slope measures the *difference*
of the two effects, not degradation.

Evidence from real data — Norris, 2026 Hungary race, MEDIUM, laps 2→16:
observed pace goes 85.2s → 85.9s, i.e. **+0.5s over 14 laps**. Fuel burn over those
same laps should have made him roughly **0.5s faster**. So the true tyre
degradation is ≈ **1.0s / 14 laps**, about double what the raw trace shows.

Season-wide the failure is worse than an understatement — it is a **sign error**. Measured
across 2026 practice, the naive fit reports MEDIUM at −0.046 and HARD at −0.154 s per 10 laps:
tyres getting *faster* as they wear. Deconfounding flips every compound positive
(+0.110 / +0.074 / +0.063). See `scripts/stop_value.py`, question 1.

### How we break the collinearity

Four independent levers, in order of strength:

1. **Race data anchors the fuel coefficient.** Across a full race, fuel declines
   monotonically from full to empty, while tyre age *saw-tooths* — resetting at every
   pit stop. Fuel and tyre age are therefore **not** collinear over a race. We
   estimate `λ` there, where it is identified.

2. **Used-tyre runs break collinearity inside practice.** Teams start some practice
   runs on scrubbed tyres. Real example: ALB, 2026 Hungary FP2, stint 3 begins at
   `TyreLife=13, FreshTyre=False`. Comparing a fresh-tyre run against a used-tyre run
   at the *same run-lap-index* separates tyre age from fuel, because the fuel term
   depends on run-lap-index while the tyre term depends on absolute tyre age.

3. **Shape.** Fuel burn is linear by construction. Degradation is not — it is convex,
   often with a cliff. A flexible basis on tyre age plus a strictly linear fuel term
   uses that shape difference as extra identifying information.

   *Verified afterwards, and it is the weakest of the three.* Shape identifies a quadratic
   fine, but it will not identify a **timescale**: profiling the saturating form
   `A(1−exp(−a/τ))` over τ moves SSR by 0.1% across τ = 3…44 laps. Do not read a physical
   wear timescale off practice data.

4. **Track evolution is identified because the log saturates.** `TrackEvo = log1p(WeekendLaps)`
   is not collinear with tyre age even though both rise with time, because its within-run slope
   varies about 11× between FP1 and FP3 while tyre age is always exactly 1.0 per lap. A *linear*
   rubber count would be collinear and unidentified. The saturation is what buys the
   identification, and dropping the term moves λ from +0.029 to +0.039 s/kg.

## Confounder handling

| Confounder | Treatment |
|---|---|
| Fuel weight | physics-constrained linear term; `λ` estimated from race, run intercept absorbs unknown start mass |
| Traffic | measured, not guessed: XY position data → track arc length → time gap to nearest car ahead |
| Track evolution | smooth term in session progress + observed `TrackTemp` |
| Driver/car | random intercept per driver |
| Cool-down / aborted laps | run segmentation + within-run relative pace filter |
| Yellow/SC/red laps | `TrackStatus != '1'` dropped |

## Validation — what we planned, and what it returned

The plan was: fit on **practice only**, predict **race** stint pace, measure error in s/lap
against three baselines — B0 stint mean, B1 naive `lap_time ~ tyre_age`, B2 naive + fuel
correction, and PITWALL with full deconfounding.

Two things came out of actually running it, and both changed the project.

**B1 ≡ B2 is an algebraic identity, not a result.** Within a race stint, `FuelKg` is exactly
affine in `TyreAge` — one lap burned is one lap of age. So within-stint RMSE *cannot*
discriminate a fuel-corrected model from a naive one; any difference is floating-point noise.
Reporting "our fuel correction improves stint RMSE" would have been reporting a tautology.
The identifying observable is the **pit-stop step**: across a stop tyre age resets and fuel
does not, so the step in pace measures the tyre effect with fuel nearly cancelled.

**Scored against that step, the deconfounded practice curve fails.** It predicts +1.52 s
against +1.26 s observed, so the average is roughly right — but the calibration slope
(regression of observed on predicted) is **+0.006**. Its stop-by-stop variation carries no
information. A saturating form does not rescue it: τ is unidentified, SSR falling 0.1% between
τ=3 and τ=44 laps.

The honest conclusion is that a defensible in-sample degradation curve can be nearly worthless
out of sample, and only a natural experiment reveals it. `src/pitwall/stopvalue.py` models the
pit-stop step directly instead: leave-one-event-out, no free constants granted to any method,
**+11.9% RMSE over the season mean at calibration 0.82**, winning 7 of 11 events.

## Real-world transfer (TrackShift 2026 brief: motorsport is the proof of concept)

The transferable principle is *recovering a degradation signal from confounded
operating conditions using a physically-constrained hierarchical model.*

Target: **Indian commercial-vehicle fleet tyre management.** A fleet operator sees
tyre wear confounded by axle load, road roughness, ambient temperature and driver
behaviour — structurally the same problem, same math. Tyre cost is one of the largest
controllable line items in Indian trucking, and tyre burst is a recognised cause of
highway fatalities. Same model, different confounders.
