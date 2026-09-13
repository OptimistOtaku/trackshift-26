# PITWALL: the measurable team advantage

Updated after the 12 September environmental rebuild. See
`PRODUCT_OPERATIONS.md` for the console, traffic-unit correction, missing data,
environmental comparison, and work remaining before stronger product claims.

The product answers: **“Where will we lose time to our rival, and what can we afford
to spend to attack?”** The degradation work establishes the confounders; the race
models turn available timing information into a forecast the engineer can use.

## What ships

- An adaptive pace estimator resets after stops and neutralisations. Robust
  gradient boosting corrects it using observed pace history, tyre state and the
  current field. The selected blend is 80% robust boosting, 20% state-space.
- A battle model forecasts cumulative relative running time over three and five
  laps against the car immediately ahead at issue time. It combines the individual
  pace forecasts with a direct model of their relative error.
  The same comparison is mirrored for the leading car to show pressure from behind.
- An attack budget subtracts the real gap, predicted relative loss, warm-up,
  traffic, extra service time and extra degradation from the expected new-tyre
  benefit. It ranks supported compounds by their worst stress margin across the
  available three/five-lap rival responses. The user supplies the actual gap and
  legal inventory. Unsupported ages, rare transitions and missing calibration
  cause abstention.
- Replay evidence and grounded engineer commentary use only the current cursor.
  Numerical facts come from models; the optional local LLM selects sentences.

## Model comparison

All experiments use cached inputs. Pace: persistence, rolling median, robust
trend, state-space, Ridge, median boosting, the previous hybrid, robust mean
boosting, deeper boosting, Extra Trees, enriched median boosting, and two blends
(plus weather, traffic, combined conditions and conditions blend: 17 approaches).
Stop models: mean, compound pair, age, state, enriched context,
stronger shrinkage, factorised old/new compounds and environment (8). Battle: constant gap,
persistence, rolling median, state-space, previous hybrid, new pace model, direct
relative model and their blend (8).

Pace and stop architectures are selected on R04–R08; the battle architecture uses
R07–R08, after three races of out-of-event pace predictions become available for
training. Selection balances events, and horizons where relevant. Architecture
is frozen for R09–R12; coefficients refit before each race on earlier events.
This is expanding chronological evaluation, **not** a random lap split.

The previous evaluation was visible during this revision. We do not describe
R09–R12 as a fresh blind holdout. No model was promoted because it looked best on
those four rounds: for example, the stop model with lowest evaluation error is
not the one selected on development data.

## Evidence

| Metric | PITWALL | Baseline | Interpretation |
|---|---:|---:|---|
| Pace RMSE, 6,831 forecasts | 0.743 s | 0.844 s | 12.0% less error than persistence |
| Pace MAE | 0.446 s | Previous model: 0.443 s | RMSE improved; MAE slightly worsened |
| Relative-time RMSE, 3,128 forecasts | 2.197 s | 2.442 s | 10.0% less error than rolling median |
| Alerts for >2 s relative loss: precision | 78.1% | 71.3% | Fewer distracting false alarms |
| Alerts for >2 s relative loss: recall | 65.9% | 66.7% | A small recall tradeoff |
| Alert AUC | 0.890 | 0.872 | Better ranking of time-loss risk |
| Threshold regret | 0.208 s | 0.259 s | 19.6% lower wrong-side threshold loss |
| Pre-stop step RMSE, 107 stops | 0.757 s | 0.761 s | 0.6% difference is too small to headline |

Threshold regret is `abs(actual_loss - 2)` on a wrong-side alert decision and zero
otherwise. It is a decision diagnostic, **not seconds saved on track**. The alert
counts are 571 true / 160 false versus 578 true / 233 false for the baseline:
73 fewer false alerts, at the cost of missing seven additional loss events.
Forecasts overlap and these are not independent racing incidents.

The relative forecast improves on its baseline in all four evaluation races.
Race-block bootstrap 95% interval for pooled RMSE improvement: **1.3–13.3%**;
threshold-regret improvement: **15.9–22.4%**. These are descriptive bootstrap
intervals from only four event blocks, not proof across all future circuits.
A fixed non-overlapping-window audit (five-lap forecasts, issue lap divisible by
five) retains 271 observations and 15.8% RMSE improvement. Cars remain correlated.
The report also includes alert thresholds of one and three seconds.

Only **3,128 / 5,117** issued relative forecasts could be scored, because the
target requires uninterrupted same-stint green running for both drivers.
Nominal 90% battle intervals achieve **88.3–88.6%** coverage. They are empirical
and slightly under-cover. Their uncertainty is shown in the product.

## What a team can do with this

Use the battle forecast to focus strategy attention before a relative pace loss
has accumulated. Evaluate a stop against the rival's predicted pace rather than
assuming equal cars. Read the remaining traffic budget before committing to an
undercut; vary response time and reject scenarios that need every assumption to
go right. The deployed output is decision support, not an autonomous pit command.

This is a tested information advantage plus a conditional planning tool. The
existing feed observes only the strategy the driver actually took. It cannot
prove the finishing position under an unchosen stop. A claim such as “our system
saves five seconds per race” requires prospective shadow operation and an
independently validated counterfactual simulator or controlled team deployment.
The earlier pit-window and overtake tests remain in the repository because they
failed; this work does not erase them or claim to have rescued those targets.

## Ninety-second demonstration

1. Open Race console: R11, NOR, lap 25 (the existing default). Show the forecast
   boundary and model errors resolved so far. The model has trained only through R10.
2. Open Strategy lab. NOR's central relative loss to PIA is about 0.16 s over five
   laps; its interval crosses zero. The system does not invent a confident call.
3. Show the compound response table. Increase rejoin traffic by one second: every
   attack budget drops by exactly one second. Explain which costs cancel when both
   cars stop, and which do not. Change inventory to remove an unavailable option.
4. Return to replay and advance the cursor. The outcome table reveals only results
   that have happened. Show another driver to demonstrate different relative risks.
5. Open Validation. Show the baseline, coverage denominator, precision/recall
   tradeoff and full development leaderboard.

Suggested pitch: “PITWALL forecasts the time we are about to lose to a rival and
prices the attack needed to respond. On four chronological evaluation races,
relative-time error fell 10%, while loss-alert precision rose from 71% to 78%.
Then we stress the attack against rival response and rejoin costs. Every forecast
can be replayed and checked against what actually happened.”

## Reproduce and audit

Run `python scripts/build_intelligence.py`, then `python scripts/serve_demo.py`.
The build runs all three benchmarks and tests. Every candidate prediction is saved
in the CSV artifacts. The pace report hashes its source replays. Unit tests poison
future observations and labels, verify pit/flag resets, check cost conservation,
compare Python/browser arithmetic, and recompute the scoreboards from saved rows.

Key files: `src/pitwall/{intelligence,decision,battle}.py`,
`scripts/benchmark_{intelligence,decision,battle}.py`, `demo_fallback/battle.js`.
The older slide deck documents the previous research story and has not been
refreshed for this revision; use this proof document and the live demo for these claims.
