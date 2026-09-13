/* ===================================================================== *
 *  1 — The sign flip.
 *
 *  Both curves are drawn straight from model.degradation_curves.practice and
 *  nothing on this surface is computed from them, per the not_a_predictor note:
 *  the practice fit is the diagnostic, not the product. The only arithmetic
 *  here is "read both curves at one age and subtract", which is a statement
 *  about the two fits, not a prediction about a race.
 * ===================================================================== */

import { useState } from "react";
import { Plot, Path, VRule, extent } from "../components/Chart.jsx";
import { Limitation, Num, Pill, SurfaceHead, Source } from "../components/ui.jsx";
import { fmt, signed } from "../lib/model.js";

const ORDER = ["SOFT", "MEDIUM", "HARD"];

/* Curves are tabulated at integer ages; read between points linearly rather
   than snapping, so dragging the marker feels continuous. */
function readAt(curve, age) {
  if (!curve?.length) return null;
  if (age <= curve[0].age) return curve[0].delta_s;
  const last = curve[curve.length - 1];
  if (age >= last.age) return last.delta_s;
  for (let i = 1; i < curve.length; i += 1) {
    if (curve[i].age >= age) {
      const a = curve[i - 1];
      const b = curve[i];
      const t = (age - a.age) / (b.age - a.age || 1);
      return a.delta_s + t * (b.delta_s - a.delta_s);
    }
  }
  return last.delta_s;
}

/* Land the marker where the two fits disagree most. That is the single age at
   which the confound is doing the most damage, it differs by compound, and it
   is found in the data rather than hardcoded. */
function widestGapAge(cc) {
  let best = cc.naive.curve[0].age;
  let gap = -Infinity;
  cc.naive.curve.forEach((p) => {
    const d = Math.abs((readAt(cc.deconfounded.curve, p.age) ?? 0) - p.delta_s);
    if (d > gap) {
      gap = d;
      best = p.age;
    }
  });
  return best;
}

export default function SignFlip({ M }) {
  const dc = M.raw.degradation_curves;
  const [compound, setCompound] = useState("HARD");
  const c = dc.practice.compounds[compound];

  const [age, setAge] = useState(() => widestGapAge(dc.practice.compounds.HARD));
  const shownAge = Math.min(Math.max(age, c.age_lo), c.age_hi);

  const naiveAt = readAt(c.naive.curve, shownAge);
  const deconAt = readAt(c.deconfounded.curve, shownAge);
  const missing = deconAt - naiveAt;

  const ys = [
    ...c.naive.curve.map((p) => p.delta_s),
    ...c.deconfounded.curve.map((p) => p.delta_s),
  ];
  const yDomain = extent([...ys, 0], 0.1);

  const naiveSlope = c.naive.slope_s_per_lap;
  const deconSlope = c.deconfounded.slope_s_per_lap;
  const flipped = naiveSlope < 0 && deconSlope > 0;

  return (
    <section>
      <SurfaceHead
        n="1"
        title="Practice says these tyres get faster as they wear"
        lede={`Same laps, same cars, fitted twice. Lap time on tyre age and nothing else
               gives the red curve. Subtract a fuel sensitivity measured on race laps, add the
               traffic and rubber we can observe, and you get the yellow one. Within a single
               practice run the fuel load falls as the tyre ages, so an age term with no fuel term
               absorbs the fuel saving and reports it as tyre life.`}
      />

      <div className="mb-5 flex flex-wrap items-center gap-6">
        <div className="flex items-center gap-2">
          {ORDER.map((k) => {
            const on = k === compound;
            return (
              <button
                key={k}
                type="button"
                onClick={() => {
                  setCompound(k);
                  setAge(widestGapAge(dc.practice.compounds[k]));
                }}
                className={`px-2.5 py-1 text-[12.5px] transition-colors ${
                  on ? "bg-raise text-white" : "text-dim hover:text-white"
                }`}
              >
                <span className="flex items-center gap-2">
                  <Pill compound={k} />
                  {dc.practice.compounds[k].naive.slope_s_per_lap < 0 ? (
                    <span className="text-tifosi">wrong sign</span>
                  ) : (
                    <span className="text-dim">right sign</span>
                  )}
                </span>
              </button>
            );
          })}
        </div>
      </div>

      <div className="bg-panel p-5">
        <div className="mb-4 flex flex-wrap items-baseline justify-between gap-4">
          <div className="flex items-baseline gap-5 text-[12.5px]">
            <span className="flex items-baseline gap-2">
              <span aria-hidden className="inline-block h-0 w-5 border-t-2 border-tifosi" />
              <span className="text-dim">lap time on tyre age alone</span>
            </span>
            <span className="flex items-baseline gap-2">
              <span aria-hidden className="inline-block h-0 w-5 border-t-2 border-flag" />
              <span className="text-dim">fuel, traffic and rubber accounted for</span>
            </span>
          </div>
          <span className="num font-mono text-[12px] text-faint">
            {dc.practice.n_laps} practice laps · {dc.practice.n_runs} runs
          </span>
        </div>

        <Plot
          xDomain={[c.age_lo, c.age_hi]}
          yDomain={yDomain}
          height={300}
          zeroLine
          xLabel="tyre age, laps"
          yLabel={`s/lap slower than a ${fmt(c.anchor_age, 0)}-lap-old tyre`}
          fmtX={(v) => String(Math.round(v))}
        >
          {({ x, y, h, top }) => (
            <>
              <VRule at={shownAge} x={x} top={top} h={h} stroke="#3a3a3a" />
              <Path
                points={c.naive.curve.map((p) => [p.age, p.delta_s])}
                x={x}
                y={y}
                stroke="var(--color-tifosi)"
                width={2}
              />
              <Path
                points={c.deconfounded.curve.map((p) => [p.age, p.delta_s])}
                x={x}
                y={y}
                stroke="var(--color-flag)"
                width={2}
              />
              {/* The gap at the marker, drawn as the thing it is: the distance
                  between the two answers. */}
              <line
                x1={x(shownAge)}
                x2={x(shownAge)}
                y1={y(naiveAt)}
                y2={y(deconAt)}
                stroke="#ffffff"
                strokeWidth="1"
              />
              <circle cx={x(shownAge)} cy={y(naiveAt)} r="3.5" fill="var(--color-tifosi)" />
              <circle cx={x(shownAge)} cy={y(deconAt)} r="3.5" fill="var(--color-flag)" />
            </>
          )}
        </Plot>

        <div className="mt-4 border-t border-hair pt-4">
          <div className="mb-2 flex items-baseline justify-between gap-4">
            <span className="text-[12.5px] text-dim">Read both fits at one tyre age</span>
            <span className="num font-mono text-[12.5px] text-flag">
              {Math.round(shownAge)} laps old
            </span>
          </div>
          <input
            type="range"
            min={c.age_lo}
            max={c.age_hi}
            step={1}
            value={shownAge}
            aria-label="Tyre age to read both curves at"
            onChange={(e) => setAge(Number(e.target.value))}
          />

          <dl className="mt-4 grid grid-cols-1 gap-x-8 gap-y-2 sm:grid-cols-3">
            <Row label="Age alone says" value={<Num value={naiveAt} dp={2} sign tone="tifosi" unit="s/lap" />} />
            <Row label="Fuel accounted for says" value={<Num value={deconAt} dp={2} sign tone="flag" unit="s/lap" />} />
            <Row
              label="Degradation the fuel term was hiding"
              value={<Num value={missing} dp={2} sign unit="s/lap" />}
            />
          </dl>
        </div>
      </div>

      {/* The finding, stated as the two slopes with their signs printed. A sign
          error is why this project exists, so no sign on this page is implied. */}
      <div className="mt-5 grid gap-5 md:grid-cols-2">
        <div className="bg-panel p-5">
          <h3 className="mb-3 text-[15px] font-semibold">
            Slope at {fmt(dc.slope_ref_age, 0)} laps, every compound
          </h3>
          <table className="w-full text-[13.5px]">
            <thead>
              <tr className="text-left text-[11.5px] text-faint">
                <th className="pb-1.5 font-normal">Compound</th>
                <th className="pb-1.5 text-right font-normal">Age alone</th>
                <th className="pb-1.5 text-right font-normal">Corrected</th>
              </tr>
            </thead>
            <tbody className="font-mono">
              {ORDER.map((k) => {
                const cc = dc.practice.compounds[k];
                const bad = cc.naive.slope_s_per_lap < 0;
                return (
                  <tr key={k} className="border-t border-hair">
                    <td className="py-2">
                      <Pill compound={k} />
                    </td>
                    <td className={`py-2 text-right num ${bad ? "text-tifosi" : "text-dim"}`}>
                      {signed(cc.naive.slope_s_per_lap, 3)}
                    </td>
                    <td className="py-2 text-right num text-flag">
                      {signed(cc.deconfounded.slope_s_per_lap, 3)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          <p className="mt-3 text-[12.5px] leading-relaxed text-dim">
            A negative slope claims a tyre is quicker at ten laps old than at two.{" "}
            {flipped ? (
              <>
                On {compound.toLowerCase()} the correction moves it from{" "}
                <span className="num font-mono text-tifosi">{signed(naiveSlope, 3)}</span> to{" "}
                <span className="num font-mono text-flag">{signed(deconSlope, 3)}</span> s/lap.
              </>
            ) : (
              <>
                Soft tyres degrade fast enough that the confound does not reverse the sign, only
                the magnitude: <span className="num font-mono text-tifosi">{signed(naiveSlope, 3)}</span>{" "}
                against <span className="num font-mono text-flag">{signed(deconSlope, 3)}</span> s/lap.
              </>
            )}
          </p>
        </div>

        <div className="bg-panel p-5">
          <h3 className="mb-3 text-[15px] font-semibold">Where the correction comes from</h3>
          <p className="text-[13.5px] leading-relaxed text-dim">
            Fuel sensitivity is{" "}
            <span className="num font-mono text-flag">
              {signed(dc.lambda_fuel_s_per_kg, 4)}
            </span>{" "}
            <span className="num font-mono text-dim">
              ± {fmt(dc.lambda_se_s_per_kg, 4)}
            </span>{" "}
            s/kg, fitted on <span className="num font-mono text-white">{dc.lambda_events}</span>{" "}
            events of race laps and never on the practice laps it is then applied to. Stints start
            at different points in a race, so one tyre age is seen at many fuel loads and the two
            separate. Published figures put the fuel effect at 0.030–0.035 s/kg, which is where
            ours lands.
          </p>
          <p className="mt-3 text-[13.5px] leading-relaxed text-dim">
            Practice identifies the <em className="text-white not-italic">shape</em> of a curve and
            not its height — each run carries its own intercept and runs one compound — so both
            curves are pinned to zero at {fmt(c.anchor_age, 0)} laps and only the shape is claimed.
          </p>
        </div>
      </div>

      <div className="mt-5">
        <Limitation title="These curves do not predict anything, and we are not using them to">
          {/* Quoted from model.json rather than retyped, so a refit cannot leave
              this paragraph claiming a number the model no longer produces. */}
          {dc.not_a_predictor}
        </Limitation>
      </div>

      <Source>
        model.json → degradation_curves.practice ({dc.practice.n_laps} laps,{" "}
        {dc.practice.n_runs} runs). Age-alone fit: {dc.practice.naive_spec}. Corrected fit:{" "}
        {dc.practice.deconfounded_spec}.
      </Source>
    </section>
  );
}

function Row({ label, value }) {
  return (
    <div>
      <dt className="text-[11.5px] text-faint">{label}</dt>
      <dd className="text-[17px]">{value}</dd>
    </div>
  );
}
