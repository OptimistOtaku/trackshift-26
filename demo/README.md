# PITWALL — demo surfaces

The front end for TrackShift 2026. Four surfaces, walked in the order in
`docs/JUDGE_QA.md` §4, plus the race-engineer panel on the replay.

Every number on screen is read from `artifacts/demo/` at runtime and recomputed
in the browser. There is no hardcoded headline figure anywhere in `src/`. Re-export
the artifacts and the page changes; nothing here needs editing.

## Run it

```bash
cd demo
npm install
npm run dev          # http://localhost:5173
```

For the day itself, build once and keep the folder:

```bash
npm run build        # -> demo/dist, with artifacts/demo copied in
npm run preview      # serves dist on :4173
```

`dist/` is self-contained. No CDN, no webfont, no API call, no key. Switch the wifi
off, reload, and every surface still works — that is the drill in `JUDGE_QA.md` and
this build is meant to pass it.

## What is where

```
src/
  lib/model.js      phi, step0, undercut — mirrors src/pitwall/stopvalue.py
  lib/data.js       static JSON loader, three-candidate root resolution
  lib/engineer.js   race-engineer state block + the deterministic templates
  components/       Chart.jsx (hand-rolled SVG) and ui.jsx (pills, limitations)
  surfaces/         SignFlip, Undercut, Replay, Validation
```

`vite.config.js` sets `publicDir: '../artifacts/demo'`, so `artifacts/demo/model.json`
is served at `/model.json` in dev and copied into `dist/` on build. If that ever breaks,
`lib/data.js` walks up to the repo root instead, so `python -m http.server` from the
repo root also works. Do not simplify that fallback away.

## Things that are deliberate

**The clamp in `phi`.** The fitted quadratic bends downwards past `peak_age`, so it is
held flat there. A declining `phi` claims tyres get faster as they wear, which is the
sign error this project exists to point at. The charts draw straight segments for the
same reason: every chart library smooths that corner into a decline.

**Pit loss is on screen with a line through it.** It cancels — both cars serve the same
pit lane — and that cancellation is why an undercut works at all. Showing it struck
through is the difference between "it cancels" and "we forgot it".

**The gap is an input and says so.** Nothing in the dataset measures the interval between
two cars. It is the one number the operator supplies, labelled `gap_source: "ui_input"`
in the state block.

**`stops[]` is filtered to `pit_lap <= lap` before anything derives from it.** The race
file knows the whole race. On lap 16 at Austria it already knows VER stops on lap 17,
and the replay is not allowed to.

**The red-bordered blocks are the negative results.** A full border on this page means:
we built this, we tested it, it did not survive, and it is on the surface anyway. They
are the only full borders in the design.

**Colour does two jobs and shape disambiguates.** Bare yellow is a number we measured or
a live control; a filled yellow pill is the MEDIUM compound. Bare red is a wrong-signed
number or the naive fit; a filled red pill is SOFT. Pirelli's compound colours and the
brief's palette are the same four values, so nothing had to be invented.

## Reference case

Austria, `MEDIUM>HARD`, track temp 51.092599, both tyres 24 laps old, 1.5 s behind:

```
step0 = 1.628518 + (-0.376029) + 0.039178 * (51.092599 - 41.394659) = 1.632346
dL    = step0 - phi(24) + phi(3)                                    = 1.073801
lap 1 = dL + phi(25) - phi(1)                                       = +1.760057
```

The undercut surface loads on exactly this case. If it shows **+1.80**, `model.json`
predates the 11 Sep causality fix — re-pull the artifacts before presenting.

## Keyboard

`1`–`4` move between surfaces. On stage that is more reliable than a trackpad.
