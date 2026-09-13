# PITWALL control panel — 13 September 2026

**Current tyre-response model:** 0.671706s RMSE versus 0.764444s for the previous
model and 0.761195s for mean on the same 107 stops: 12.13% and 11.76% lower error,
respectively. Track temperature and observed traffic now enter the stop-response
model alongside tyre age, compounds and pace state. The console exposes those
inputs and uses that response throughout compound and undercut scenarios.
This is new research on reused races; the main event-bootstrap gain interval
narrowly includes zero. See [selection, evidence and reproduction](TYRE_RESPONSE_UPGRADE.md).

**Live accuracy comparison (current):** Circuit, Forecast and Deep Telemetry
now show paired predicted-versus-observed next-lap traces. Blue is the model
prediction issued before its target; white is the observed target lap, revealed
only after its completion timestamp. Thin vertical connectors show error.
The next issued prediction is a hollow blue point marked awaiting actual.
The view scrolls with the race clock and draws the newly received observation
with a brief reveal animation (disabled for reduced-motion users).
A prominent readout shows the latest paired prediction, actual and absolute
error, alongside cumulative driver RMSE and persistence RMSE. No unrelated
lap's prediction is matched against the observation. Pit/interrupted targets
remain gaps. Audit locks do not freeze the live comparison.
**Watch comparison 10×** advances both race and chart at demo speed; **Real time
1×** returns both to recorded race speed. The current main graph emphasizes
accuracy comparison; future horizon intervals remain in the forecast readouts.

**Earlier forecast visibility and tyre-tab update:** The adaptive chart has its own
Play/Pause, Real time 1× and Demo 10× controls; these operate the shared race
clock, not a separate chart timer. A moving cursor shows elapsed time divided
by the issued lap duration, explicitly an estimated clock position, not GPS.
The numerical forecast remains fixed between received laps. Pit/out-laps,
neutralisation, stale timing and new-stint warm-up have distinct explanations.
Warm-up displays the number of representative observations out of the required
three. For R11 NOR, L41/L42 show 1/3 and 2/3; the model resumes at L43.
The selected car trail is four seconds of reconstructed past movement.
Navigation uses soft-red, medium-yellow and hard-white tyre rings as styling;
these tabs do not select the strategy compound.

**Adaptive forecast and workflow update:** The circuit now includes a rolling
adaptive chart, mirrored in Forecast and Deep Telemetry. All three read the
selected driver's received lap timestamps, rather than the older field-lap
cursor. White traces are observed clean laps, blue dots are historical issued
next-lap predictions, lime is the current forecast with its empirical 90% band,
and amber marks the audit lock. The clock and elapsed-time indicator advance
between observations; forecast numbers refresh only when timing arrives.

**Lock next lap for audit** keeps the original number while the live chart,
cars and strategy continue. **Audit +3 / +5 laps** opens the longer-horizon
witness. Changing the horizon selector does not erase an existing lock;
**Replace audit lock** explicitly replaces it, and **Release lock** clears it.
Actuals and errors remain hidden until target completion. A lock in another
driver/race/time context is identified rather than scored in the wrong context.

The numbered workflow links tyre condition → forecast pace → plan the stop →
rejoin and attack. Tyre age is the recorded age of the set (including prior use),
not a guessed wear percentage. Compound and cost controls feed the same live
calculation throughout. The rejoin order shows our car between the nearest
covered rivals, with conditional timing gaps and coverage. These changes improve
clock consistency and usability; they do not establish new model accuracy.

**Live console integration:** **Run live evaluation** starts the recorded
race at 1×, expands the centre console and enables looping. The on-track audit
shows each frozen next-lap prediction beside the arriving actual result and
persistence error. **Pin this forecast** preserves one horizon for inspection;
it does not change the model. **Run replay & verify** lets its result arrive
naturally rather than skipping the race forward.

The main stop/rejoin and centre undercut views now consume individual driver
timestamps, using `decision-clock/` with `clock/`. The visible chain is actual
tyre age / pace trend → continuation forecast → modelled stop recovery → clean-lap
scenario → rival margin. Field-relative stint drift remains a separate warning;
it is not added again as a second tyre gain. Changing traffic or compound changes
the shared calculation. Rivals' forecasts are integrated to a common future lap
so cars on different last-completed laps are aligned. Deeper legacy research
screens retain their labelled historical protocols.

The motion layer reconstructs a continuous path from recorded speed, bounded
position corrections and measured circuit geometry. Repeated XY coordinates no
longer freeze the car; implausible jumps cannot draw a chord across the circuit.
It uses a one-second display buffer and only received samples. Gaps with
overlapping reconstruction uncertainty are unresolved. **This is reconstructed
replay motion, not exact GPS.** Strategy uses timing observations, not animation
coordinates. Source files are preserved.

The earlier frozen stop architecture scored 0.7644s RMSE versus 0.7612s for mean.
The current replacement scores **0.6717s** on the same 107 stops. Uncertainty
remains visible. Primary pace evidence remains 0.7456s versus 0.8437s persistence.
Rebuild the current stop export with `python scripts/challenge_tyre_response.py`
then `python scripts/export_tyre_response.py`; the complete build runs both.

**Tyre-response update:** use **Inspect tyre response** in the driver controls.
The new panel shows field-relative drift against a personal early-stint reference,
then actual completed stop recovery with named stay-out controls and traffic
before/after. Results unlock only after all control-selection source windows
resolve. Expand **Tyre-specific evidence and model challenge** for the archive
study, current three-target comparison and earlier unsuccessful candidates.
See `TYRE_RESPONSE_UPGRADE.md`; `TYRE_RECOVERY_RESEARCH.md` preserves earlier work.

**Timestamp-model update:** the primary forecast, Circuit horizons and driver
briefing now follow each driver's lap-completion timestamp. The new audit gives
0.746s RMSE versus 0.844s persistence (11.6% lower), with 92.5% empirical interval
coverage. This closes the pace model's field-completion delay. Main strategy and rejoin calculations also use the driver clock. Separate
legacy research screens retain their explicitly labelled historical protocols.
See `CATEGORY_ASSESSMENT.md` and `artifacts/demo/clock/report.json`.

Start: `python scripts/serve_demo.py --port 8001`.
Open http://127.0.0.1:8001/demo_fallback/.
No account, model download, npm install or cloud service is required to use the
exported product. The local engineer has a deterministic fallback.

## Product workflow

1. Choose the event and driver. **Focus console** gives the circuit more space.
   **Play** advances timestamped cached positions at 1×, 10× or 30×. Car labels,
   speed, gear, throttle, braking and estimated physical gap share that clock.
   Click a car to select its driver. Pausing stops both the clock and the cars.
2. Read the left-side recoverable same-compound pace estimate and three forecast
   horizons. This is a predicted pace change across a stop, not a measured wear
   percentage. Residual fuel and traffic effects are not completely identified.
3. **Plan stop & rejoin** jumps to the connected strategy panel. It compares
   supported compounds, shows their uncertainty, estimates nominal stop-cost
   recovery, and identifies the cars either side of the projected rejoin.
4. Confirm available sets. Pit loss defaults to the median of at least three
   measurable stops already completed at the analysis lap. It includes out-lap
   warm-up. If support is insufficient, the displayed 22s value is explicitly a
   planning assumption. An override remains in effect until **Use observed pit loss**.
5. Adjust extra rejoin loss and new-tyre decay. Inspect four entry scenarios.
   Ranking first avoids a projected gap below 2.5s, then favours greater five-lap
   benefit. This is a short-horizon scenario comparison, not optimal race strategy.
6. Read named undercut targets. **Load these inputs into undercut calculator**
   transfers the measured timing-line gap and the chosen compound/costs. It assumes
   equal service and warm-up for the two stops. Change those assumptions in Strategy lab.
7. Expand **Where do the rival forecast numbers come from?** for the live arithmetic
   and model source. Forecast and Results views retain the verification workflow.

## Clock and measurement contract

- `artifacts/demo/motion/R*.json` contains one-second samples from the cached
  FastF1 race position/car channels. Each sample uses the latest source value at
  or before its timestamp. Positions interpolate with a one-second display delay;
  both endpoints have already arrived at the displayed clock. A source older than
  2.5s is hidden. No rank-spaced positions or decorative lap clock are used.
- Physical forward gap is projected centreline distance divided by current speed.
  This is an approximation, not official timing. Overlapping samples or separation
  below the geometry resolution are reported as unresolved, never as zero gap.
  Off-circuit/pit samples are omitted from on-track traffic. Missing geometry
  disables position/gap display. Sparse Monaco coverage remains sparse.
- The main forecast and strategy use each driver's received completion timestamp.
  Older research screens retain their labelled field-completed analysis cursor.
  Numerical estimates update when representative lap observations arrive, not
  every animation frame. The product replays precomputed timestamped outputs;
  it is not connected to an external live F1 service.
- Weather and lap-average traffic in the analysis panel are measured context at
  that analysis lap. The physical-gap ticker is a separate timestamped estimate.

## Strategy arithmetic and boundaries

Same-compound pace recovery comes from the pre-stop model trained on earlier
races. Its aggregate RMSE is 11.76% lower than mean on reused evaluation stops;
broad uncertainty remains visible. It is not a causal physical-wear measurement.

Observed pit cost = in-lap + out-lap minus the medians of two preceding and three
following green non-pit laps, all already completed. Values outside 10–40s are
excluded from this typical-stop estimate. Failures/slow stops require an override.

Main-console rejoin adds full pit loss to continuation forecasts integrated to
a common timing line. Future entry projections compare integrated lap forecasts;
unsupported cars are excluded from the reported covered field.
Pit/neutralised cars are excluded, and coverage is displayed. Traffic, future
stops, overtaking and lapped traffic are not fully simulated. The result names
projected neighbours, not a guaranteed position.

The after-both-stops attack margin is `3 × tyre step − relative time loss − gap
− extra traffic − 3 × extra decay`. Equal pit loss and warm-up cancel; uncertainty
adds the shared tyre-step radius across all three laps plus the relative radius.
The undercut calculator allows different service/warm-up assumptions explicitly.

The main-console rival forecast uses each driver's available lap forecasts,
integrated to a common target lap. The separate historical battle model uses
integrated self/rival lap forecasts plus a learned relative correction. It uses both
drivers' recent pace, trend, spread, tyre age/compound, field-relative pace and
race progress. Adjacent-rival selection is made at issue. For other named targets,
the product labels the calculation as integrated pace forecasts without a learned
relative correction. Measured gap and forecast relative loss are different inputs.

## Rebuild and verify

`python scripts/export_motion.py` refreshes all position/car exports using the
existing offline cache. `--rounds 11` refreshes one race. It changes no model fit.

`python -m unittest discover -s tests -v` includes Node contracts for delayed
position interpolation, stale data, unresolved overlapping positions, pit-loss
causality, inventory abstention, future-data isolation, shared-cost cancellation
and traffic/decay accounting.

The current tyre-response improvement is documented separately from interface
polish. Physical tyre life, optimal full-race pit lap, realized time saved and
positions gained remain unvalidated.
