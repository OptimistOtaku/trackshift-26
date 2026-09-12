/* ===================================================================== *
 *  2 — The undercut. P0.
 *
 *  Set as a ledger on purpose. DEMO_BRIEF section 3: show the rate and the
 *  subtraction, never assert the outcome. A layout that is literally a
 *  subtraction with a rule line cannot assert an outcome — the reader does the
 *  last step themselves, and every sign is printed so they can check it.
 *
 *  Reference case, which is what loads: Austria, MEDIUM>HARD, both tyres 24
 *  laps old, 1.5 s behind → +1.76 s on the first lap out. Computing 1.80 means
 *  model.json predates the 11 Sep causality fix.
 * ===================================================================== */

import { useMemo, useState } from "react";
import { Plot, Path, VRule, extent } from "../components/Chart.jsx";
import { Field, Limitation, Pill, Select, SurfaceHead, Source } from "../components/ui.jsx";
import { fmt, pl, signed } from "../lib/model.js";

const COMPOUNDS = ["SOFT", "MEDIUM", "HARD"];
const opts = (xs) => xs.map((v) => ({ value: v, label: v }));

export default function Undercut({ M, index }) {
  const [round, setRound] = useState(8);
  const [from, setFrom] = useState("MEDIUM");
  const [to, setTo] = useState("HARD");
  const [mine, setMine] = useState(24);
  const [theirs, setTheirs] = useState(24);
  const [gap, setGap] = useState(1.5);

  const race = index.races.find((r) => r.round === round) ?? index.races[0];
  const pair = `${from}>${to}`;
  const known = M.hasPair(pair);

  const u = useMemo(
    () =>
      known
        ? M.undercut({ pair, trackTemp: race.track_temp_c, mine, theirs, gap, laps: 8 })
        : null,
    [M, known, pair, race.track_temp_c, mine, theirs, gap],
  );

  const firstLap = u?.rows[0];

  return (
    <section>
      <SurfaceHead
        n="2"
        title="What a stop buys you against the car ahead"
        lede={`The pit loss cancels. Both cars serve the same pit lane, so the twenty-two seconds
               drops out of the comparison and what is left is the lap-time difference between your
               new tyres and their old ones. That difference is what an undercut actually is, and it
               is measured, not assumed.`}
      />

      <div className="grid gap-5 lg:grid-cols-[300px_minmax(0,1fr)]">
        {/* ---------------- inputs ---------------- */}
        <div className="bg-raise p-5">
          <div className="space-y-4">
            <Field label="Event">
              <Select
                ariaLabel="Event"
                value={String(round)}
                onChange={(v) => setRound(Number(v))}
                options={index.races.map((r) => ({
                  value: String(r.round),
                  label: `${r.event.replace(" Grand Prix", "")} · ${fmt(r.track_temp_c, 1)}°C`,
                }))}
              />
            </Field>

            <div className="grid grid-cols-2 gap-3">
              <Field label="Coming off">
                <Select ariaLabel="Current compound" value={from} onChange={setFrom} options={opts(COMPOUNDS)} />
              </Field>
              <Field label="Fitting">
                <Select ariaLabel="New compound" value={to} onChange={setTo} options={opts(COMPOUNDS)} />
              </Field>
            </div>

            <Field label="Your tyre age" hint={pl(mine, "lap")}>
              <input
                type="range"
                min={1}
                max={40}
                step={1}
                value={mine}
                aria-label="Your tyre age in laps"
                onChange={(e) => setMine(Number(e.target.value))}
              />
            </Field>

            <Field label="Their tyre age" hint={pl(theirs, "lap")}>
              <input
                type="range"
                min={1}
                max={40}
                step={1}
                value={theirs}
                aria-label="Their tyre age in laps"
                onChange={(e) => setTheirs(Number(e.target.value))}
              />
            </Field>

            {/* There is no gap field anywhere in artifacts/demo and none can be
                derived from it. So it is an input, and it says so. */}
            <Field label="Gap to the car ahead" hint={`${fmt(gap, 1)} s`}>
              <input
                type="range"
                min={0}
                max={6}
                step={0.1}
                value={gap}
                aria-label="Gap to the car ahead in seconds"
                onChange={(e) => setGap(Number(e.target.value))}
              />
              <p className="mt-1.5 text-[11.5px] leading-relaxed text-faint">
                Your number, not ours. Nothing in the dataset measures the gap between two cars, so
                this is the one figure on the page you supply.
              </p>
            </Field>
          </div>

          <dl className="mt-5 space-y-2 border-t border-hair pt-4 text-[12.5px]">
            <Line label="Track temperature" value={`${fmt(race.track_temp_c, 1)} °C`} />
            <Line label="Pit loss here" value={`${fmt(race.pit_loss_s, 1)} s`} strike />
            <Line label="Stops measured at this event" value={String(race.stops)} />
          </dl>
          <p className="mt-2 text-[11.5px] leading-relaxed text-faint">
            Pit loss is struck through because it cancels — it is on screen to show it was not
            quietly dropped.
          </p>
        </div>

        {/* ---------------- the ledger ---------------- */}
        <div className="min-w-0">
          {!known ? (
            <div className="bg-panel p-5">
              <p className="text-[14px] text-dim">
                No stops were recorded from <Pill compound={from} /> to <Pill compound={to} /> this
                season, so there is no measured step for that change and this page will not invent
                one. Pick another pair.
              </p>
            </div>
          ) : (
            <>
              <div className="bg-panel p-5 md:p-6">
                <div className="mb-5 flex flex-wrap items-center gap-x-3 gap-y-2 text-[13px] text-dim">
                  <Pill compound={from} />
                  <span className="font-mono text-faint">→</span>
                  <Pill compound={to} />
                  <span>
                    at {race.event.replace(" Grand Prix", "")}, {pl(mine, "lap")} against{" "}
                    {pl(theirs, "lap")}
                  </span>
                </div>

                {/* The subtraction. Three rows and a rule — the whole argument. */}
                <dl className="font-mono text-[15px]">
                  <LedgerRow
                    label="Gap to the car ahead"
                    sub="your input"
                    value={signed(gap, 2)}
                    tone="text-white"
                  />
                  <LedgerRow
                    label="One lap on new tyres buys you"
                    sub={`${fmt(u.step0, 2)} s/lap for fresh rubber, less the ${fmt(
                      M.degVsFresh(mine),
                      2,
                    )} s/lap you were already losing, plus their extra lap of wear`}
                    value={signed(-firstLap.gained, 2)}
                    tone="text-flag"
                  />
                  <div className="ledger-rule my-2.5" />
                  <div className="flex items-start justify-between gap-6 pt-1">
                    <dt className="max-w-[34ch] text-[13px] leading-snug text-dim">
                      Gap after one lap
                    </dt>
                    <dd className="shrink-0 text-right">
                      <span
                        className={`num text-[40px] leading-none font-semibold md:text-[52px] ${
                          firstLap.ahead ? "text-flag" : "text-white"
                        }`}
                      >
                        {signed(firstLap.after, 2)}
                      </span>
                      <span className="ml-1.5 text-[15px] text-faint">s</span>
                    </dd>
                  </div>
                </dl>

                <p className="mt-4 max-w-[62ch] text-[13.5px] leading-relaxed text-dim">
                  {firstLap.ahead ? (
                    <>
                      A negative gap means you come out in front. You gain{" "}
                      <span className="num font-mono text-flag">{signed(firstLap.gained, 2)}</span> s
                      on the lap out, which clears {fmt(gap, 1)} s, and you rejoin on tyres{" "}
                      <span className="num font-mono text-white">{pl(u.needsThemOut, "lap")}</span>{" "}
                      fresher than theirs — until they stop, at which point that advantage reverses
                      and they are the ones on new rubber.
                    </>
                  ) : (
                    <>
                      You gain <span className="num font-mono text-flag">{signed(firstLap.gained, 2)}</span>{" "}
                      s on the lap out and that does not clear {fmt(gap, 1)} s.{" "}
                      {u.clears ? (
                        <>
                          It takes {pl(u.needsThemOut, "lap")} of them staying out before the gap
                          goes negative. Whether they stay out that long is a decision on another
                          pit wall.
                        </>
                      ) : (
                        <>
                          Eight laps of them staying out still does not clear it, so from here this
                          is not an undercut — it is a stop you take for some other reason.
                        </>
                      )}
                    </>
                  )}
                </p>
              </div>

              {/* Lap by lap, because the honest version of this answer is a
                  sequence of conditionals about what the other car does. */}
              <div className="mt-5 grid gap-5 md:grid-cols-2">
                <div className="bg-panel p-5">
                  <h3 className="mb-1 text-[15px] font-semibold">If they stay out</h3>
                  <p className="mb-3 text-[12.5px] leading-relaxed text-faint">
                    Cumulative time you take out of them, and the gap that leaves.
                  </p>
                  <table className="w-full text-[13px]">
                    <thead>
                      <tr className="text-left text-[11px] text-faint">
                        <th className="pb-1.5 font-normal">Laps out</th>
                        <th className="pb-1.5 text-right font-normal">You gain</th>
                        <th className="pb-1.5 text-right font-normal">Gap becomes</th>
                      </tr>
                    </thead>
                    <tbody className="font-mono">
                      {u.rows.map((r) => (
                        <tr key={r.k} className="border-t border-hair">
                          <td className="num py-1.5 text-dim">{r.k}</td>
                          <td className="num py-1.5 text-right text-flag">{signed(r.gained, 2)}</td>
                          <td
                            className={`num py-1.5 text-right ${
                              r.ahead ? "font-semibold text-flag" : "text-white"
                            }`}
                          >
                            {signed(r.after, 2)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                <div className="bg-panel p-5">
                  <h3 className="mb-1 text-[15px] font-semibold">The curve the number came from</h3>
                  <p className="mb-3 text-[12.5px] leading-relaxed text-faint">
                    Seconds per lap lost to tyre age, from{" "}
                    {M.raw.degradation_curves.race.n_stops} measured stops. Flat past{" "}
                    {fmt(M.D.peak_age, 1)} laps — the fitted quadratic bends down there, and letting
                    it fall would say tyres get faster as they wear.
                  </p>
                  <DegCurve M={M} mine={mine} theirs={theirs} />
                </div>
              </div>

              <div className="mt-5 space-y-5">
                {u.extrapolating && (
                  <Limitation title="Past the data">
                    One of those tyre ages is beyond the oldest set in the sample (
                    {fmt(M.D.max_age_seen, 0)} laps). The curve is held flat out there rather than
                    extended, so the number is a floor, not an estimate.
                  </Limitation>
                )}

                <Limitation title="We do not tell you which lap to stop on">
                  {index.window_is_not_reported}
                </Limitation>
              </div>

              <Source>
                model.json → intercept {fmt(M.raw.intercept, 6)}, pair {pair}{" "}
                {signed(M.raw.pairs[pair], 6)}, track-temp coefficient {signed(M.raw.tt_coef, 6)} per
                °C about a {fmt(M.raw.tt_mean, 2)} °C mean. Traffic is held at the sample mean: the
                model&rsquo;s traffic term is a difference across the stop, so half of it lies in the
                future at the moment you have to decide.
              </Source>
            </>
          )}
        </div>
      </div>
    </section>
  );
}

function Line({ label, value, strike = false }) {
  return (
    <div className="flex items-baseline justify-between gap-3">
      <dt className="text-dim">{label}</dt>
      <dd className={`num font-mono ${strike ? "text-faint line-through" : "text-white"}`}>
        {value}
      </dd>
    </div>
  );
}

function LedgerRow({ label, sub, value, tone }) {
  return (
    <div className="flex items-start justify-between gap-6 py-1.5">
      <div className="max-w-[46ch]">
        <dt className="text-[13.5px] leading-snug text-white">{label}</dt>
        {sub ? <p className="mt-0.5 font-sans text-[11.5px] leading-snug text-faint">{sub}</p> : null}
      </div>
      <dd className={`num shrink-0 text-right text-[17px] ${tone}`}>{value}</dd>
    </div>
  );
}

function DegCurve({ M, mine, theirs }) {
  const curve = M.raw.degradation_curves.race.curve;
  const ys = curve.map((p) => p.delta_s);
  return (
    <Plot
      xDomain={[0, Math.max(curve[curve.length - 1].age, mine, theirs)]}
      yDomain={extent([...ys, 0], 0.08)}
      height={200}
      pad={{ l: 44, r: 10, t: 10, b: 30 }}
      xLabel="tyre age, laps"
      fmtX={(v) => String(Math.round(v))}
    >
      {({ x, y, h, top }) => (
        <>
          <VRule at={M.D.peak_age} x={x} top={top} h={h} stroke="#333333" dash="3 3" />
          <Path points={curve.map((p) => [p.age, p.delta_s])} x={x} y={y} stroke="var(--color-flag)" width={2} />
          <circle cx={x(mine)} cy={y(M.phi(mine))} r="3.5" fill="#ffffff" />
          <circle cx={x(theirs)} cy={y(M.phi(theirs))} r="3.5" fill="none" stroke="#ffffff" strokeWidth="1.5" />
          <text
            x={x(mine)}
            y={y(M.phi(mine)) - 8}
            textAnchor="middle"
            fill="#ffffff"
            fontSize="10"
            fontFamily="var(--font-mono)"
          >
            you
          </text>
        </>
      )}
    </Plot>
  );
}
