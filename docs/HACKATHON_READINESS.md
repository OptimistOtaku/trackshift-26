# PITWALL — readiness review, 12 September 2026

**Latest tyre-response update:** the deployed model now scores 0.6717s RMSE
versus 0.7644s previously and 0.7612s for mean on 107 reused stops. Temperature
and observed traffic are now actual stop-response inputs. The pace model below
remains separate and unchanged. See [current evidence](TYRE_RESPONSE_UPGRADE.md);
older no-uplift stop-model findings below are historical, not current results.

**13 September update:** the primary pace forecast now has an exact-timestamp
model and audit: 0.746s RMSE vs 0.844s persistence, 11.6% lower error, on 6,831
scored forecasts. The circuit uses recorded position telemetry. See the current
[category assessment and limitations](CATEGORY_ASSESSMENT.md); the review below
documents the preceding lap-synchronous revision.

PITWALL is a credible hackathon prototype with a working race console and a
measured forecasting advantage. It is not yet a validated autonomous race-strategy
product. There is no defensible percentage chance of winning without the judging
rubric and competing submissions. The most important remaining gap is proving
that better information leads to better decisions, while keeping the entry tied
to the requested tyre-degradation problem.

## Our strongest points

1. **A scientific distinction that matters.** Lap-time slope is not tyre wear:
   fuel burn, weather, traffic and track evolution can conceal the tyre effect.
   The project investigates those confounders and records failed transfer tests.
   Show the tyre-science view, but describe its curves as research, not a portable
   physical wear sensor. The historical research artifacts predate the latest
   replay traffic corrections and need separate regeneration before new claims.
2. **A reproducible information advantage.** The deployed pace model has 0.743 s
   RMSE versus 0.844 s for persistence on 6,831 forecasts: 12.0% lower error.
   Relative-time RMSE is 2.197 s versus 2.442 s, a 10.0% improvement. Two-second
   loss alerts have 78.1% precision versus 71.3%, with 65.9% versus 66.7% recall.
   These four evaluation races were already inspected; they are not a blind test.
3. **An engineer can inspect the arithmetic.** Rival response, compound inventory,
   warm-up, rejoin traffic and service delay all enter a transparent attack budget.
   Unsupported scenarios abstain. A positive scenario margin is not a promised pass.
4. **The product tells one coherent story.** Select race and driver, run the circuit
   replay, inspect the forecast and briefing, then scroll into sensor context and
   resolved forecast evidence. It runs from local files with no cloud dependency.

## What was completed in this revision

- Motorsport console: controls and primary output on the left, animated circuit
  in the centre, grounded race engineer on the right, detailed telemetry below.
- Play/pause, speed, lap stepping, driver selection, race selection and timing-row
  selection use the same cursor. The car movement is explicitly schematic;
  circuit geometry comes from validated pre-race telemetry. It is not a vehicle
  physics simulator or synchronized live GPS feed.
- Track/air temperature, humidity, wind, rainfall, sensor age, measured dirty-air
  exposure, median forward-gap estimate and traffic sample coverage are visible.
- Fixed FastF1 XY decimetres being interpreted as metres by the off-line filter.
  Rejected discontinuous reference geometry and traffic with less than 50% lap
  sample coverage. China has no reliable cached pre-race geometry, so its traffic
  and circuit are unavailable rather than fabricated. Monaco coverage is sparse.
- Weather is the last sample at or before lap completion, at most 180 seconds old.
  Position resampling holds past samples only. Missing telemetry has explicit
  indicators. Temperature and traffic interactions with tyre age are compared.
- Seventeen pace candidates, eight stop-model specifications, eight rival models;
  chronological rebuild, source hashes and 25 passing regression/contract tests.

## Did temperature and traffic improve the model?

| Pace candidate | Development MSE, equal event/horizon | Reused evaluation RMSE |
|---|---:|---:|
| Deployed pace/state blend | 0.6944 | 0.7428 s |
| Pace-only robust mean | 0.7176 | 0.7376 s |
| Add weather | 0.7149 | 0.7458 s |
| Add measured traffic | 0.7192 | 0.7337 s |
| Add weather and traffic | 0.7061 | 0.7444 s |
| Conditions/pace blend | 0.6982 | 0.7337 s |

The conditions blend is promising, but the deployed model won the prespecified
development selection. Promoting another model because of these evaluation
numbers would tune on the evaluation set. The console uses environmental data as
measured context; **the current selected pace model does not directly consume
the new weather/traffic features**. All candidates and feature wiring are retained
for a genuinely new evaluation. Weather coverage is 100% and traffic coverage
83.2% of issued forecast requests; this is not a claim of sensor coverage for all
race time. The stop model with environmental terms did worse: 0.801 s versus
0.757 s for the selected stop model and 0.761 s for its mean baseline.

## What still prevents stronger accuracy claims

| Missing or limited factor | Current treatment | What would close the gap |
|---|---|---|
| Tyre carcass/surface temperature and pressure | Explicitly unavailable; track temperature is distinct | Team sensor channels, timestamp alignment and thermal-state validation |
| Actual fuel load and burn rate | Historical fuel identification; current pace/progress proxies | Team fuel estimates, burn maps and uncertainty |
| Driving style, energy deployment, DRS and mistakes | Some effects absorbed in recent observed pace | Causal car-telemetry export and a new ablation |
| Setup, downforce, loads, compound construction, tyre history | Compound/age and local pace proxies | Setup and tyre-set records; race-to-race compound normalization |
| Traffic measurement quality | Past-position projection, coverage gate; lap-average speed approximates time gap | Better geometry/position alignment, exact timing gaps, compare to an independent source |
| Rejoin traffic and pit warm-up | Engineer-entered scenario costs | Pit exit timing, tyre preparation and rival trajectory data |
| Rain, safety cars and strategy interruptions | Green same-stint forecasting; resets at interruptions | Separate validated regimes and explicit scenario probabilities |
| Direct true-wear identification | Research curves; no reliable race transfer established | Independent tyre measurements or a better natural-experiment design |
| Actual benefit of a different strategy | Not identifiable from the observed action alone | Prospective shadow trial and independently validated counterfactual simulation |

Adding arbitrary constants for these missing factors would make the display more
confident without making it more accurate. Track temperature alone cannot diagnose
overheating, graining, blistering, puncture risk or remaining physical tyre life.

## Submission deliverables completed

The earlier multi-day presentation estimate is superseded by the completed
deliverables: an informative five-view centre console, a four-chapter guided jury
walkthrough, a forecast lock-and-reveal with baseline scoring, a traffic-sensitive
undercut breakdown, the six-slide browser presentation, an editable final PPTX,
an offline demo ZIP and a 90-second script. See `docs/JURY_PRESENTATION.md`.
The live walkthrough replaces the need for a prerecorded video in this package.

The remaining limits are validation and event requirements, not unfinished
presentation features:

1. Match the official rubric and submission format. If pure wear identification
   is primary, lead with the science view and explain race decision support as
   the extension. A lap predictor is not a physical wear estimator.
2. Freeze the models and test additional unseen races or a held-out season. Report
   event-level error, uncertainty coverage and sensor dropout. This depends on
   obtaining suitable data; do not promise an immediate accuracy increase.
3. Run a small blinded engineer usability exercise: can users identify a developing
   pace threat and reject a fragile attack faster than with a timing table? Publish
   the method and results, including failures. This can demonstrate product value
   without inventing on-track places gained.

**For an operational racing product: several weeks of engineering plus access to
team data and prospective validation.** Needs a real timestamped ingestion service,
latency and stale-feed handling, persistent audit logs, deployment monitoring,
team workflow integration, legal tyre inventory, and validation under interruptions.
Public replay data alone cannot complete those requirements.

## A defensible 90-second demo

1. Race console, R11 / NOR / lap 25: show tyre age, forecast range, measured track
   temperature and traffic. Press Play and identify the historical replay boundary.
2. Scroll to the pace chart: explain why observed pace is not pure degradation.
3. Open Strategy lab: explain the rival forecast, then add one second of rejoin
   traffic. Every attack margin loses exactly one second; uncertain cases stay uncertain.
4. Model evidence: show the baseline, interval coverage, all candidates and the
   environmental ablation. Explain why the tempting 0.734 s candidate was not
   promoted based on a reused evaluation set.
5. Finish: “We make tyre-related pace risk visible, test the cost of responding,
   and give the engineer an auditable decision aid.” Do not claim an optimal pit
   lap, physical tyre life, places won or a validated autonomous pit command.

## Reproduce

```bash
python scripts/export_conditions.py  # uses the existing offline FastF1 cache
python scripts/build_intelligence.py # three benchmarks and regression tests
python scripts/serve_demo.py --port 8001
```

Open http://127.0.0.1:8001/demo_fallback/. Current evidence lives in
`artifacts/demo/intelligence/{report,decision_report,battle_report}.json`.
