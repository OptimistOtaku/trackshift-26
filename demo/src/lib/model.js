/* ===================================================================== *
 *  The model, client side. Mirrors src/pitwall/stopvalue.py.
 *
 *  Ported from demo_fallback/index.html, which is verified against the
 *  Python to 4e-5 s. Reference case, re-derived by hand against the shipped
 *  model.json:
 *
 *    Austria, MEDIUM>HARD, track temp 51.092599, my tyre 24, rival 24
 *      step0 = 1.628518 + (-0.376029) + 0.039178 * (51.092599 - 41.394659)
 *            = 1.632346
 *      dL    = step0 - phi(24) + phi(3) = 1.073801
 *      lap 1 = dL + phi(25) - phi(1)    = +1.760057
 *
 *  If you compute 1.80, model.json is stale — re-pull. See DEMO_BRIEF.md
 *  section 3 and the 11 Sep causality fix.
 * ===================================================================== */

export const int = (x) => Math.round(Number(x));

/* ONE formatter, used by the DOM and by the race-engineer state block alike.
   RACE_ENGINEER.md section 1.5: if the panel shows 0.5097 while the radio line
   says 0.51, a judge notices the disagreement. Both read from here. */
export const fmt = (x, dp = 2) =>
  x == null || !Number.isFinite(Number(x)) ? "—" : Number(x).toFixed(dp);

export const round = (x, dp = 2) =>
  x == null || !Number.isFinite(Number(x)) ? null : Number(Number(x).toFixed(dp));

/* Signs are printed, never implied. This project exists because of a sign
   error, so no number on this page is allowed to hide its own sign.
   U+2212 MINUS SIGN, not a hyphen — it aligns with the digits. */
export const signed = (x, dp = 2) => {
  if (x == null || !Number.isFinite(Number(x))) return "—";
  const v = Number(x);
  return (v < 0 ? "−" : "+") + Math.abs(v).toFixed(dp);
};

export const pl = (n, word) => `${n} ${word}${Number(n) === 1 ? "" : "s"}`;

export function makeModel(model) {
  const D = model.degradation;

  /* Tyre-age effect. MUST saturate.
     The fitted quadratic has b2 < 0 and bends DOWNWARDS past peak_age. Letting
     it decline claims tyres get FASTER as they wear, which is the exact sign
     error this whole project exists to point at. Do not remove this clamp, and
     do not let a chart library smooth the corner into a decline either. */
  const phi = (a) => {
    const x = Math.min(Math.max(Number(a) || 0, 0), D.peak_age);
    return D.b1 * x + D.b2 * x * x;
  };

  /* Seconds per lap a fresh tyre buys, before any age arithmetic.
     d_close is fixed at 0 — the sample mean, i.e. "typical traffic". The model's
     traffic term is a difference ACROSS the stop, so half of it lies in the
     future during a replay and there is no honest per-lap value to use. */
  const step0 = (pair, trackTemp, dClose = 0) =>
    model.intercept +
    (model.pairs[pair] ?? 0) +
    model.tt_coef * (trackTemp - model.tt_mean) +
    model.traf_coef * dClose;

  /* The replay feed carries INTERMEDIATE and null compounds, for which no pair
     exists. `?? 0` would silently score those as HARD>HARD — a wrong number on
     screen with no error. Callers check first and render a dash. */
  const hasPair = (pair) => model.pairs[pair] != null;

  /* What a stop right now buys this car, net of the age it is carrying. */
  const stopBuys = (pair, trackTemp, age) =>
    hasPair(pair)
      ? step0(pair, trackTemp) - phi(age) + phi(model.fresh_age)
      : null;

  /* Degradation carried against a fresh set. Clamped at 0 below fresh_age: a
     tyre two laps into a stint computes negative, and "you are 0.06 s/lap
     better than fresh" is not a sentence anyone should hear on the radio. */
  const degVsFresh = (age) => Math.max(0, phi(age) - phi(model.fresh_age));

  /* THE HERO CALCULATION.
     The pit loss CANCELS — both cars serve the same pit lane, so the ~22 s drops
     out of the comparison entirely. That is why undercuts work and it is the
     one line of copy that explains the whole mechanism. */
  function undercut({ pair, trackTemp, mine, theirs, gap, laps = 8 }) {
    const s0 = step0(pair, trackTemp);
    const dL = s0 - phi(mine) + phi(model.fresh_age);
    const rows = [];
    let gained = 0;
    for (let k = 1; k <= laps; k += 1) {
      gained += dL + phi(theirs + k) - phi(k);
      rows.push({ k, gained, after: gap - gained, ahead: gap - gained < 0 });
    }
    const first = rows.find((r) => r.ahead) ?? null;
    return {
      rows,
      step0: s0,
      firstLapGain: rows[0].gained,
      clears: Boolean(first),
      needsThemOut: first ? first.k : null,
      /* The cost. You rejoin this many laps older than the car you passed.
         A gain quoted without its cost is a sales pitch, not a call. */
      tyreDeficit: first ? first.k : null,
      extrapolating: mine > D.max_age_seen || theirs > D.max_age_seen,
    };
  }

  return { phi, step0, hasPair, stopBuys, degVsFresh, undercut, D, raw: model };
}
