# Demo brief — Ruhani

You own the demo. This is everything you need; you should not have to ask what a number means
or read any Python. If something here is wrong or missing, that's a bug in this document —
say so and I'll fix it.

**Presentation: Sat 12 Sep, Mohali.** Judges will click on this themselves, so it has to work
without anyone narrating it.

---

## 1. Setup (5 minutes)

```bash
git pull
cd trackshift-26
python -m http.server 8000
```

Then build in a folder like `demo/` and point `fetch` at `../artifacts/demo/…`, or just copy
`artifacts/demo/` next to your `index.html`. Either is fine.

**Do not open the HTML as `file://`** — `fetch` is blocked by CORS and you'll lose twenty
minutes to a confusing error. Always go through `http://localhost:8000`.

Stack is your call. My only recommendation: **no build step if you can avoid it.** A single
`index.html` with React from a CDN, or plain JS, means nothing can fail to compile on stage.
If you'd rather use Vite/React properly, do that — you know this better than I do.

---

## 2. The data

Three things, all static JSON in `artifacts/demo/`. Full spec in
[DEMO_CONTRACT.md](DEMO_CONTRACT.md). **The contract is frozen** — field names and shapes will
not change before Saturday. If a number needs correcting, the value changes and the shape
doesn't, so nothing you build will break.

| File | What's in it |
|---|---|
| `index.json` | Headline numbers + the list of 12 races |
| `model.json` | Fitted coefficients — lets you compute the undercut **client-side, no server** |
| `races/R01.json` … `R12.json` | Every lap and every real pit stop, per race |

Numbers you can put on screen as fact:

- **288** pit stops analysed, **12** races, full 2026 season
- **0.95 s/lap** RMSE, out-of-sample (leave-one-event-out)
- **0.82** calibration slope (1.0 = magnitudes exactly right)
- **+11.9%** better than a season-average baseline
- **21.75 s** measured pit loss (season median; 20.1–23.7 s across circuits)

⚠️ In `laps_data`, `lap`, `tyre_age` and `position` come out of JSON as **floats** (`1.0`, not
`1`). Coerce before you use them as keys or labels.

---

## 3. Feature 1 — Undercut calculator ← **this is the hero, build it first**

The question a race engineer actually asks, live, with the gap on screen: *"I pit now, they
respond a lap or two later. Do I come out ahead?"*

Paste this in — it's verified against the Python to within 3×10⁻⁵ s:

```js
const model = await fetch('artifacts/demo/model.json').then(r => r.json());
const D = model.degradation;

// Tyre-age effect. MUST saturate — never let it decline past the peak.
// A declining curve claims tyres get FASTER as they wear, which is the exact
// sign error this whole project exists to point at. Don't "fix" this clamp.
function phi(a) {
  const x = Math.min(Math.max(a, 0), D.peak_age);
  return D.b1 * x + D.b2 * x * x;
}

// The validated model: seconds per lap a fresh tyre buys.
function step0({ pair, trackTemp, dClose = 0 }) {
  return model.intercept
       + (model.pairs[pair] ?? 0)
       + model.tt_coef   * (trackTemp - model.tt_mean)
       + model.traf_coef * dClose;
}

// THE HERO CALCULATION.
// myTyreAge = age of the tyre you are about to REMOVE.
// gapS      = how far behind the rival you are now, in seconds (positive = behind).
function undercut({ pair, trackTemp, myTyreAge, rivalTyreAge, gapS, laps = 8 }) {
  const s0 = step0({ pair, trackTemp });
  const dL = s0 - phi(myTyreAge) + phi(model.fresh_age);  // compound gain, net of age
  const rows = [];
  let gained = 0;
  for (let k = 1; k <= laps; k++) {
    gained += dL + phi(rivalTyreAge + k) - phi(k);
    rows.push({ respondAfter: k, gained,
                gapAfter: gapS - gained, ahead: gapS - gained < 0, tyreDeficit: k });
  }
  const first = rows.find(r => r.ahead);
  return { rows, works: Boolean(first),
           needsThemOutFor: first ? first.respondAfter : null,
           firstLapGain: rows[0].gained };
}
```

**Inputs to expose:** race (dropdown — sets `trackTemp` from `index.json`), compound pair
(dropdown, 9 options from `model.pairs`), my tyre age (slider 1–50), rival tyre age (slider
1–50), gap in seconds (slider 0–5, step 0.1).

**The output that should be biggest on the page:**

```
UNDERCUT WORKS
+1.80 s on the first lap out
They only have to stay out 1 more lap
Cost: you rejoin 1 lap older than the car you just passed
```

Reference case to check your wiring — Austria, `MEDIUM>HARD`, track temp 51.1, my tyre 24
laps, rival 24 laps, gap 1.5 s → **+1.80 s on lap one, works, needs them out 1 lap.**

Two things that make this land with judges:

- **Say that the pit loss cancels.** Both cars serve the same pit lane, so the ~22 s drops out
  of the comparison. That's *why* undercuts work, it's counter-intuitive, and one line of copy
  on screen explains the whole mechanism.
- **Always show `tyreDeficit`.** Undercutting leaves you that many laps older than the car you
  just passed. Showing the cost alongside the gain is what makes this a tool instead of a hype
  machine, and judges notice.

---

## 4. Feature 2 — Race replay scrubber

Load `races/R08.json` (Austria is the best demo race — 71 laps, 41 stops). Slider over laps.
At lap *L*: filter `laps_data` to that lap, sort by `position`, and show driver, compound, tyre
age, lap time. Mark anyone whose `pit_lap === L` in `stops`.

The bit that ties it to the model: for each driver, show what a stop **right now** would buy
them — `step0({ pair: currentCompound + '>HARD', trackTemp })`. As you scrub, the numbers move.

---

## 5. Feature 3 — Validation, if there's time

`races/*.json` → `stops[]` has both `step_obs_s` (measured) and `step_pred_s` (predicted,
out-of-sample). Scatter one against the other with a y=x line. **That scatter is the proof the
model works** — no computation needed, it's already in the file.

---

## 6. What NOT to build

**No "recommended pit lap." No "optimal strategy."** This is the important one.

I built the pit-window recommender and then tested it, and it failed: it covers 66.9% of real
stops, but a window of the same width just placed mid-race covers 66.2%. It adds nothing over
"pit halfway through the race." So it's out of the product.

If you put a recommended lap in the UI, a judge will ask how we validated it, and the honest
answer is "we did, and it didn't beat a trivial heuristic." Much better to not have the feature
and be able to say *we tested it and cut it* — that's a strength, not a gap.

**No safety-car probability that looks fitted.** If SC appears at all it's a slider the user
sets, labelled as their assumption. We have 12 races at 12 different circuits — one observation
each — so we cannot estimate it and won't pretend to.

---

## 7. Copy rules

The modelling is defensible; the labels have to be too. One overclaiming word undoes it.

| ✅ Use | ❌ Never |
|---|---|
| "Undercut available" | "Optimal strategy" |
| "A fresh tyre buys 1.8 s/lap here" | "Predicted lap time" |
| "Measured across 288 real pit stops" | "AI-powered" / "machine learning" |
| "Out-of-sample RMSE 0.95 s/lap" | "95% accurate" |
| "Pit loss measured at 21.7 s" | "Simulated race" |

We never predict lap times and we never simulate a race — we predict *the pace a fresh tyre
buys*, which is a different and much better-supported claim. Keep the copy on that.

---

## 8. Priority order

If you run out of time, ship in this order. **A polished feature 1 alone beats three rough
ones.**

- **P0 — Undercut calculator, working and interactive.** If only this exists, we're fine.
- **P1 — Race replay scrubber.**
- **P2 — Validation scatter.**
- **P3 — Polish:** dark F1-style theme, team compound colours (soft red / medium yellow / hard
  white), the big number in a monospace face.

**Done means:** someone who has never seen it can open it, move a slider, and get a number that
changes — without anyone explaining what to click.

---

## 9. What I'm doing

Deck rewrite, the validation figures, and fixing one causality leak in the model (a track-temp
term currently uses a race average, which at lap 10 technically knows the future — irrelevant
to the published numbers, but indefensible in a live replay).

**`model.json` values may change slightly when I fix that. The field names will not.** Just
re-pull before Saturday and your code keeps working.

Ping me for anything — especially if a number here doesn't match what you're seeing. That'd
mean I've made an error, and I'd rather find it tonight than on stage.
