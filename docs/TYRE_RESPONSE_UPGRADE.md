# Tyre-response upgrade — 13 September 2026

The deployed stop-response model now predicts observed clean-lap recovery with
**0.671706 s RMSE**, versus **0.764444 s** for the previous architecture and
**0.761195 s** for the historical mean on the same 107 supported stops.
That is **12.13% less error than the previous model** and **11.76% less than mean**.
These are error reductions, not a percentage of accurate predictions or tyre wear.

## What changed

A strongly regularized ridge model combines a saturating tyre-age basis,
old/requested compound, recent pace state, race progress, track temperature,
observed traffic and age/temperature interactions. Normalizing recovery by
pre-stop pace helps transfer across circuits. Missing sensors have explicit flags.
Temperature and observed traffic now enter the tyre-response estimate directly.
The separate continuation lap-pace model is unchanged; it does not directly use
these sensor features. Actual fuel, tyre core temperature and pressure remain absent.

The same timestamped response drives compound comparisons, clean-lap scenarios,
stop-cost recovery and undercut arithmetic. Rejoin positions use aligned rival
lap forecasts and pit loss; extra future traffic and new-set decay remain explicit
engineer assumptions. The console shows current inputs, regression contributions,
intervals and narrower transition-age extrapolation warnings.

## Selection and evidence

Twenty-two declared configurations per target were compared on R04–R08 using
equal-event mean squared error. Only the selected challenger and two baselines
were then evaluated on R09–R12. Coefficients and interval calibration use earlier
races only. All these races were inspected in earlier work: this is a bounded,
exploratory research iteration, not a fresh blind test.

| Separately evaluated target | Stops | Selected RMSE | Mean RMSE | Previous architecture RMSE |
|---|---:|---:|---:|---:|
| Deployed cleaned stop recovery | 107 | 0.671706 s | 0.761195 s | 0.764444 s |
| Strict three-before/three-after recovery | 68 | 0.635937 s | 0.721965 s | 0.623047 s |
| Recovery relative to stay-out controls | 68 | 0.752083 s | 0.792680 s | 0.772649 s |

The deployed model beats mean in three of four evaluation races. Its event-bootstrap
95% improvement interval is **−0.0358% to 21.7501%**, narrowly including zero.
The separate control-adjusted study improves **5.12%** over mean in all four races,
with interval **1.4280% to 17.9251%**, but only 68 stops. It is not the deployed target.
The strict raw challenger does not beat the earlier architecture on that target.
No target is pooled with another or relabelled as physical wear.

Main stop-response intervals cover all scored outcomes but are wide: 100% observed
coverage is not 100% accuracy. Observational recovery still includes residual fuel,
driver, setup and stop-selection effects. Physical wear, remaining tyre life,
guaranteed compound superiority and realized positions gained remain unvalidated.

## Reproduce

Run from the repository root with existing local dependencies and cached data:

```text
python scripts/challenge_tyre_response.py
python scripts/export_tyre_response.py
python -m unittest discover -s tests -v
```

The full build runs the old audit first, then the challenge and final export.
Running only `benchmark_clock_decision.py` restores old model artifacts; run the
exporter afterwards to retain this upgrade. Source results and per-stop predictions
are in `artifacts/demo/tyre-challenge/`; deployed metrics and earlier-race model
coefficients are in `artifacts/demo/decision-clock/`.

Verification: 47 Python tests passed, including source-time isolation, development
selection, metric recomputation, exported-coefficient reconstruction and unsupported
transition abstention. The suite also invokes the JavaScript strategy contracts.
After the final UI changes, 18 focused JavaScript contracts and syntax checks
passed. In the running browser, adding 2s of future traffic reduced NOR's
conditional PIA margin from 4.51s to 2.51s with the 1.85s tyre response unchanged.
The current narrow layout has no horizontal overflow or browser errors. Versioned
data requests prevent stale model exports from mixing with updated interface code.
