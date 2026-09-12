/* ===================================================================== *
 *  Charts, hand-rolled in SVG.
 *
 *  No chart library, for two reasons. One: every CDN import is a thing that
 *  can fail on stage, and this demo has to survive the wifi being switched
 *  off. Two: every mainstream library smooths a polyline by default, and the
 *  one curve on this page that MUST NOT be smoothed is phi() at peak_age —
 *  a spline through that corner draws tyres getting faster as they wear,
 *  which is the exact error the project exists to point at. Straight
 *  segments only. The kink is the finding.
 * ===================================================================== */

import { useEffect, useLayoutEffect, useRef, useState } from "react";

/* Render at real pixel width so a 1px rule is 1px, not 1px scaled by a
   viewBox. preserveAspectRatio tricks distort strokes and type; measuring is
   fifteen lines and correct. */
function useWidth() {
  const ref = useRef(null);
  const [w, setW] = useState(0);
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return undefined;
    const ro = new ResizeObserver(([e]) => setW(Math.floor(e.contentRect.width)));
    ro.observe(el);
    setW(Math.floor(el.getBoundingClientRect().width));
    return () => ro.disconnect();
  }, []);
  return [ref, w];
}

const lerp = (t, a, b) => a + t * (b - a);

export function niceTicks(lo, hi, count = 5) {
  if (!(hi > lo)) return [lo];
  const raw = (hi - lo) / count;
  const mag = 10 ** Math.floor(Math.log10(raw));
  const norm = raw / mag;
  const step = (norm >= 5 ? 10 : norm >= 2 ? 5 : norm >= 1 ? 2 : 1) * mag;
  const out = [];
  for (let v = Math.ceil(lo / step) * step; v <= hi + step * 1e-9; v += step) {
    out.push(Number(v.toFixed(10)));
  }
  return out;
}

export function extent(values, padFrac = 0.08) {
  const nums = values.filter((v) => Number.isFinite(v));
  if (!nums.length) return [0, 1];
  let lo = Math.min(...nums);
  let hi = Math.max(...nums);
  if (lo === hi) {
    lo -= 0.5;
    hi += 0.5;
  }
  const pad = (hi - lo) * padFrac;
  return [lo - pad, hi + pad];
}

/* --------------------------------------------------------------------- *
 *  Plot — the frame, the axes, the scales. Children are a render prop and
 *  receive { x, y, w, h, left, top } so a surface can draw in data units and
 *  never think about pixels.
 * --------------------------------------------------------------------- */
export function Plot({
  xDomain,
  yDomain,
  height = 280,
  pad = { l: 52, r: 16, t: 14, b: 34 },
  xTicks,
  yTicks,
  xLabel,
  yLabel,
  fmtX = (v) => String(v),
  fmtY = (v) => v.toFixed(2),
  zeroLine = false,
  children,
  onPointerMove,
  onPointerLeave,
  className = "",
}) {
  const [ref, w] = useWidth();
  const innerW = Math.max(10, w - pad.l - pad.r);
  const innerH = Math.max(10, height - pad.t - pad.b);

  const x = (v) =>
    pad.l + lerp((v - xDomain[0]) / (xDomain[1] - xDomain[0] || 1), 0, innerW);
  const y = (v) =>
    pad.t + lerp((v - yDomain[0]) / (yDomain[1] - yDomain[0] || 1), innerH, 0);
  x.invert = (px) =>
    xDomain[0] + ((px - pad.l) / (innerW || 1)) * (xDomain[1] - xDomain[0]);

  const tx = xTicks ?? niceTicks(xDomain[0], xDomain[1], 6);
  const ty = yTicks ?? niceTicks(yDomain[0], yDomain[1], 5);

  return (
    <div ref={ref} className={className}>
      {w > 0 && (
        <svg
          width={w}
          height={height}
          role="img"
          onPointerMove={onPointerMove ? (e) => onPointerMove(e, x, y) : undefined}
          onPointerLeave={onPointerLeave}
          style={{ display: "block", touchAction: "none" }}
        >
          {/* Grid. Faint enough to read a value against, quiet enough to
              disappear when you are looking at the lines. */}
          {ty.map((v) => (
            <line
              key={`gy${v}`}
              x1={pad.l}
              x2={pad.l + innerW}
              y1={y(v)}
              y2={y(v)}
              stroke="#1e1e1e"
              strokeWidth="1"
              shapeRendering="crispEdges"
            />
          ))}
          {tx.map((v) => (
            <line
              key={`gx${v}`}
              x1={x(v)}
              x2={x(v)}
              y1={pad.t}
              y2={pad.t + innerH}
              stroke="#161616"
              strokeWidth="1"
              shapeRendering="crispEdges"
            />
          ))}

          {/* Zero. Heavier and white, because on the sign-flip chart the whole
              argument is which side of this line a curve sits on. */}
          {zeroLine && yDomain[0] < 0 && yDomain[1] > 0 && (
            <line
              x1={pad.l}
              x2={pad.l + innerW}
              y1={y(0)}
              y2={y(0)}
              stroke="#ffffff"
              strokeWidth="1"
              shapeRendering="crispEdges"
            />
          )}

          {ty.map((v) => (
            <text
              key={`ty${v}`}
              x={pad.l - 8}
              y={y(v) + 3.5}
              textAnchor="end"
              fill="var(--color-faint)"
              fontSize="10.5"
              fontFamily="var(--font-mono)"
            >
              {fmtY(v)}
            </text>
          ))}
          {tx.map((v) => (
            <text
              key={`tx${v}`}
              x={x(v)}
              y={pad.t + innerH + 15}
              textAnchor="middle"
              fill="var(--color-faint)"
              fontSize="10.5"
              fontFamily="var(--font-mono)"
            >
              {fmtX(v)}
            </text>
          ))}

          {xLabel && (
            <text
              x={pad.l + innerW}
              y={height - 4}
              textAnchor="end"
              fill="var(--color-faint)"
              fontSize="10.5"
            >
              {xLabel}
            </text>
          )}
          {yLabel && (
            <text
              x={pad.l - 8}
              y={pad.t - 4}
              textAnchor="end"
              fill="var(--color-faint)"
              fontSize="10.5"
            >
              {yLabel}
            </text>
          )}

          {children({ x, y, w: innerW, h: innerH, left: pad.l, top: pad.t })}
        </svg>
      )}
    </div>
  );
}

/* Straight segments through the points. No curve interpolation — see header. */
export function Path({ points, x, y, stroke, width = 2, dash }) {
  const usable = points.filter((p) => Number.isFinite(p[1]));
  if (usable.length < 2) return null;
  const d = usable
    .map((p, i) => `${i === 0 ? "M" : "L"}${x(p[0]).toFixed(2)} ${y(p[1]).toFixed(2)}`)
    .join(" ");
  return (
    <path
      d={d}
      fill="none"
      stroke={stroke}
      strokeWidth={width}
      strokeDasharray={dash}
      strokeLinejoin="miter"
      strokeLinecap="butt"
      vectorEffect="non-scaling-stroke"
    />
  );
}

export function VRule({ at, x, top, h, stroke = "var(--color-flag)", dash }) {
  return (
    <line
      x1={x(at)}
      x2={x(at)}
      y1={top}
      y2={top + h}
      stroke={stroke}
      strokeWidth="1"
      strokeDasharray={dash}
      shapeRendering="crispEdges"
    />
  );
}

/* A small open square, not a filled circle: two series overlap heavily in the
   validation scatter and open marks stay readable where discs blur together. */
export function Mark({ cx, cy, r = 3, stroke, fill = "none", width = 1 }) {
  return (
    <rect
      x={cx - r}
      y={cy - r}
      width={r * 2}
      height={r * 2}
      fill={fill}
      stroke={stroke}
      strokeWidth={width}
    />
  );
}

/* Deferred mount: the ResizeObserver needs one frame, and a chart that paints
   at width 0 then snaps is a flicker on a projector. */
export function useMounted() {
  const [on, setOn] = useState(false);
  useEffect(() => {
    const id = requestAnimationFrame(() => setOn(true));
    return () => cancelAnimationFrame(id);
  }, []);
  return on;
}
