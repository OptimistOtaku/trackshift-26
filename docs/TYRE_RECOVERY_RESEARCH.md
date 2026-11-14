# Tyre-reset response research — 13 September 2026

The largest evidence gap is tyre-specific recovery, rather than general lap
forecasting. This revision adds a measured response study and a live personal
stint reference. It does not establish physical wear or more accurate stop calls.

## Data and target

The corrected, unfiltered race replays provide weather, missing-aware traffic,
tyre age, compound and lap-completion timestamps. The older cleaned season table
is not used here. Its historical practice/traffic research is not silently
relabelled as refreshed evidence.

An eligible stop has three consecutive green laps before the in-lap and three
after the out-lap, with a tyre-age reset. Pit and out-lap costs are excluded.
No fastest-lap selection or retrospective whole-stint cleaning is used. The
173 eligible stops include 166 with at least three continuous stay-out controls.
Up to five controls are matched on pre-stop mean pace and trend. Their median
pace change is subtracted from the stopped car's pace change.

Control eligibility is retrospective. A result unlocks only after all recorded
source windows used in control selection have arrived, including unselected
candidates. Thus a slower, later-arriving candidate cannot change an already
revealed result. This is a recorded-data protocol, not a live retirement feed.

For same-compound resets, the 30 matched stops across six events show mean
relative recovery **1.5976 s/lap**, with event-bootstrap 95% interval
**1.2262–2.1190 s/lap**. These are descriptive observational results, not a
causal treatment effect or the benefit expected at every stop.

## Negative control

A second equally spaced before/after comparison lies entirely before the real
stop, on the old tyres. It independently matches controls using that earlier
pre-window. On the 28 same-compound stops with both comparisons:

| Measurement | Mean s/lap |
|---|---:|
| Actual matched reset recovery | 1.6525 |
| Pre-stop no-change placebo | -0.2866 |
| Reset recovery minus placebo | 1.9392 |

The placebo is **not centred at zero**: its event-bootstrap interval is
-0.4803 to -0.0929. This warns against claiming complete confounder removal.
The difference interval is 1.5594–2.6906, across just five events. Stops are
nonrandom, controls also age, and fuel load, tyre temperature, setup, driver
behaviour and traffic changes are not fully separated.

## Model challenge

Thirty configurations per target combine ten model specifications with three
within-event adaptation settings. Candidates include fixed-knot age curves,
ridge, Huber regression, forests, extra trees, weather/traffic inputs and personal
early-stint pace references. Base models train on earlier races; event adaptation
uses only fully resolved stops and clips one incident's residual influence.
Evaluation errors are not clipped.

R04–R08 equal-event development error selects a specification before scoring
R09–R12. This is exploratory research on reused races. Initial results were
examined before adding personal stint references; `initial_report.json` and
`initial_selection.json` retain that first iteration. This is not a blind test.

| Target, 68 evaluation stops | Selected model RMSE | Historical mean RMSE |
|---|---:|---:|
| Raw stop recovery | 0.7354 s | 0.7220 s |
| Recovery relative to controls | 0.8118 s | 0.7927 s |

The new models do not beat the historical mean. They remain research artifacts
and are **not promoted into strategy calls**. Reporting their improvement over
only the weaker adaptive baseline would obscure this result. The existing
deployed stop model retains its separate, weak incremental evidence and wider
intervals. No comparison between different targets is an accuracy improvement.

## Product integration

“Inspect tyre response” opens the new panel directly below the race console:

- Personal field-relative stint drift updates with the driver's timestamped
  observations. It compares the last three available observations with the first
  three in the stint, whose reference age is displayed. This is a pace warning,
  not an isolated wear rate. Missing/stale/pit observations suspend the signal.
- A selector exposes only resolved real stops. Each shows before/after pace,
  named stay-out controls, traffic exposure and the pre-stop placebo.
- Archive evidence and the complete model comparison are available inside the
  product. Archive statistics are labelled as retrospective research.

Reproduce with `python scripts/benchmark_recovery.py`, then
`python scripts/export_recovery_evidence.py`. Both are included in the complete
`scripts/build_intelligence.py` workflow. Sources and prediction CSVs live in
`artifacts/demo/recovery/` and `artifacts/recovery_*_2026.csv`.

The category story is stronger: tyre-age resets leave an inspectable pace
response beyond common field movement. The unresolved step is reliable
individual pre-stop recovery prediction, plus independent physical tyre labels.
