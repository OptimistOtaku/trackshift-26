# TrackShift 2026 — submission form answers

Copy-paste each block into the matching field. Deck to upload:
`artifacts/PITWALL_TrackShift2026.pptx` (12 slides, team: Handsome Squidward — Aditya, Ruhani).

---

## Theme
AI Motorsport Intelligence

## Problem Statement
Tyre Degradation Intelligence

## Project Title
PITWALL — Tyre Degradation Intelligence from Confounded Race Data

---

## Describe your proposed solution and what makes it innovative.

Every tyre model starts by fitting lap time against tyre age and calling the slope "degradation." On real 2026 F1 data that model is not just noisy — it is backwards: it reports HARD tyres getting faster as they wear, because inside a single run fuel burns off at exactly the rate tyre age climbs, so the naive slope measures the difference of two effects rather than wear. PITWALL first removes the confounders the brief names — fuel, traffic, track evolution — using a physically-constrained two-stage model, and that alone flips every compound to a sensible positive number.

The innovation is what we did next. Instead of trusting that deconfounded practice curve, we tested whether it predicts an actual race — and it does not (calibration slope 0.006; right on average, uncorrelated stop-by-stop). Most teams will report the in-sample curve and stop there. We treat the pit stop as a natural experiment — the one moment where tyre age resets but fuel does not — and model the decision an engineer actually makes: the seconds per lap a fresh tyre buys. That quantity is learned directly from 288 real stops and, unlike the curve, it holds up out of sample. The headline finding is honest and non-obvious: degradation accumulates for ~20 laps and then stops, so a curve that keeps climbing systematically over-values a late stop.

---

## What technologies, AI/ML models, tools, and datasets do you plan to use?

Data: the full 2026 F1 season via the FastF1 telemetry API — 14,310 laps across 12 events and 1,068 practice/race runs, including per-lap timing, tyre compound/age, and 4–10 Hz car position telemetry. Stack: Python, pandas/NumPy, statsmodels, SciPy, matplotlib.

Models & methods: a two-stage hierarchical estimator (fuel sensitivity λ identified from race data where fuel and tyre age are not collinear, then imported into practice fits); track evolution entered as log1p(weekend laps) — identified precisely because the log saturates; traffic measured from position telemetry via a KD-tree projection onto the racing-line centreline (not inferred); ~1,100 run fixed effects absorbed analytically by Frisch–Waugh–Lovell demeaning; cluster-robust standard errors; and a profile-likelihood test of the saturating degradation form. The deployed predictor is a deliberately interpretable regression (compound pair + track temperature + traffic) — we chose an identified causal model over a black box because the output must be an effect an engineer can act on, not just a fit.

---

## How will you validate your solution's performance, feasibility, and effectiveness?

Ground truth is a natural experiment, not the model's own fit. Across a pit stop tyre age resets while fuel barely changes, so the step in pace measures the tyre effect directly. We validate against 288 such stops with leave-one-event-out cross-validation, granting no method a free constant — the model must get the level right, not merely the shape. Metric: RMSE in s/lap of predicted vs observed stop value.

Result: PITWALL beats the season-mean baseline by +11.1% RMSE at a calibration slope of 0.79 (1.0 = magnitudes correct), and wins 7 of 11 held-out events. It is robust to method-blind outlier caps (+9.6–11.1% across all cuts). Fitted effects are individually significant with event-clustered SEs (track temp +0.039 s/°C, p<0.001; traffic +0.50 s, p=0.003). We also run falsification checks (the traffic measure rises monotonically from P1–3 to P16–20, as it must) and state our limits plainly: the pooled gain is carried by larger events, and track temperature partly proxies circuit identity across only 12 events.

---

## Upload your Idea Submission Presentation (PPT/PDF)
Upload: artifacts/PITWALL_TrackShift2026.pptx   (12 slides)

## Live demo video link (if any)
Optional — leave blank, or add later if you record a walkthrough.
