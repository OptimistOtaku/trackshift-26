/* ===================================================================== *
 *  4 — Out of sample.
 *
 *  step_obs_s is measured, step_pred_s is the model's prediction for that stop
 *  fitted WITHOUT the event it belongs to. Plotting one against the other is
 *  the validation figure; no extra computation is needed and none is done.
 *  The headline statistics are read from index.json, not recomputed here, so
 *  this page cannot quietly disagree with the paper.
 * ===================================================================== */

import { useEffect, useMemo, useState } from "react";
import { getRace } from "../lib/data.js";
import { Plot, Path, Mark, extent } from "../components/Chart.jsx";
import { Limitation, Pill, SurfaceHead, Source } from "../components/ui.jsx";
import { fmt, signed } from "../lib/model.js";

export default function Validation({ M, index }) {
  const [stops, setStops] = useState(null);
  const [err, setErr] = useState(null);
  const [highlight, setHighlight] = useState(0); // 0 = every event

  useEffect(() => {
    let live = true;
    Promise.all(index.races.map((r) => getRace(r.round)))
      .then((races) => {
        if (!live) return;
        const all = [];
        races.forEach((rc) => {
          rc.stops.forEach((s) => {
            if (s.step_obs_s == null || s.step_pred_s == null) return;
            all.push({ ...s, round: rc.round, event: rc.event });
          });
        });
        setStops(all);
      })
      .catch((e) => live && setErr(e.message));
    return () => {
      live = false;
    };
  }, [index.races]);

  const shown = useMemo(
    () => (stops ? (highlight ? stops.filter((s) => s.round === highlight) : stops) : []),
    [stops, highlight],
  );

  const worst = useMemo(
    () =>
      [...shown]
        .map((s) => ({ ...s, resid: s.step_obs_s - s.step_pred_s }))
        .sort((a, b) => Math.abs(b.resid) - Math.abs(a.resid))
        .slice(0, 6),
    [shown],
  );

  const h = index.headline;

  if (err) {
    return (
      <section>
        <SurfaceHead n="4" title="Out of sample" />
        <p className="text-[14px] text-dim">Could not read the race files. {err}</p>
      </section>
    );
  }

  if (!stops) {
    return (
      <section>
        <SurfaceHead n="4" title="Out of sample" />
        <p className="font-mono text-[13px] text-faint">Reading {index.races.length} events…</p>
      </section>
    );
  }

  const vals = [...stops.map((s) => s.step_obs_s), ...stops.map((s) => s.step_pred_s)];
  const dom = extent(vals, 0.06);
  const lo = dom[0];
  const hi = dom[1];

  return (
    <section>
      <SurfaceHead
        n="4"
        title="Every stop, scored by a model that had not seen the race"
        lede={`Leave one event out, fit on the other eleven, predict every stop at the event that
               was held back, repeat. The model scoring Silverstone has never seen Silverstone. The
               season-average baseline goes through the identical loop, so neither side gets a free
               constant the other does not.`}
      />

      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_280px]">
        <div className="bg-panel p-5">
          <div className="mb-4 flex flex-wrap items-baseline justify-between gap-3">
            <div className="flex items-baseline gap-5 text-[12.5px] text-dim">
              <span className="flex items-baseline gap-2">
                <span aria-hidden className="inline-block h-0 w-5 border-t border-white" />
                perfect prediction
              </span>
              <span className="flex items-baseline gap-2">
                <span aria-hidden className="inline-block h-0 w-5 border-t-2 border-flag" />
                what we actually do
              </span>
            </div>
            <span className="num font-mono text-[12px] text-faint">
              {shown.length} stops plotted
            </span>
          </div>

          <Plot
            xDomain={[lo, hi]}
            yDomain={[lo, hi]}
            height={360}
            xLabel="predicted, s/lap"
            yLabel="observed, s/lap"
            fmtX={(v) => v.toFixed(1)}
            fmtY={(v) => v.toFixed(1)}
            zeroLine
          >
            {({ x, y }) => (
              <>
                {/* y = x. Perfect prediction, for reference only — we are not on it. */}
                <Path
                  points={[
                    [lo, lo],
                    [hi, hi],
                  ]}
                  x={x}
                  y={y}
                  stroke="#ffffff"
                  width={1}
                  dash="4 4"
                />

                {/* The reported calibration line: observed = slope x predicted,
                    through the season mean. Slope 0.79, read from index.json —
                    not refitted in the browser, so it cannot drift from the
                    number in the paper. */}
                {(() => {
                  const mx = stops.reduce((a, s) => a + s.step_pred_s, 0) / stops.length;
                  const my = stops.reduce((a, s) => a + s.step_obs_s, 0) / stops.length;
                  const f = (px) => my + h.calib_slope * (px - mx);
                  return (
                    <Path
                      points={[
                        [lo, f(lo)],
                        [hi, f(hi)],
                      ]}
                      x={x}
                      y={y}
                      stroke="var(--color-flag)"
                      width={2}
                    />
                  );
                })()}

                {stops.map((s, i) => {
                  const on = !highlight || s.round === highlight;
                  return (
                    <Mark
                      key={i}
                      cx={x(s.step_pred_s)}
                      cy={y(s.step_obs_s)}
                      r={on ? 3 : 2}
                      stroke={on ? (highlight ? "var(--color-flag)" : "#9a9a9a") : "#2a2a2a"}
                      width={1}
                    />
                  );
                })}
              </>
            )}
          </Plot>

          <p className="mt-3 max-w-[70ch] text-[13px] leading-relaxed text-dim">
            The yellow line is flatter than the dashed one. A calibration slope of{" "}
            <span className="num font-mono text-flag">{fmt(h.calib_slope, 2)}</span> means that when
            the model says a stop is worth a lot, it is usually worth somewhat less than that, and
            when it says a little, usually somewhat more. The ordering is largely right; the spread
            is compressed by about a fifth. That is a real limitation and it is on the chart rather
            than in a footnote.
          </p>
        </div>

        <div className="space-y-5">
          <div className="bg-raise p-5">
            <div className="mb-3 text-[12.5px] text-dim">Highlight one event</div>
            <select
              aria-label="Highlight event"
              value={String(highlight)}
              onChange={(e) => setHighlight(Number(e.target.value))}
            >
              <option value="0">All {index.races.length} events</option>
              {index.races.map((r) => (
                <option key={r.round} value={String(r.round)}>
                  {r.event.replace(" Grand Prix", "")} ({r.stops})
                </option>
              ))}
            </select>

            <dl className="mt-5 space-y-2.5 text-[13px]">
              <Stat label="Out-of-sample RMSE" value={`${fmt(h.rmse_s, 2)} s`} tone="text-flag" />
              <Stat label="Season-mean baseline" value={`${fmt(h.baseline_rmse_s, 2)} s`} />
              <Stat label="Improvement" value={`${fmt(h.improvement_pct, 1)} %`} />
              <Stat label="Mean absolute error" value={`${fmt(h.mae_s, 2)} s`} />
              <Stat label="Bias" value={`${signed(h.bias_s, 2)} s`} />
              <Stat label="Stops scored" value={`${h.n_scored} of ${h.stops}`} />
              <Stat label="Events scored" value={`${h.events_scored} of ${h.events}`} />
              <Stat label="Events beaten" value={`${h.events_won} of ${h.events_compared}`} />
            </dl>
            <p className="mt-3 text-[11.5px] leading-relaxed text-faint">
              Read from index.json. Nothing on this page recomputes them, so this page cannot
              disagree with the write-up.
            </p>
          </div>

          <div className="bg-panel p-5">
            <h3 className="mb-1 text-[15px] font-semibold">Where it misses worst</h3>
            <p className="mb-3 text-[12px] leading-relaxed text-faint">
              Largest residuals in view. Observed minus predicted.
            </p>
            <ul className="space-y-1.5 font-mono text-[12px]">
              {worst.map((s, i) => (
                <li key={i} className="flex items-baseline justify-between gap-3">
                  <span className="truncate text-dim">
                    {s.driver} L{s.pit_lap} {s.event.replace(" Grand Prix", "")}
                  </span>
                  <span className={`num shrink-0 ${s.resid > 0 ? "text-white" : "text-tifosi"}`}>
                    {signed(s.resid, 2)}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>

      {/* The three things we built and cut. On the surface, not in an appendix. */}
      <div className="mt-6">
        <h3 className="mb-3 text-[15px] font-semibold">Three things we tested and cut</h3>
        <div className="grid gap-5 md:grid-cols-3">
          <Limitation title="The practice degradation curve">
            {M.raw.degradation_curves.not_a_predictor}
          </Limitation>
          <Limitation title="The pit window">{index.window_is_not_reported}</Limitation>
          <Limitation title="A per-compound saturating curve">
            The saturation age is not identified. The sum of squares barely moves across the whole
            plausible range, and with three compounds the term is collinear with stint position. One
            shared curve, held flat past{" "}
            <span className="num font-mono text-white">{fmt(M.D.peak_age, 1)}</span> laps, is what we
            can defend.
          </Limitation>
        </div>
      </div>

      <div className="mt-5 bg-panel p-5">
        <h3 className="mb-2 text-[15px] font-semibold">What this is actually for</h3>
        <p className="max-w-[74ch] text-[13.5px] leading-relaxed text-dim">
          The same confound sits in any fleet that replaces a wearing part on a duty cycle. Tyre
          wear on an Indian commercial-vehicle fleet is collinear with load, route and season, so a
          naive fit on age reads the wrong sign for the same reason ours did in practice. The
          transferable piece is not the coefficient — it is the move: find the moment the part
          resets and the confound does not, and measure the step across it.
        </p>
        <div className="mt-3 flex items-center gap-2 text-[12px] text-faint">
          <Pill compound="SOFT" />
          <Pill compound="MEDIUM" />
          <Pill compound="HARD" />
          <span>
            {M.raw.n_obs} stops, {index.races.length} events, {index.season} season
          </span>
        </div>
      </div>

      <Source>
        races/R01–R{String(index.races.length).padStart(2, "0")}.json → stops[].step_obs_s against
        stops[].step_pred_s. Baseline is the season mean scored through the same
        leave-one-event-out loop: {h.baseline_spec}.
      </Source>
    </section>
  );
}

function Stat({ label, value, tone = "text-white" }) {
  return (
    <div className="flex items-baseline justify-between gap-3">
      <dt className="text-dim">{label}</dt>
      <dd className={`num font-mono ${tone}`}>{value}</dd>
    </div>
  );
}
