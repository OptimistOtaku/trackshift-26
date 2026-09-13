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
- **0.96 s/lap** RMSE, out-of-sample (leave-one-event-out)
- **0.79** calibration slope (1.0 = magnitudes exactly right)
- **+11.1%** better than a season-average baseline
- **21.75 s** measured pit loss (season median; 20.1–23.7 s across circuits)

These moved slightly on 11 Sep when I fixed a causality leak (a track-temp term was using the
whole race's average, so at lap 10 it was reading laps 11–71). RMSE was 0.95, calibration 0.82,
improvement 11.9%. **The numbers above are the current ones — take them from here, not from an
older screenshot.**

**All five are now live fields in `index.json` → `headline`; nothing needs hardcoding.**
`rmse_s`, `calib_slope`, `improvement_pct`, `baseline_rmse_s` and `events_won` are all there as
of the latest export. If a number on your screen disagrees with this table, trust your screen
and tell me — that means I've let this doc go stale, not that you've wired it wrong.

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

**The output that should be biggest on the page — the RATE, then the arithmetic:**

```
A fresh tyre buys you 1.76 s/lap here
You are 1.5 s behind
One lap of clear air covers it

Cost: you rejoin 1 lap older than the car you just passed
```

⚠️ **Do not print "UNDERCUT WORKS" as a verdict.** I backtested exactly that claim against 137
real head-to-head duels this season and it failed a placebo — see §6. We can defend the rate.
We cannot defend "you will gain a place." Show the subtraction and let the user conclude; that
is what a race engineer actually does, and it is the version that survives a judge's question.

Reference case to check your wiring — Austria, `MEDIUM>HARD`, track temp 51.09, my tyre 24
laps, rival 24 laps, gap 1.5 s → **+1.76 s on lap one, so one lap of clear air covers 1.5 s.**
(This was 1.80 before the 11 Sep causality fix. If you get 1.80, re-pull.)

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

### Two traps in this feature. Both will bite you.

**1. `stops` contains the whole race, including the future.** At lap 16 the array already holds
a stop that happens on lap 17. If you render it unfiltered you are showing the judge a pit stop
before it has happened, which is the exact sin this project exists to criticise. Always:

```js
const sofar = race.stops.filter(s => s.pit_lap <= L);
```

Same for anything derived from it. The full array is still the right thing for the validation
scatter in §5 — that's a post-race view, so there it's fine.

**2. Some laps have no rows at all and the table goes blank — FIXED, use the new feed.**
`laps_data` in `races/R*.json` was filtered to green, non-pit, accurate laps because it was
built to *fit* a model. That leaves **62 holes across the season** — Austria is missing 24 and
25, Monaco 60–71, Britain its last five.

**`artifacts/demo/replay/R01…R12.json` now exists and has zero blank laps in all twelve races.**
Point the scrubber at it. Same field names as `laps_data` plus per-lap flags:

```js
const race = await fetch('../artifacts/demo/replay/R08.json').then(r => r.json());
// each row adds: green, in_lap, out_lap, deleted, clean, track_status
const rows = race.laps_data.filter(r => r.lap === L);
```

Three things worth knowing about it:

- `clean: true` reproduces the old `laps_data` **row for row**, so the two feeds provably differ
  by nothing but the filter. Grey out the non-clean rows rather than dropping them — that's how
  the judge sees a safety car instead of a gap.
- `lap`, `tyre_age` and `position` are real **integers** here, not the float trap in §2.
- **Don't re-derive `clean` as `green && !in_lap && !out_lap && !deleted`.** It won't match: lap
  1 passes all four and is still excluded from the fit, because a standing start puts it seconds
  outside the pace band. Use the `clean` field.

**Keep the empty-state guard anyway.** It costs nothing and it's the difference between
"handled" and "broken" if anything is missing on the day:

```js
if (rows.length === 0) return <Caption>No timing data for this lap</Caption>;
```

### Three more traps in the replay feed — I hit all three building the fallback

**3. `track_status` is a concatenation of codes, not one code.** `"671"` does not mean status
671; it means statuses 6, 7 and 1 all occurred during that lap (VSC deployed, VSC ending,
green). There are 24 distinct combinations across the season. So looking the whole string up in
`track_status_codes` misses on everything except the single-digit cases, and you get raw digits
on screen:

```js
// WRONG — prints "126 / 26"
const label = codes[row.track_status];
// RIGHT — split into characters, drop green, then look each one up
const flags = [...new Set(String(row.track_status ?? '').split(''))]
  .filter(c => c && c !== '1').map(c => codes[c] || c);
```

This is worth getting right because it's the payoff of the whole replay feed: at Austria laps
24–25 — the exact two laps missing from the filtered feed — it renders **YELLOW · VSC
DEPLOYED**. The judge sees *why* there was a hole instead of seeing a hole.

**4. `compound` is not always one of SOFT/MEDIUM/HARD.** The feed also contains
`INTERMEDIATE` and `null`. So the `currentCompound + '>HARD'` lookup in §4 above returns
`undefined` for those rows, and `?? 0` then silently scores them as if they were `HARD>HARD` —
a wrong number on screen with no error. Check the pair exists first and render a dash if it
doesn't:

```js
const pair = `${row.compound}>HARD`;
const buys = model.pairs[pair] != null ? step0({pair, trackTemp}) - phi(age) + phi(3) : null;
```

**5. `drivers[]` can be shorter in `races/` than in `replay/`, and by a different amount per
race.** Austria is 20 in `races/` against 22 in `replay/`; Australia is 20 in both; Britain is
22 in both. The filtered feed only lists drivers who set a clean lap, so the gap is however many
drivers never set one. Don't size anything off one feed and index it with the other. Row counts
also fall through a race as cars retire — Austria is 22 on lap 1, 19 by lap 24, 8 on the last
lap. That's real, not missing data.

---

## 5. Feature 3 — Validation, if there's time

`races/*.json` → `stops[]` has both `step_obs_s` (measured) and `step_pred_s` (predicted,
out-of-sample). Scatter one against the other with a y=x line. **That scatter is the proof the
model works** — no computation needed, it's already in the file.

---

## 6. What NOT to build

**No "recommended pit lap." No "optimal strategy."** This is the important one.

I built the pit-window recommender and then tested it, and it failed. It covers 68.4% of real
stops against 65.8% for a window of the same width just placed mid-race — a 2.6-point edge, too
small to lean on. And the test that actually decides it is worse: per event, does our window
*move* with the lap teams chose? The mid-race **constant** tracks it better than we do (r=+0.73
vs +0.64, MAE 4.9 laps vs 8.4), and with race length divided out our centre carries no signal at
all (r=+0.08, p=0.80). So it adds nothing over "pit halfway through the race." So it's out of the product.

If you put a recommended lap in the UI, a judge will ask how we validated it, and the honest
answer is "we did, and it didn't beat a trivial heuristic." Much better to not have the feature
and be able to say *we tested it and cut it* — that's a strength, not a gap.

**No claim that we predict who comes out ahead.** Same story, found last night. I scored the
undercut against 137 real duels — A running behind B, A pits, B responds later, who's ahead
afterwards (`scripts/check_undercut_backtest.py`).

It looks like a hit: cars we flagged won 34% of the time, cars we called against won 5%
(p < 0.0001). But rank the same duels by **the gap alone, no model at all** and you get AUC
0.836; our margin gets 0.836 too. Identical. Our model's own contribution, scored by itself, is
AUC 0.490 — a coin flip.

The reason is a ruler, not a bug. The margin is `gain − gap`. Across those duels the gain we
supply has a spread of 0.46 s; the gap has a spread of 14.6 s. A term 30× smaller than the one
it's subtracted from can't change the ordering, so `gain − gap` is just `−gap` in a costume.

**So: show the rate, show the subtraction, never assert the outcome.** The rate is ours and it's
validated. The gap is on every timing screen in the pit lane and we didn't discover it.

**No safety-car probability that looks fitted.** If SC appears at all it's a slider the user
sets, labelled as their assumption. We have 12 races at 12 different circuits — one observation
each — so we cannot estimate it and won't pretend to.

---

## 7. Copy rules

The modelling is defensible; the labels have to be too. One overclaiming word undoes it.

| ✅ Use | ❌ Never |
|---|---|
| "A fresh tyre buys 1.8 s/lap here" | "Undercut works" / "you will gain a place" |
| "One lap of clear air covers 1.5 s" | "Optimal strategy" |
| "Measured across 288 real pit stops" | "Predicted lap time" |
| "Out-of-sample RMSE 0.96 s/lap" | "AI-powered" / "machine learning" |
| "Pit loss measured at 21.7 s" | "95% accurate" / "Simulated race" |

We never predict lap times, we never simulate a race, and we never predict positions — we
predict *the pace a fresh tyre buys*, which is a different and much better-supported claim.
Keep the copy on that.

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

## 9. What changed on 11 Sep, and what I'm doing

Three things landed tonight. **Re-pull before you do anything else.**

1. **Causality leak fixed.** A track-temp term was using the whole race's average, so at lap 10
   it was reading laps 11–71. Now it's an expanding mean over laps so far. Every headline number
   moved slightly (§2) and the Austria reference case went 1.80 → 1.76. All field names are
   unchanged, so nothing you've built breaks.
2. **The undercut's headline changed from a verdict to a rate** (§3, §6). This is the one that
   affects what you're building right now — sorry for the churn, but I'd rather eat it tonight
   than have a judge find it tomorrow.
3. **Two replay traps documented** (§4). The `stops` future leak is the one to fix first; it's
   a one-line filter.

Still coming from me: an unfiltered replay feed so the scrubber stops going blank on safety-car
laps, and the degradation curve exported so we can draw the naive-vs-corrected sign flip. Both
are additive — new files, no changes to what you already read.

**Both of those landed later the same night**, along with two more:

4. **The unfiltered replay feed is in** (`artifacts/demo/replay/`) — §4 rewritten. Zero blank
   laps across all twelve races, per-lap green/in-lap/out-lap/deleted/clean flags.
5. **The sign-flip curves are in** (`model.json` → `degradation_curves`) — see §10.
6. **`races/R*.json` had the wrong race length for Britain** — it said 47 laps for a 52-lap
   race, because it was taking the highest lap anyone set a *clean* time on and Silverstone
   finished under a safety car. If your scrubber's track stopped early there, that was this,
   not you. Fixed, and there's a new `last_clean_lap` field so you can tell the two apart.
7. **`improvement_pct`, `baseline_rmse_s` and `events_won` are now real fields** in
   `index.json` → `headline`. Nothing in §2 needs hardcoding any more.

Ping me for anything — especially if a number here doesn't match what you're seeing. That'd
mean I've made an error, and I'd rather find it tonight than on stage.

---

## 9a. There's a working fallback at `demo_fallback/` — steal from it

**This is not competing with your build.** `demo/` is yours and it's what we show. I built
`demo_fallback/index.html` for two reasons: so there is something clickable if your build isn't
finished by Saturday morning, and because writing it was the only way to find traps 3–5 above.
If yours works, we show yours and this never comes up.

```bash
python -m http.server 8000     # from the repo root
# then http://localhost:8000/demo_fallback/
```

It's one file, no build step, no framework, no CDN, nothing from the network — so it passes the
"turn the wifi off and reload" drill in [JUDGE_QA.md](JUDGE_QA.md) §4. All four surfaces work:
undercut, sign flip, replay scrubber, validation scatter.

**What's worth stealing rather than rewriting:**

- The `phi` / `step0` / `undercut` functions are verified against the Python. The Austria
  reference case comes out at **+1.760057** in the browser, against 1.760057 from
  `model.json` in Python.
- The `track_status` splitting and the missing-pair guard (traps 3 and 4).
- The copy. Every string in it obeys §7 — it shows the rate and the subtraction and never
  asserts the outcome.
- Every number is read from the JSON at runtime. Nothing is hardcoded, so a re-export can't
  leave a stale figure on a slide.

Take the logic, drop the styling — you'll do the visual side better than I have.

---

## 10. Feature 4 — The sign flip (new data, `model.json` → `degradation_curves`)

This is the chart that opens the story, and until tonight it wasn't in the demo data. It is now.
Slot it **between P1 and P2** in §8: it's more valuable than the validation scatter and less
valuable than the scrubber, and it is the least code of the three.

**The story in one paragraph.** Do the obvious thing — fit lap time against tyre age on practice
long runs — and two of the three compounds tell you tyres get *faster* the more you wear them.
Nothing is broken. Inside a practice run the car burns one lap of fuel for every lap the tyre
ages, so fuel and tyre age move together and the age slope swallows the fuel effect, which pulls
the other way. You cannot separate them with practice data at all. So we estimate the fuel
sensitivity on *race* laps instead, where stints start at different points in the race and the
same tyre age turns up at many different fuel loads. Subtract that, measure the rubber going
down, and the curves flip over.

**The numbers, s/lap at tyre age 10:**

| compound | naive fit | deconfounded | |
|---|---|---|---|
| SOFT | +0.0518 | +0.1096 | right sign, but understated 2.1× |
| MEDIUM | **−0.0459** | +0.0738 | sign flip |
| HARD | **−0.1535** | +0.0631 | sign flip |

Fuel sensitivity came out at **+0.0294 s/kg (se 0.0039)**, against a literature range of
0.030–0.035 s/kg. Put that on screen — it's the line that says we measured a real thing rather
than tuned a number until the picture looked right.

**What to draw.** One chart, one compound at a time (a three-tab or three-button switcher is
plenty). X axis is tyre age, Y axis is `delta_s`. Two lines:

```js
const C = model.degradation_curves.practice.compounds.HARD;  // or MEDIUM / SOFT
// grey / dashed:  C.naive.curve         → [{ age, delta_s }, …]
// bright:         C.deconfounded.curve  → [{ age, delta_s }, …]
```

No maths. The points are already sampled at every whole lap over the ages practice actually ran
(`age_lo` → `age_hi`), both lines share the same ages, and `age` is a real integer here — not
the float trap in `laps_data`. Both lines start at exactly `delta_s = 0`, because practice can
only identify the *shape* of a degradation curve and not its height, so we pin both to zero at
the youngest tyre in the fit. Say that in a caption if there's room; it's the kind of honesty a
judge notices.

**HARD is the one to show first.** The naive line dives to **−2.47 s/lap by age 17** — it is
seriously claiming a seventeen-lap-old HARD is two and a half seconds a lap quicker than a fresh
one — and never gets back above zero. The deconfounded line climbs the whole way to **+2.73** by
age 30. Opposite directions, same laps, same regression, one confounder removed.

Each compound also carries `sign_flip` (true for MEDIUM and HARD, false for SOFT), so you can
badge the flip without hardcoding which ones flipped.

**Copy that works here:** *"The obvious fit says tyres get faster as they wear. It's fuel."* And
the label under the axis: *"seconds per lap slower than a 2-lap-old tyre."* Don't write
"corrected" or "improved" — the naive line isn't a mistake we made, it's the answer the standard
method gives, which is the entire point.

### Also new: `degradation_curves.race`

The same `phi` you already use for the undercut, pre-sampled as `[{ age, delta_s }, …]` from 0
to 50 laps, so the tyre-age gauge and the curve are visibly the same object. If you're already
showing a tyre-age number somewhere in the scrubber, this is the curve to put behind it with a
dot on it.

⚠️ **The tail is flat on purpose.** Every point from age 22 onwards is exactly `0.755031`, and it
must stay flat. That's the saturation clamp: the fitted quadratic would bend *downwards* past its
peak, which would claim tyres get faster as they wear — the exact error this whole chart exists
to point at. If your chart library smooths the corner into a decline, turn the smoothing off.

### What not to do with the practice curves

**Draw them, don't compute with them.** The deconfounded practice curve is defensible in sample
and does not transfer to a race — calibration slope +0.006 against the real pit-stop step, which
is precisely why the undercut calculator is built on race stops instead. So nothing on the page
should read a tyre age off `degradation_curves.practice` and turn it into seconds gained. The
undercut code in §3 is unchanged and stays exactly as it is.

**And nothing here changed underneath you.** `degradation_curves` is a new key. Every field you
were already using is spelled the same and means the same thing.
