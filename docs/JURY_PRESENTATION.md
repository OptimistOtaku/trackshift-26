# PITWALL jury walkthrough

Start with `python scripts/serve_demo.py --port 8001`, then open
http://127.0.0.1:8001/demo_fallback/. Click **Present to jury**. The four chapters
use Hungary (R11), Norris (NOR), issue lap 25. The presenter prompt sits above
the console. **Next chapter** advances the story; **Exit** returns to exploration.

## The 90-second script

1. **Tyre science — 20 seconds.** “A lap time is not a tyre-wear measurement.
   Fuel, traffic and track evolution hide the signal. Our historical research
   corrects a misleading negative HARD-tyre slope, but that practice curve did
   not predict individual race pit-stop effects. We validate race forecasts
   separately.” The chart is historical research, not a physical wear sensor.
2. **Next chapter: Forecast — 25 seconds.** The app locks a three-lap forecast
   automatically: **85.066 s**, versus **84.973 s** persistence. Point to
   **Not revealed**, then click **Advance to lap 28 & score**. The recorded lap
   is **85.071 s**: **0.005 s** model error versus **0.098 s** baseline error.
   Say: “The prediction stays fixed while replay advances. This is one named
   example; our complete evaluation is the accuracy evidence.”
3. **Next chapter: Undercut — 25 seconds.** Read the cost bars: roughly
   **3.95 s** fresh-tyre benefit, less **0.08 s** rival pace, **1.50 s** gap and
   **0.70 s** warm-up. Central margin is **+1.67 s**. Click **Add 2s traffic**:
   it becomes **−0.33 s**. Say: “Rejoin traffic erases the central advantage.
   Both ranges cross zero, so this is a stress test for the engineer.” Initial
   range: **−6.93 to +10.26 s**; stressed: **−8.93 to +8.26 s**. Both cars stop;
   shared pit transit cancels. Inventory and scenario costs require confirmation.
4. **Next chapter: Results — 20 seconds.** “Across 6,831 scored forecasts,
   pace RMSE is **0.743 s**, versus **0.844 s** persistence: **12.0% lower**.
   Rival-time RMSE improves **10.0%**. Loss-alert precision is **78.1%**.
   The engineer can inspect predictions, assumptions and evidence in one place.”
   Close with: “PITWALL makes tyre-related pace risk visible and prices the response.”

## Ready-to-use presentation and backup

- `demo_fallback/pitch.html`: six-slide browser presentation, arrow-key navigation,
  presenter notes and print/save-PDF. Click **Pitch deck** from the console.
- `artifacts/submission/PITWALL_Jury_Final.pptx`: editable six-slide PowerPoint.
- `artifacts/submission/PITWALL_Offline_Demo.zip`: extract and run `START_DEMO.cmd`
  on Windows, or `python3 scripts/serve_demo.py --port 8001` elsewhere. Requires
  Python 3.10+, no pip/npm install or cloud connection for viewing. Includes the deck.
- Build the package again with `python scripts/package_jury.py`.

## Answers to likely jury questions

**Is it live inference?** No. This is a historical replay of chronological,
precomputed model predictions. The receipt freezes an existing as-of prediction;
actuals are only displayed after the replay reaches the target. A production
timestamped ingestion/inference service is outside this demo.

**Does weather improve the deployed model?** Weather and measured traffic are
visible as context, with freshness and coverage checks. Seventeen pace candidates
include environmental ablations. The selected pace model won development
selection and does not directly consume the new weather/traffic features.

**Does the undercut win a position?** That has not been established. The pre-stop
model's RMSE is 0.757 s versus a 0.761 s mean baseline, a small improvement. The
undercut is a conditional arithmetic stress test, with wide uncertainty, not a
validated optimal pit call or measured race time saved.

**How strong is the evaluation?** Models use earlier races; development chooses
architectures. R09–R12 were already inspected, so this is a reused evaluation,
not a new blind test. 6,831/9,062 pace forecasts and 3,128/5,117 rival forecasts
are scored; interruptions exclude other targets. Alert precision improves but
recall is 65.9% versus 66.7%. Overlapping windows are correlated.

**What happens with missing data?** Select an early lap or pit/neutralised lap:
the console waits for supported history. China has no reliable cached circuit
geometry, and sparse traffic is unavailable. Unsupported stop scenarios abstain.
Changing driver or race prevents a locked receipt revealing another context's result.

**What is missing for physical tyre life?** Carcass/surface temperature, pressure,
actual fuel and tyre-set history, and independent wear measurements. Track
temperature is not tyre temperature. These gaps are not filled with guessed data.

Sources: `artifacts/demo/intelligence/report.json`, `battle_report.json`,
`decision_report.json`, `R11.json` and historical `artifacts/demo/model.json`.
