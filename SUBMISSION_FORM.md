# TrackShift 2026 — updated submission answers

These answers describe the current strategy-intelligence build. The final jury
deck is `artifacts/submission/PITWALL_Jury_Final.pptx`; the portable demo is
`artifacts/submission/PITWALL_Offline_Demo.zip`. The four-chapter guided console
and six-slide browser presentation are complete. The click sequence and speaker
script are in `docs/JURY_PRESENTATION.md`. Current evidence is documented in
`docs/STRATEGY_EDGE.md` and `docs/PRODUCT_OPERATIONS.md`.

## Theme

AI Motorsport Intelligence

## Problem statement

Tyre Degradation Intelligence

## Project title

PITWALL — Opponent-Aware Tyre Strategy Intelligence

## Proposed solution and innovation

PITWALL forecasts the time a driver is about to lose to a rival, then prices the
attack needed to respond. It combines tyre and pace state with the opponent's
forecast, a team's available compounds, warm-up, pit-service differences and
rejoin traffic. The output is an attack-cost budget and a stress test across
rival response times, with uncertainty and an explicit option to abstain.

The scientific foundation separates fuel, traffic and track evolution from tyre
age. We tested that foundation against race outcomes: a plausible practice
curve did not transfer into useful stop-by-stop race predictions. That led us
to learn observable pace and relative time directly, while preserving the
confounder analysis. The product delivers decisions an engineer can inspect.

## Technologies, models and data

The cache contains 12 2026 Formula 1 events from FastF1. The unfiltered race
replay has 14,095 recorded driver laps; the separate cleaned modelling table has
14,310 practice and race laps. These are different populations.

Python, pandas, NumPy, SciPy, statsmodels and scikit-learn support the pipeline.
Seventeen pace approaches include robust state estimation, Ridge, gradient
boosting, Extra Trees, environmental ablations and ensembles. Eight pre-stop specifications explore
compound effects, age, context and shrinkage. Eight rival-forecast approaches
compare constant-gap and recent-pace baselines with direct relative modelling.
The deployed pace model blends robust boosting with state-space estimation;
the battle model adds a learned relative correction. A static HTML/JavaScript
race console works offline, with an animated circuit schematic, controls and
primary output on the left, an engineer briefing on the right, and telemetry below.
Track/air temperature, humidity, wind, rainfall, measured traffic and sensor
coverage are shown at the selected lap. The selected pace model retains its
development-selected inputs; environmental candidates are separately evaluated.
Optional local LLM commentary selects verified numerical
facts; it never generates telemetry or pit recommendations.

## Validation and effectiveness

Models train on earlier races only. Development races select architectures;
R09–R12 evaluate frozen choices with expanding earlier-event training. These
four races were inspected in a previous revision, so they are a reused
evaluation set, not a new blind test.

Pace RMSE is 0.743 seconds over 6,831 scored forecasts, 12.0% below persistence.
Relative-time RMSE is 2.197 seconds over 3,128 forecasts, 10.0% below the strongest
simple development-selected baseline, rolling-median extrapolation. Alerts for
losing more than two seconds achieve 78.1% precision versus 71.3%, with recall
of 65.9% versus 66.7%. That is 73 fewer false alerts at the cost of missing seven
additional positive cases. Overlapping forecasts are correlated.

Race-block bootstrap, event breakdowns, interval coverage, exclusions and a
non-overlapping-window audit are published. Only 3,128 of 5,117 issued relative
forecasts are scoreable because stops or neutralisations interrupt continuation.
Battle intervals cover about 88% at nominal 90%.

The evidence demonstrates a forecasting and alert-quality advantage. Attack
budgets remain conditional on supplied costs and rival response. We do not
claim measured positions gained or seconds saved under an unobserved strategy.
The pre-stop model's 0.6% RMSE advantage over the mean is too small to support
that claim. A prospective team trial is needed for realized race benefit.

## Demo

Run `python scripts/serve_demo.py --port 8001`, open
`http://127.0.0.1:8001/demo_fallback/`, and click **Present to jury**. Show tyre
science, advance a locked forecast to its target, stress the undercut with
traffic, then show all benchmark results. **Pitch deck** opens the browser slides.
Reproduce the models with
`python scripts/build_intelligence.py`.
