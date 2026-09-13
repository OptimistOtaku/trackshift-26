# Tyre Degradation Intelligence — category assessment

Assessment: 13 September 2026. This is an engineering judgment, not a prediction
of judging outcomes. The full official rubric and competitors were not available.

PITWALL is a credible contender with a strong working demonstration and measurable
forecasting evidence. Its strongest story is tyre-related pace intelligence that
helps an engineer inspect a stop. Its weakest claim would be a physical tyre-life
sensor or an optimal autonomous race strategist.

## Gap closed in this revision

**Live integration:** the main circuit, pinned forecasts, stop scenarios and
undercut view now share driver timestamps. An automatic on-track audit reveals
actual lap results as the replay advances. Speed-driven reconstruction removes
freezes from repeated XY samples and prevents off-track interpolation chords.
The current tyre-response upgrade also reduces error: **0.6717s RMSE versus
0.7644s previously and 0.7612s for mean**, on the same 107 stops. It now uses
temperature and observed traffic as actual model inputs. That is 12.13% less
error than the previous model. The main gain interval narrowly includes zero;
this is exploratory evidence on reused races, not a new blind result.
See [TYRE_RESPONSE_UPGRADE.md](TYRE_RESPONSE_UPGRADE.md).

**New tyre-specific research:** 166 matched real stops now support an inspectable
tyre-reset response study. Thirty same-compound stops show 1.60 s/lap average
recovery relative to stay-out controls. A nonzero pre-stop placebo exposes
remaining confounding. The console includes live personal stint drift and
timestamp-unlocked before/after evidence with traffic context. This strengthens
category fit. Earlier predictive candidates failed and were not promoted; the
new bounded challenge now improves control-adjusted recovery RMSE by 5.12% over
mean on 68 stops. This separate research target is not deployed as physical wear.
See [earlier research](TYRE_RECOVERY_RESEARCH.md) and the upgrade above.

The primary pace forecast now uses individual driver completion timestamps.
It no longer waits for the entire field to complete the same numbered lap.
Features only contain observations available at issue time, including the latest
received field observations. The previously chosen mean/state architecture was
kept fixed. Training and interval calibration use earlier races only.

On the same reused R09–R12 evaluation:

| Exact-timestamp audit | Result |
|---|---:|
| Pace RMSE | 0.745595 s |
| Persistence RMSE | 0.843650 s |
| Reduction in RMSE | 11.6227% |
| Scored / issued forecasts | 6,831 / 9,062 |
| Empirical coverage at nominal 90% | 92.5487% |
| Scored targets at/before issue | 0 |
| Event-bootstrap improvement interval | 8.7445–15.4140% |

The narrower claim is now demonstrated: a forecasting advantage survives a
timestamp-causal protocol. This is still recorded replay, not an external live
feed, measured live-service latency or a new blind dataset. The older 12% result
belongs to the archived lap-synchronous model. Use 11.6% for the primary clock model.

The primary forecast, three horizons, driver briefing and outcome score follow
the position clock. Outcomes are revealed only when their target timestamp has
passed. Pit/neutralised/stale timing suspends the model. Strategy and learned
rival scenarios also use the driver clock; historical research views retain
their labelled lap-synchronous analysis state.

## Where we stand

| Dimension | Assessment | What matters in judging |
|---|---|---|
| Working product | Strong prototype | Show the jury changing driver, replay time, compound and traffic themselves. |
| Forecast evidence | Defensible, preliminary | Show baseline, all scored predictions, coverage and exclusions; disclose reused races. |
| Fit to tyre-degradation category | Credible but vulnerable | Lead with confounder separation and tyre-related pace cost. Explain why pace is not wear. |
| Fresh-tyre value | Improved, preliminary evidence | 11.76% less RMSE than mean on 107 reused stops; wide intervals still limit confident compound or pit claims. |
| Undercut/rejoin decisions | Transparent conditional scenarios | Inputs and uncertainty are inspectable; realized advantage under another strategy is unproven. |
| Operational deployment | Prototype | External feed integration, timing/latency monitoring and prospective validation remain. |

We should be competitive if the rubric rewards a working decision-support product,
validation and explainability. A team with independently validated physical wear
or remaining-life estimates could beat us on a rubric focused tightly on those
targets. Interface polish cannot remove that scientific difference.

## Highest-value actions before evaluation

1. Keep the pitch on one problem: “How much pace is tyre-related, what could fresh
   rubber recover, and does traffic make the response worthwhile?” Show the
   scientific limitation before the jury has to expose it.
2. Demonstrate one complete action chain in the app: clock forecast → actual
   outcome → same-compound pace proxy → compound comparison → rejoin queue →
   traffic stress → named rival margin. Let the jury change one input.
3. Use the aggregate timestamp audit as the main accuracy evidence. A good single
   lap is a demonstration of verification, not proof of general accuracy.
4. Rehearse three failure cases: unavailable geometry, a pit/neutralised lap and
   an unsupported compound. Correct abstention is evidence of engineering quality.
5. Match the official PS wording as soon as it is available. Do not headline a
   claim about physical wear if the only validation is lap-time prediction.

## What cannot be closed honestly from these files

- Physical wear and remaining tyre life need an independent target: tyre scans,
  tread/mass measurements or team thermal/pressure channels with an explicit
  validated relationship to wear. Adding a guessed wear percentage is not a bridge.
- Optimal full-race pit strategy needs a validated simulator, tyre-set constraints,
  rival-response assumptions and prospective or independently evaluated decisions.
  The current four-entry comparison is a conditional planning feature.
- Measured race benefit needs a shadow trial or other defensible counterfactual
  study. Observing the one strategy actually taken cannot establish positions won
  by an unchosen stop.
- Generalization needs untouched races or a season withheld before model choice.
  Re-splitting already examined data does not create a new blind evaluation.

Source: `artifacts/demo/clock/report.json`. Rebuild with
`python scripts/benchmark_clock.py`; complete model build also runs this audit.
